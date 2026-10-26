## 结论与交接状态

本轮选择一个共同目标：**删除仅为阶段交接而存在的 GM 物化，并按采样点数决定是否值得保留全输入 packed 布局**。

- **子例 a，S=32768：保留全输入双份配对 packing；把几何生成并入采样 owner，采样结果直接写最终 NCS 输出，取消全域 geometry 表和 Compact。**
- **子例 b，S=8：不做全输入 packing；单 owner 按需从 NCDHW 搬入八邻域、在 UB 重排并计算，直接写最终输出。几何同样在本地生成，不保留 geometry/ypad workspace。**

这不是已实现或已验证候选。状态为 **conditional_plan / source_reviewed / not_measured**：地址与生命周期可以纸面闭合，但实际 SDK、可分配 UB、Host workspace/launch 接线仍须在 C3 实施前核验。缺少计时不否决这两个试验；也不由逻辑字节减少推导确定加速比。

以下以用户指定的当前四阶段序列为父本，不把最早的 `GridSampler3DScalar` 当成当前运行路径。未执行工具、路由命令、编译或硬件测试；不虚构 hash、机器注册回执或正确性结果。

---

## 一、共同理解：当前实际路径与数值依赖

记：

\[
I=DHW=32768,\quad C=63,\quad C_p=64,\quad e=4\text{ B}
\]

当前实际序列是：

```text
grid → GridGeometryRange → GM geometry
x(NCDHW) → GridPackChannels<float> → GM paired-packed x
geometry + packed x → GridSampleChannels<float> → GM padded NCS
padded NCS → GridCompactOutput<float>(small=false) → 最终紧凑 NCS
```

### 1. 数学和数值顺序

对空间点 \(p\)，坐标依次经过源码的：

1. `GridUnnormalize`；本例 `alignCorners=false`；
2. `GridApplyPadding`；本例 zeros；
3. `GridFloor`，形成八邻域；
4. 按 `k` 的位选择 x/y/z 方向权重。

当前 `GridGeometryRange:258-268` 将每个权重按：

\[
w_k=\operatorname{float}(\operatorname{float}(w_xw_y)w_z)
\]

形成并保存。当前通道采样按 **k=0…7 顺序**消费：

- 普通路径：每个邻居先 `Mul`，再有序 `Add`；
- `GridNeedsFma32` 命中时：调用现有 `GridFma32Bits` 路径。

**本轮保持这套实际计算组织，不改为嵌套 lerp、树形求和、低精度或 Cube 归约，也不擅自合并 Mul/Add。** 最早原始标量代码的 `x*wx*wy*wz` 与当前预先形成权重的组织不能仅凭实数公式认定逐位等价；原 oracle 的完整验证仍须保留。

本例 x 在 [-1,1]、grid 严格内部，说明本次运行不会使用边界备用搬运，不能据此删除通用路径的异常值、范围检查或软件数值分支。派发也不能只凭 shape 就假定输入有限、grid 内部。

### 2. paired-packed 布局

由 `GridPackChannels:1126-1135`，可写成：

\[
P[n,i,0,c]=X[n,c,i]
\]

\[
P[n,i,1,c]=
\begin{cases}
X[n,c,i+HW],&i+HW<I\\
0,&\text{否则}
\end{cases}
\]

通道补到 64，另有空间哨兵。物理地址以元素计：

\[
((n(I+1)+i)\cdot2+\text{slot})C_p+c
\]

这使一个内部点的八邻域能用 `GridSampleChannels:1162` 的一次 API 表达：

- `blockCount=2`；
- 每块 `4Cp*sizeof(float)=1024 B`；
- 两块总有效读 2048 B；
- GM 间隙为 \((W-2)2C_pe=15360\) B。

因此，**当前内部邻域搬运已经不是逐通道一次 API**。不能再把“API 一次能处理 cp 通道”当作尚未完成的优化。

### 3. 可由源码算出的分块与空间

| 项目 | 推导值 |
|---|---:|
| 原输入有效字节 \(4CI\) | 8,257,536 B |
| paired-packed 段 \(8(I+1)C_p\) | 16,777,728 B |
| pack 的 `p_` | 224 点 |
| pack tile 数 | 147，最后 64 点 |
| pack 显式 UB | 174,080 B |
| sample 的 `batch_` | 48 点 |
| sample 显式 UB | 163,840 B |
| Compact 显式 UB | 65,536 B |

sample 的 48 点来自初始化容量循环：64 点不满足源码预算，减到 48 点后满足。上述 UB 是**显式分配账**，不是目标实际可用 UB 已核验的证明；源码常量 `188160` 也不能代替平台资源事实。

---

## 二、子例 a：S=32768

### A1. 当前路径与关键事实

- 几何记录数：32768；几何已经按空间点生成一次，**没有每通道重复生成 63 次**。
- geometry 为八个 uint32 偏移、八个 float 权重，共 \(64S=2,097,152\) B。
- sample 为 \(\lceil32768/48\rceil=683\) 个 tile，末 tile 32 点。
- 内部邻域输入搬运：32768 次 API，逻辑 packed 读 67,108,864 B。
- \(S\) 已是 16 元素对齐，故 `sa=S`；所谓 padded 输出在本例实际上没有额外空间 padding。
- 最终输出有效字节 \(4CS=8,257,536\) B。即使 `sa=S`，当前仍完整执行 Compact 的读和写。

按输入源码可见的数据区，当前算法 workspace 为：

\[
W_a=P+64S+4C\,AlignUp(S,16)
=27,132,416\text{ B}
\]

不含未给出的框架保留区。

### A2. 主方案：保留 packing，几何本地化并直接输出

候选序列：

```text
全输入 paired pack
    ↓ launch/stream 完成依赖
本地几何生成 → packed 邻域读取 → 原有序计算 → 最终 y
```

每个 sample tile 的唯一 owner：

1. 从原 grid 生成本 tile 的偏移和权重；
2. 写入现有 `geometry_` UB 分配，而不是 GM geometry；
3. 继续使用现有 Brcb、邻域搬运、数值判别、Mul/Add 或软件路径；
4. 转置后直接写最终 y。

**全域工作变化：**

| 工作 | 当前 | 候选 |
|---|---:|---:|
| 几何生成次数 | \(S\) | \(S\)，不减少数学生成次数 |
| geometry GM 写读 | \(128S\) B | 0 |
| 全输入 pack | 完整执行 | 完整保留 |
| packed 邻域逻辑读 | \(2048S\) B | 不变 |
| sample 输出 | \(4CS\) B 到 workspace | \(4CS\) B 到最终 y |
| Compact 读写 | \(8CS\) B | 0 |
| 阶段启动数 | 4 | 2 |

可消除的逻辑 GM 请求：

\[
\Delta B_a=128S+8CS=632S
=20,709,376\text{ B}
\]

这里只计请求 payload，不是实测 HBM 字节。

若仅统计这些源码可见数据访问，当前与候选分别为：

\[
B_{\text{old}}=4CI+P+(12+128+2048+12C)S
=121,504,256\text{ B}
\]

\[
B_{\text{new}}=4CI+P+(12+2048+4C)S
=100,794,880\text{ B}
\]

候选算法 workspace 仅保留 packed 段：

\[
W'_a=P=16,777,728\text{ B}
\]

### A3. 最有竞争力的替代：直接 NCDHW 按需搬运

将子例 b 的按需方案推广到 a，也可以取消全输入 pack。它会减少原输入全扫描及 packed 写入，并将邻域有效读从每点 2048 B 降为 2016 B。

但本方案所选具体实现每个点需要四组“两 x 邻居 × 全通道”的规则搬运：

- 邻域搬运调用由 \(S\) 增为 \(4S=131072\)；
- 新增 \(4S\) 次 UB Gather；
- 每点四组 staging 的物理行跨度合计 8192 B，虽然有效 GM 输入只有 2016 B；
- 全域还要构造/使用 Gather 索引，并维护 staging 的读完→覆盖依赖。

在 a 中，全输入 pack 的一次性读写成本摊到每个采样点约为：

\[
(4CI+P)/S \approx 764\text{ B/点}
\]

它换来了规则的大邻域读取。当前没有时间权重证明哪方更快；本轮优先保留这一已存在的通路，先删除 **20.7 MB 的确定交接请求**，避免同时引入大规模短行 padding 和 Gather。

另一个有力替代是改成单份 `[I+1,Cp]` packing：约少写、少占 8 MiB，但八邻域读取需要重新组织，不能继续照搬当前一次 paired 读取。其额外搬运调用、UB 重排和边界路径需重新比较，本轮不叠加。

### A4. Action 实例

任务内纸面实例 **A-a**：

- 注册意图：`action.reduce_memory_traffic`，输入提供的 v0006 正文。
- 目标：当前 GM geometry、sample→Compact 的输出中间段。
- 阶段：`GridGeometryRange`、`GridSampleChannels<float>`、`GridCompactOutput<float>`。
- 父实现：本输入声明的四阶段实际路径及对应源码定位。
- 覆盖：所列 a 的 FP32/NCDHW/bilinear/zeros/alignCorners=false 元数据域；其他域保留原序列。
- 配套变更：阶段组合、本地几何生成、最终输出接线和 workspace 公式。
- 不另加“输入驻留”或“不变量外提”实例：这里保存的是派生几何，不是原输入；也不是仅缓存控制字段。
- 准入：具体可删读写关系已明确；语义保持按上述约束实施；capacity 和实际接口/接线尚待核验，不能标成全部 true。

一个 Action 足以表达删除这些交接物化的共同目标，阶段组合属于其必要实现步骤，不再对同一批字节重复登记收益。

---

## 三、子例 b：S=8

### B1. 当前路径与关键事实

- 输出仅 \(63\times8=504\) 个 float，即 2016 B。
- geometry 为 512 B。
- sample 只有一个 tile、`count=8`；增加 BlockDim 不会让该循环产生更多有效空间任务。
- 全输入 pack 仍处理 8,257,536 B 原输入，写出 16,777,728 B packed 数据；同一次调用仅使用一次，不存在跨调用摊销。
- sample 的有效邻域 packed 读只有 16,384 B。
- `sa=16`，输出 workspace 为 4032 B，但 sample 实际只写各行前 8 个元素，不能把未写 padding 也算成已搬运字节。

当前算法 workspace：

\[
W_b=P+512+4032=16,782,272\text{ B}
\]

按与 a 相同的 payload 口径，当前逻辑数据访问为 25,058,816 B。这里显著的结构事实是**全输入转换规模与实际消费规模不同**，不是“已经测到启动或带宽主导”。

### B2. 主方案：单 owner 的按需邻域搬运与计算

候选只启动一个 AIV owner，拥有完整 `[C,S]=[63,8]` 输出。步骤如下。

#### 从 NCDHW 按需读取

对每个点，按 `(z位,y位)` 的四个组合，搬入相邻的 `x0,x1`：

```text
GM：每通道两个连续 float，通道间隔一个 I 平面
UB：每通道一行，行跨度 32 B
```

具体 GM→UB 参数：

- `blockCount=63`；
- `blockLen=8 B`；
- `srcStride=(I-2)*4=131064 B`；
- `dstStride=0`；
- staging 行跨度 32 B。

每组有效读 \(63\times8=504\) B，UB 行跨度总计 2048 B，包含预留的 dummy 通道行。用固定索引：

\[
index[jC_p+c]=32c+4j,\quad j\in\{0,1\}
\]

将两列提取到规范的 `raw[p,k,c]` 布局。第 63 个补齐通道显式定义为零，不读取源输入的第 64 通道。

八个点总计：

- **32 次 GM→UB 多块搬运**；
- **32 次 Gather**；
- 输入有效读 \(8CS\times4=16,128\) B。

当前所列 grid 全部内部，走上述两列路径。候选不能仅凭 shape 将这一数据属性硬编码：若保留该元数据入口的通用输入能力，须检查现有几何偏移；不满足合法相邻对时，使用逐合法邻居的有界搬运，非法邻居定义为零，禁止先越界读后 mask。

#### 本地几何、原计算和紧凑输出

- 八点几何仍使用原公共函数和原权重形成顺序，本地保存一次。
- 将 `batch=8`、`gTile=64` 明确作为 C2 参数。
- 采用原 Brcb 和 Apply 数值路径；raw 的邻居槽由原 paired slot 顺序改为规范 k 顺序，消费者地址必须同步修改，k 累加顺序不变。
- 转置得到 `[Cp,8]` 后，前 \(63\times8\) 个元素恰好是紧凑 NCS。
- 单次有效长度 2016 B 的 UB→GM `DataCopyPad` 写最终 y；不写第 64 通道。

### B3. 全部变化和代价

| 工作 | 当前 | 候选 |
|---|---:|---:|
| 全输入 pack 原输入读 | 8,257,536 B | 0 |
| packed 全域写 | 16,777,728 B | 0 |
| 采样输入有效读 | 16,384 B | 16,128 B |
| geometry GM 写读 | 1024 B | 0 |
| 输出交接和 Compact | 三次有效输出访问 | 一次最终输出写 |
| 几何生成次数 | 8 | 8 |
| 阶段启动数 | 4 | 1 |
| 算法 GM workspace | 16,782,272 B | 0 |

候选有效逻辑数据访问：

\[
B'_b=12S+32CS+4CS
=18,240\text{ B}
\]

相对当前可减少 25,040,576 B 的该口径请求。**这是静态通路差异，不是 HBM 节省或时延测量。**

新增代价包括：

- 32 次短行多块搬运、32 次 Gather；
- staging 每组 2048 B 的 UB 物理跨度，32 组合计 65,536 B 跨度；不能与有效 GM 字节混为一账；
- 固定两列 Gather 索引、规范 raw 布局转换；
- 单 owner 不暴露通道并行；
- DMA→Gather、Gather 读完→staging 覆盖的完成边；
- 边界输入的额外有界备用路径和验证成本。

### B4. 最有竞争力的替代

**保留全输入 pack，只做 a 的本地几何和直接输出。**

它复用现有邻域大块读取，只有 8 次邻域搬运，避免 32 次 Gather，且修改面更小；但仍支付约 25 MB 的一次性全输入读写。本轮 b 只有 8 个点且没有已有 packed 副本、没有调用间复用，因此优先试按需路径。

另一个竞争方案是按通道对分给多个 owner：

- S=8 时每通道输出 32 B，可按两通道组成 64 B owner；
- 可产生 32 个任务，最后一个只含一个通道；
- 不需要八邻居归约的跨核合并。

但它增加任务调度，并可能在各 owner 重读 grid/重算几何，或重新引入共享 geometry 阶段。504 个输出是否值得更多核完全未测。本轮选单 owner 是为了避免为极小结果建立额外协议，并不是断言多核一定慢。

### B5. Action 实例

任务内纸面实例 **A-b**：

- 注册意图：同为 `action.reduce_memory_traffic` v0006。
- 目标：全输入 packed 中间表示，以及 geometry/ypad 交接段。
- 阶段：当前 pack→sample→Compact 数据通路。
- 变换：让消费者接受原 NCDHW stride，仅对实际邻域做本地重排，删除全输入转换物化。
- 不是 `reuse_input_tiles`：候选没有证明任意两个 grid 点取到相同原输入，不登记未获证的邻域输入复用。
- 不是 `coalesce_contiguous_transfers` 的直接实例：当前 paired 内部读取已经合并；新方案实际增加采样搬运调用，目标是取消全输入转换，而非声称邻域调用进一步减少。
- 覆盖和合法性：按下面 C2 元数据谓词；输入值不作为 Host 派发条件。capacity、SDK 和接线验证仍是实施前缺项。

---

## 四、统一 C2 共同计划

纸面计划身份记为 **grid-paper-r1**，分析基础是本次输入源码。没有计算源码/template hash；正式工件应在获准实施时补齐，不使用伪 hash。

### 1. 分派与覆盖

仅为已说明的不同数据通路设互斥分组，不猜测最优 S 阈值：

| 组 | 元数据条件 | 执行计划 |
|---|---|---|
| a | FP32，N=1/C=63/D=H=W=32，S=32768，bilinear/zeros/alignCorners=false，外部 NCDHW | paired pack + 本地几何采样直接输出 |
| b | 同上，但 S=8 | 单 owner 按需 NCDHW 采样直接输出 |
| fallback | 所有其他支持的元数据 | 原四阶段通用路径 |

S 的判断绑定实际 `spatialOut`，不绑定 case 名称或输出三维的某一种分解。grid 内容、x 值范围不进入 Host shape 派发。目标 dav-2201 来自用户约束，不冒充设备探测；核数、SDK 和可用 UB 分别待确认。

可在正式实现中为两个特化和 fallback 分配唯一 uint64 key；当前材料未给出现工程 key 表，**不在纸面凭空指定可能冲突的数值**。

### 2. 所有权、布局和同步

**a：**

- pack 保留原 tile 所有权和 paired 布局。
- sample tile owner 独占全部 63 通道的空间段。
- 每个 tile 起点是 48 的倍数；各通道行起点 `c*S`、tile 起点和有效长度都满足本例 64 B 边界，末 tile 为 32 点。
- pack 全部完成后才启动消费 packed 的采样阶段，保留 stream/launch 完成关系。
- 几何只由本 tile owner 生成和消费，不存在跨核 geometry 发布。
- 输出直接写 `y[n*C*S+c*S+p]`，不再写 workspace。

**b：**

- 一个 owner 拥有所有 504 个有效输出，避免短行在不同 owner 间共享物理边界。
- staging 的前 63 行由 DMA 定义，dummy 通道由初始化定义；Gather 不读取每行无定义的 padding。
- 每次 DMA 完成后才能 Gather；Gather 完成读取 staging 后才能下一组 DMA 覆盖。
- raw 全部生成后才能做数值判别和消费；最后有序 Add 完成后才能复用 values 作转置输出。
- 最终 MTE3 完成读取后才能结束或复用输出区。
- 无跨核归约、无跨核共享 UB、无新增全局槽。

### 3. 同时存活容量

**a** 沿用 sample 的显式分配：

\[
U_{\text{sample,a}}=163840\text{ B}
\]

本地生成几何使用已有 `geometry_` 4096 B 区，不再额外分配一份。必须保持现有租约顺序：

1. 本地几何生成；
2. 读取索引、完成权重广播、完成邻域搬入；
3. 几何不再被消费后，才允许 `GridNeedsFma32` 把相应区当 mask 临时区。

pack 与 sample 是两个 kernel，其 UB **取阶段最大值，不相加**：

\[
U_{\text{a,explicit}}=\max(174080,163840)=174080\text{ B}
\]

**b** 的明确独立分配：

| 区域 | 字节 |
|---|---:|
| raw：\(8\times8\times64\) float | 16,384 |
| values：\(2\times8\times64\) float | 4,096 |
| weights | 2,048 |
| acc | 2,048 |
| geometry，gTile=64 | 4,096 |
| transpose 索引 | 2,048 |
| NCDHW staging：64×32 B | 2,048 |
| 两列 Gather 索引：128×uint32 | 512 |
| **合计** | **33,280** |

合法门禁为：

\[
U_{\text{explicit}}+U_{\text{SDK/API附加}}+U_{\text{必要预留}}
\le U_{\text{当前可分配}}
\]

目前没有核验等式右侧，不能承诺固定分配已合法。a 若不满足，应先缩 tile 并重新核算任务数、尾块、mask 租约；超出本计划参数和边界则回 C2。b 不因预算较小就跳过核验。

### 4. KEEP 判断与知识采用

两组均为 **P_CHANGE**：改变阶段边界、GM workspace、几何 owner 和最终输出通路。没有完整有效旧计划可引用，不能写 P_KEEP。未改变的 packing/数值代码是“保留部分实现”，不是整个计划 KEEP。

手工依据输入正文采用以下内容，未声称运行 router：

- **`planning.indexing.coordinate_neighborhood`**：完整绑定坐标、边界、邻域和 F 累加函数；因此不把几何相同误算成 x 输入相同，也不假定随机 grid 有局部输入窗口。
- **`planning.layout.transpose`**：要求比较整个通路，直接影响 a 保留 packing、b 删除全域转换的选择，而非只比较一个 Gather。
- **`planning.elementwise.continuous`**：仅借用输出互斥分区与边界原则；整个 GridSampler 不是同下标 elementwise，不冒充完整适用模板。
- **`implementation.memory-transfer.strided-pad`**：决定 b 的 8 B 有效行、131064 B GM 间隙和 32 B UB 行跨度，禁止把这些单位混用。
- **`implementation.buffer-lifetime.reuse`**：约束 geometry→mask、values→转置的真实最后消费者，不因词法作用域结束就覆盖。
- **`implementation.precision-boundaries.numeric/bounds`**：禁止改变 k 顺序、FMA 路径和有效 GM 范围。

没有使用 bank-padding、L2 hint 或深流水配方：缺少具体冲突/复用轨迹，且 b 只有一个 tile。不是因没有 profile 一概否决这些方向。

---

## 五、C3 准确实施步骤与返回条件

### 子例 a

1. 核对真实 Host、扩展 tiling 定义及四阶段 launch，建立源码身份；当前给出的旧头文件没有 `geometryLength`，不能直接据它编写最终 ABI。
2. 保留 pack kernel 和实际 packed 大小。
3. 将 `GridGeometryRange` 的单点生成体提取为保持原 float 中间边界的本地生成逻辑，填入 `geoWeight[k*gTile+p]`、`geoIndex[k*gTile+p]`。
4. 对 Brcb 会读取的补齐权重 lane 明确定义零；不无理由清零全部 tile。
5. 保持邻域 Copy、`GridNeedsFma32`、k 有序计算和转置代码。
6. sample 新增最终 y 地址参数，输出跨度改为 S；本例 `sa=S`，只改目的地址，不增加一次拷贝。
7. Host 改为 pack→sample，取消 geometry、Compact 的启动及对应算法 workspace 段。
8. 审查跨流水完成、末 tile、geometry mask 租约和直接输出互斥范围。

### 子例 b

1. 新实现固定本组 `batch=8`，使用一套 TPipe 和上表分配。
2. 本地生成八点几何和原顺序权重。
3. 初始化 dummy 通道所需值，构造两列 Gather 索引和 `[Cp,8]` 转置索引；索引仅含整数布局变换。
4. 对每点四组合法 x 邻居对，执行上述多块 DataCopyPad→完成边→Gather→完成边。
5. 规范 raw 为 `[p,k,c]`，同步修改所有消费偏移；不能残留原 paired `2*(k&3)+(k>>2)` 映射。
6. 保持现有数值判别与有序 Apply；不因本 workload 值域而删除软件路径。
7. 转置后一次写 2016 B 到最终输出，只写前 63 通道。
8. Host 在 b 组不启动原 geometry/pack/Compact，不分配这些算法 workspace；框架保留区单独处理。

上述方法会实际使用 strided-pad、局部 Gather、valid-length、数值边界及保守同步正文。**不使用 O_KEEP 表示“无需实现”**；未追加双缓冲、缓存策略、bank 调整。若最终 patch 改成多 owner、共享 geometry、跨核槽或新数值路径，必须返回 C2。

正式 C3 的后续门禁仍是：代码审查、目标 SDK 构建、原 oracle 完整正确性、存储/同步检查。通过后才有资格测整个调用序列；不能只计候选 sample 而遗漏父本 pack/geometry/Compact。

---

## 六、后继可复用摘要与待验证事项

### 当前状态

- 授权范围：一轮纸面优化及 C2/C3 交接；未授权本次实际编译、修改和硬件运行。
- 原四阶段父本保留；两个候选均未实现、未构建、未测。
- a 选择保留 paired packing，消除 geometry 与输出交接。
- b 选择单 owner 按需 NCDHW 取数，消除全输入 packing 和全部算法中间 workspace。
- 两组都保持原权重形成、k=0…7、dtype、异常值与 FMA 契约。

### 已比较路线

| 路线 | 静态判断 | 不能回答的问题 |
|---|---|---|
| a：本地几何＋直接输出 | 可删 \(632S\) B 交接请求；显式 UB 不新增 | 这些访问是否处于关键路径，融合后的 Scalar 调度成本 |
| a：直接 NCDHW | 可删 pack，但增加到 4S 次短行 Copy 和 Gather | 是否足以抵消全输入转换成本 |
| b：按需 NCDHW | 只消费约16 KB 输入，不再全域转换 | 32 次短行 Copy/Gather 的真实延迟与单核代价 |
| b：保留 pack 的融合方案 | 通路简单，保留一次性约25 MB转换读写 | 大块转换是否仍可能因硬件行为而有竞争力 |
| 单份 packing、通道并行 | 均有合法候选空间 | 新布局/任务成本与实际性能边界 |

### 必须补齐或验证

1. **实施安全**：实际 SDK 重载、可分配 UB、API 附加临时区、真实 tiling ABI、GM 别名合同、Host workspace 和 launch 顺序。
2. **地址检查**：至少手核两个相邻 tile、b 的两列索引、dummy 通道、最后输出字节及所有备用边界读取。
3. **数值检查**：正常值、抵消、次正规数、±0、极值、NaN/Inf，以及现有软件数值路径；禁止因 shape 特化偷换值域。
4. **完整覆盖**：两个选中元数据组、相邻 S 和 C 边界的 fallback、其他 dtype/模式原路径、重复调用。
5. **性能判别**：整个调用端到端、实际入口、逻辑请求与 HBM/L2 分开、各阶段时间和候选新增 Gather/同步成本。
6. 若 a 的新增本地几何控制拉长最长核，重开“保留 GM geometry、仅直接输出”；若 b 的按需重排成本意外占优，比较保留 pack 或通道对 owner，不能用未测计划提前宣布赢家。

这些记录足够让后继直接复用当前理解和成本模型；新增实测应形成后继证据，不回填本轮为“已通过”或“已加速”。