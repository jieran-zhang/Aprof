## 结论与交接状态

本轮选择如下，均为**纸面方案，未修改、未编译、未验证、未计时**：

- **子例 a，S=32768：保留全输入 packed 路径，采样结果直接写最终输出，删除 compact 阶段。**  
  本例 `sa=S`，compact 实际没有压缩 padding，只是在复制同布局数据。选择一个 `action.reduce_memory_traffic` 实例即可。
- **子例 b，S=8：改为单 owner 的按需邻域搬入、计算和最终写回；几何在本核产生并消费，不再全输入 pack，也不再产生 padded 输出。**  
  用 `action.reduce_memory_traffic` 表达消除全量物化，用 `action.fuse_kernel_chain` 表达几何生产消费边界的组合。两个实例有不同目标和合法性要求，不重复计算节省量。

没有根据缺计时统一否决试验；但实际可用 UB、目标 SDK 构建及完整正确性仍是实施验收条件。下述实例仅作任务内纸面登记：输入没有可校验的源码、模板 hash，也未运行 router，故不冒充已生成或通过正式 `action-decision/v3`、`handoff/v4` 产物。

---

# 一、共同理解：当前执行的不是原始逐输出 Scalar 路径

### 1. 数学与数值依赖

令输入空间长度：

\[
I=DHW=32768,\qquad C_p=\lceil C/16\rceil16=64.
\]

外部输出按 `[N,C,S]` 理解，空间维展平但不改变 NCDHW 外部契约。对每个空间点 \(p\)：

1. 按 `GridUnnormalize` 的原表达式得到三维坐标；
2. zeros padding 不改变坐标；
3. floor 得到低邻点和三个小数部分；
4. 以源码 k=0…7 的次序形成八个邻点及权重；
5. 每个通道读取自己的八个输入值，按规定次序累加。

几何与通道无关，输入值仍依赖通道。**共享几何不等于共享输入值。**

当前实际实现中，权重先计算为：

\[
w_k=\operatorname{float}(\operatorname{float}(w_xw_y)w_z),
\]

普通路径再按 k 顺序执行独立 `Mul`、`Add`；特殊大数路径使用 `GridFma32Bits`。原始算法 125–132 行的源码表达式不能直接拿来替换当前实现：权重结合位置、乘加是否融合都可能不同。本轮保持当前实际数值路径，不把它们视为实数意义下可任意重排。

对给定 `x∈[-1,1]`，`GridNeedsFma32` 的大数条件不触发；但不能据此把通用路径的特殊数值处理删掉。

### 2. 当前四阶段的数据流

依据实际类实现：

```text
grid
  → GeometryRange：GM 中 8 个 uint32 偏移平面 + 8 个 float 权重平面
x[N,C,I]
  → PackChannels：GM 中 [N,I+1,2,Cp] 配对布局
geometry + packed x
  → SampleChannels：GM 中 [N,C,sa] 输出
  → CompactOutput(small=false)：最终 [N,C,S]
```

其中：

\[
sa=\lceil S/16\rceil16.
\]

配对 packed 输入满足以下语义：

- 槽 0 保存当前位置的通道向量；
- 槽 1 保存该位置沿 z 加一平面的通道向量；
- 顶层和额外 sentinel 使用零。
- 内部点通过一次 `blockCount=2`、每块 `4Cp*sizeof(float)` 的搬运取回八邻居。

因此，内层不是每通道一次搬运。**已知 API 一次处理 Cp 通道，只能说明现有通道搬运已合批，不能再把 63 次通道调用合为一次作为收益。**

### 3. 可复算的当前资源与工作量

由 Init 公式推导：

- Pack：`p_=224`，空间 tile 数 `ceil(32768/224)=147`；
- Sample：初始 batch=64 超过源码预算，降至 **48**；
- `gTile=64`，显式 Sample UB 分配为 **163840 B**；
- Pack 显式 UB 分配为 **174080 B**；
- Compact 两块 8192 float buffer 合计 **65536 B**。

这些是所列显式分配，不是目标可用容量证明，也不含未给出的编译器或框架额外需求。

全输入 pack 每次调用都付出：

\[
B_{\rm pack,read}=4NCI=8,257,536\ {\rm B},
\]

\[
B_{\rm pack,write}=8N(I+1)C_p=16,777,728\ {\rm B}.
\]

合计 **25,035,264 B**？需要注意两项直接相加的准确值为：

\[
8,257,536+16,777,728=\boxed{25,035,264\ {\rm B}}.
\]

下文统一使用该值。它包含配对存储、零区及 sentinel 写入；不是 HBM 实测流量。

两例的主要数量如下：

| 项目 | a：S=32768 | b：S=8 |
|---|---:|---:|
| 有效输出元素 `CS` | 2,064,384 | 504 |
| 有效输出字节 `Y=4CS` | 8,257,536 | 2,016 |
| geometry 存储 `64S` | 2,097,152 B | 512 B |
| geometry 写入＋消费读取 | 4,194,304 B | 1,024 B |
| packed 邻域读取 `32CpS` | 67,108,864 B | 16,384 B |
| Sample 有效空间 tile 数 | 683，末 tile 32 点 | 1，8 点 |
| padded 输出分配 `4Csa` | 8,257,536 B | 4,032 B |

`GeometryRange` 的实际跨核划分和各阶段真实 BlockDim 未提供；不能从原始 Scalar tiling 推断当前所有启动参数。Sample 自身的轮转 tile 分配式则可直接从 1156–1158 行确认。

---

# 二、子例 a：保留 packed 输入，采样直接写最终 y

## A1. 关键事实与选择理由

本例：

\[
S=32768,\qquad sa=S.
\]

所以 Sample 已写出的 `[N,C,sa]` 与最终 `[N,C,S]` **布局、行跨度、有效长度完全一致**。`GridCompactOutput` 在这里不是必要的布局转换，而是再读一次、再写一次全部有效输出，并执行一次 UB→UB copy。

这一事实支持消除具体往返，不需要先证明带宽饱和。对应临时机制为：

> 跨阶段的等布局输出物化与复制，不是单 kernel 内已有合法片上边界的中间往返。

因此不套用范围较窄的 `keep_intermediate_onchip`。

## A2. 主方案的完整工作变化

新序列：

```text
GeometryRange → PackChannels → SampleChannelsDirectOutput
```

Sample 保持：

- packed 输入布局、八邻居搬入方式；
- batch=48、空间任务顺序、每 tile 所有通道的 owner；
- 权重广播、特殊数值检测；
- k=0…7 运算顺序；
- UB 转置和有效写回参数。

只将输出 GlobalTensor 绑定到最终 y，并删除 compact 启动及其工作区。

确定减少：

\[
2Y=\boxed{16,515,072\ {\rm B}}
\]

的逻辑 GM 读写；同时删除 compact 的同量级 UB→UB 复制和一次启动。这里的 GM 节省是“一次中间写入改为最终写入，再删除 compact 读写”的净结果，不能额外再计一份 Sample 写输出收益。

保留的主要工作：

- 全输入 pack 的 25,035,264 B；
- geometry 的 4,194,304 B 写读；
- Sample 的 67,108,864 B packed 邻域读取；
- 所有插值算术、检测、转置和 Sample 内同步。

新增代价：

- Host 输出指针、workspace 公式和 entry 接线变更；
- 特化域与 fallback 的维护和边界验证；
- 不新增数据 buffer，不延长当前 Sample UB 生命周期。

## A3. 最有竞争力替代：取消全量 pack，直接读取 NCDHW 邻域

可以按每点四条 x 相邻二元素行，跨 63 个通道使用规则 strided 搬运。它能删除整个 pack 阶段，并只读取真实通道：

\[
B_{\rm direct,input}=8CS\cdot4=66,060,288\ {\rm B}.
\]

与现有 packed 邻域读取相比再少 1,048,576 B 有效 payload；并可配合直接输出。相对主方案，还可删除 pack 的 25,035,264 B。

但完整代价也明显不同：

- 内部点 CopyIn API 从 **S 次变成 4S 次**：  
  32768 → 131072 次；
- 每次有 63 个有效长度 8 B 的通道块，UB 每块占 32 B；原始邻域暂存约为有效输入 payload 的四倍；
- 需要 Gather 索引、补齐区定义及输出空间微块重组；
- 不能把所有空间点的源地址当作规则连续行；
- 若直接写输出与未来原输入读取存在别名，必须另证安全或保留暂存；
- 未知缓存和事务行为，不能从有效 payload 更少直接推断更快。

**本轮 a 选择保留 packed。** 它为大量采样点摊销准备成本，并把每点八邻域组织成一次搬运；主方案先删掉确定没有布局价值的完整输出往返，不增加采样热循环的发射和 Gather 工作。直接 NCDHW 路线仍是有竞争力的后继试验，不因缺测量而被判不可行。

另一个较小替代是将 geometry 融入 Sample，可再删 4 MiB 左右的几何写读和一次启动。但它改变原先“全 grid 先消费完，再产生输出”的边界；若 y 与 grid 重叠，原顺序与新顺序不自动等价。当前没有完整别名合同，不把它夹带进本方案。

## A4. Action 实例

**A-a：`action.reduce_memory_traffic`**

- target：当前 padded 输出 tensor；
- stage：`GridSampleChannels<float>` → `GridCompactOutput<float>(small=false)`；
- workload：已列 a 元数据；
- implementation：本输入实际四阶段父本；
- 变换：Sample 直接写最终 y，删除同布局 compact。
- `traffic_reducible`：由 `sa=S` 和输出地址映射证明；
- semantic：计算和有效写回集合不变；
- capacity：不新增 UB；GM 段减少，目标实际容量仍待核验；
- 不注册 `batch_writeback`：Sample 已用一次多块调用写通道行，本方案不是将多个小写回汇总。

---

# 三、子例 b：单 owner 按需读取并完成整条链

## B1. 为什么不沿用 a 的主要路线

本例仅有 504 个输出，仍先读取全部 8 MiB 左右输入并写出约 16 MiB packed 副本。一次调用、不跨调用复用，也没有预先 packed 副本，故这些准备工作不能摊到未来调用。

只删除 compact 可净省：

\[
2Y=4032\ {\rm B},
\]

却保留 25,035,264 B 的全输入 pack。静态工作量已足以支持比较按需路径，不需要先测出 pack 的时间占比。

当前 Sample 只有一个有效空间 tile。增加启动核数不能改变这一事实；也不能据“有空核可能性”直接选择多核重分。对如此短的输出，新增 owner 和调度本身需要付费。

## B2. 主方案及准确数据组织

新路径用一个 AIV owner：

1. 读取全部 8 个 grid 点；
2. 按原几何表达式生成八邻居及权重；
3. 只搬入这些邻居的 63 通道输入；
4. 形成全部 504 个输出；
5. 最后一次写回最终 y。

不保留全量 packed 输入、GM geometry 或 padded 输出。

对内部点，将八邻居按四条 x 相邻二元素行搬入。每条行跨全部通道：

```text
blockCount = 63
blockLen   = 2*sizeof(float) = 8 B
srcStride  = (I-2)*sizeof(float) = 131064 B
dstStride  = 0
```

源通道起点差为：

\[
8+131064=131072=4I\ {\rm B},
\]

恰为 NCDHW 一个通道平面的字节跨度。四条行分别对应 `(z0,y0)`、`(z0,y1)`、`(z1,y0)`、`(z1,y1)`。

UB 原始布局取：

```text
raw[p][row=0..3][c=0..62][lane=0..7]
```

每通道行 8 个 float 的物理跨度，只有 lane 0、1 是本次搬入的有效值。邻居 k 的地址为：

\[
{\rm rawByte}(k,c,p)=
\big((4p+\lfloor k/2\rfloor)63+c\big)32+4(k\bmod2).
\]

Gather 后使用输出连续顺序：

\[
q=8c+p,\quad 0\le q<504.
\]

这使最终 accumulator 已是紧凑 `[C,S]`，不需要输出转置和 compact。

严格内部是本次输入事实，不能据此把边界语义永久删掉。实际实现应在形成 DMA 前检查两元素行的合法性；边界备用路径逐个合法读取、越界写零，保持原邻域映射。本次 b 不执行备用搬运。其余未列元数据全部走原 fallback。

## B3. 工作变化和代价

主方案有效逻辑 GM 数据量：

\[
B_{\rm grid}=3S\cdot4=96\ {\rm B},
\]

\[
B_{\rm x}=8CS\cdot4=16,128\ {\rm B},
\]

\[
B_{\rm y}=CS\cdot4=2,016\ {\rm B}.
\]

合计：

\[
\boxed{18,240\ {\rm B}}
\]

——不含缓存事务、实现元数据和框架成本，不是 HBM 测量。

原四阶段按相同口径为：

\[
96+1024+25,035,264+16,384+3(2016)
=\boxed{25,058,816\ {\rm B}}.
\]

因此静态逻辑请求净减少 **25,040,576 B**。主要来源是删除全输入准备；geometry、输出往返的删除量各只计一次。

保留：

- 8 次空间几何生成；
- 4032 次有效邻域消费；
- 每输出 k=0…7 的规定顺序；
- 当前普通 `Mul`/`Add` 与软件分支的选择语义。

新增或增加：

- 邻域输入 CopyIn 从 8 次变为 **32 次**；
- 每通道 8 B 小块的 UB 对齐开销；
- Gather 和索引表构造；
- 权重按 `[c,p]` 映射展开；
- 对消费者实际读取的 dummy 区域进行初始化；
- 全部输出由一个 owner 完成，未暴露通道并行。

这些成本不能省略；本轮选择理由是它们作用于 8 个点，而原 pack 固定作用于 32768 个源空间位置。

## B4. 最有竞争力替代：保留独立 GeometryRange，按需采样直接输出

替代序列为：

```text
GeometryRange → DirectNCDHWSampleAndOutput
```

它也删除全量 pack 和 compact，沿用相同邻域搬入及数值计算，GM 流量只比主方案多：

\[
2(64S)=1024\ {\rm B},
\]

并多一次启动。

竞争优势：

- 直接沿用现有 GM geometry 生产实现；
- 不必改写几何写入位置；
- 便于独立核对几何记录。

主方案的融合新增成本：

- 将 geometry 的存储接口改为 UB，显式保留 float 物化边界；
- 几何区在权重展开和邻域地址生成结束前不能复用；
- 需要审查整条链的完成顺序，而不是只看两个局部 kernel。

本例全部几何、输入和输出都能由同一 owner 顺序完成；只要在最终输出前读完全部输入和 grid，就不需要新增跨核可见性协议，也不会因最终 y 写回破坏未来输入读取。故本轮选择融合版，替代版作为最直接的安全回退。

## B5. Action 实例与依赖

**A-b1：`action.reduce_memory_traffic`**

- target：全输入 packed tensor、padded 输出 tensor；
- stage：Pack → Sample → Compact；
- workload：已列 b 元数据；
- 变换：消费者按原 NCDHW 地址按需读取，直接产生紧凑输出；
- 证明对象：被删除的 packed 值逐个映射回相同原输入；最终输出全部保留；
- 不是“输入驻留”：没有依赖真实重复原值读取，也不假定 8 个点邻域互相重叠。

**A-b2：`action.fuse_kernel_chain`**

- target：geometry 生产消费边；
- stage：GeometryRange → 按需采样；
- 变换：几何在同 owner UB 内产生并消费，删除 GM geometry 和独立启动；
- 依赖 A-b1 的新单 owner 消费布局；
- fusion boundary：所有 8 点几何和输入读取完成后，才允许最终输出；
- 容量按以下共同集合核算，不能分别证明两个实例后直接合并。

不使用 `hoist_invariant_control` 承载几何生成，也不使用 `reuse_input_tiles` 承载派生权重。

---

# 四、统一 C2 共同计划

## 1. 所有权、布局、workspace 与同步

| 项目 | a | b |
|---|---|---|
| 输出 owner | 保留每个 48 点空间 tile 拥有全部 63 通道 | 一个 owner 拥有全部 504 个输出 |
| 输入布局 | 外部 NCDHW；内部配对 packed 不变 | 直接 NCDHW，四条二元素行跨通道搬入 |
| 输出布局 | 直接 `[N,C,S]`，`sa=S` | accumulator 直接 `[C,8]` |
| 跨核归约 | 无 | 无 |
| 阶段边界 | Geometry、Pack 完成后 Sample；沿用调用顺序 | 单核内完成几何、输入、计算、最终写回 |
| 新数据 workspace | packed＋geometry | 0，框架保留区另计 |

a 的算法 workspace：

\[
W_a=8N(I+1)C_p+64NS
=16,777,728+2,097,152
=\boxed{18,874,880\ {\rm B}}.
\]

原输出 workspace 8,257,536 B 删除。不要把 allocator 的保留区也随之删掉。

b 原算法 workspace：

\[
16,777,728+512+4032
=\boxed{16,782,272\ {\rm B}},
\]

新算法数据 workspace 为零。

### b 的保守 UB 分配账

取 512 个输出槽位覆盖有效 504 个元素：

| 物理区域 | 字节 |
|---|---:|
| raw：`8×4×63×32` | 64,512 |
| 八组 Gather byte offset：`8×512×4` | 16,384 |
| Gather values | 2,048 |
| accumulator | 2,048 |
| 八组展开权重 | 16,384 |
| geometry／后续检测 mask 共用区 | 2,048 |
| 检测 temp | 512 |
| **显式总量** | **103,936** |

geometry 的有效记录共 512 B，先存于该 2048 B 区。只有在所有输入地址已消费、权重已展开后，才可把这块区域租给 `GridNeedsFma32`。索引、权重、raw、acc 不与该区非法重叠。

raw 的消费者包括全范围数值检测，因此不能只定义 DMA 写入的两条 lane：保守实现先把整个 raw 清零，再搬入有效值。额外初始化量 **64,512 B** 已计为新增本地工作。

容量准入：

\[
U_{\rm explicit}+U_{\rm implicit/reserved}\le U_{\rm available}.
\]

a 不增加原 Sample 的显式 163840 B；b 为 103936 B。源码中的预算常数不替代目标可用 UB 查询，不能在本轮把 `capacity=true` 伪装成设备实测。

### 同步闭环

两例均保留：

- MTE2 写输入完成 → Vector/Gather/检测读输入；
- Scalar 写 UB 几何、索引完成 → Vector 读；
- Mul 完成 → 对应 Add；
- 最后一个 k 的 Add 完成 → 输出读取；
- MTE3 读完输出 → buffer 可覆盖或 kernel 结束。

b 的 geometry→检测 scratch 复用另需最后消费者完成边。先用可审查的保守完成边，不在同轮顺手删屏障或增加双缓冲。核内 `PIPE_ALL` 不替代 a 的跨 kernel 阶段完成关系。

## 2. 分派与 KEEP 判断

冻结两个精确元数据子域：

- FP32、`N=1,C=63,D=H=W=32`、bilinear、zeros、alignCorners=false、S=32768；
- 同上，S=8。

其余元数据保持原通用序列。分派不依赖 case 名、计时结果或输入数值范围；边界和特殊数值路径不能仅凭 shape 被删掉。

由于缺少完整 Host 和现有 key 命名空间，本轮不虚构数值 key 或声称已接线。正式 C2 应给出无冲突 uint64 key 和真实 entry 后交 C3。

两例均为 **P_CHANGE**：

- a 改变最终输出的生产阶段和 workspace 所有权；
- b 改变任务、输入通路、融合边界和 workspace。

不能称 P_KEEP。没有已确认、覆盖这些变更的父计划；也不能将缺少模板命中解释成 KEEP。

---

# 五、C3 精确落地步骤与 P/O 正文的实际影响

## 子例 a

1. 为精确元数据域接入 direct-output 版本；fallback 不变。
2. `GridSampleChannels::Init` 接收最终 y，替换 1147 行的输出 GlobalTensor 绑定。
3. 保持 `sa=S`，不改 1174–1178 行转置与有效写回映射。
4. 删除该域 compact 启动；Host workspace 去掉输出段，同步修改所有偏移引用。
5. 保留 geometry、pack、Sample 的数值和同步代码。

采用知识的实际影响：

- `planning.layout.transpose`：要求比较消费者是否可直接接受现布局；这里两布局完全相同，因而不新增转置。
- `memory-transfer.strided-pad`：确认 UB→GM 的 `srcStride` 是 32 B 块、`dstStride` 是 GM 字节间隙；不能把它们交换。
- `precision-boundaries.bounds`：最终只写有效输出，不因对齐扩大 y。
- 不采用 `batch_writeback` 或 coalesce 作为主变换，避免把已有多块输出调用重复算作优化。

## 子例 b

1. 新建单 owner entry，初始化上述独立物理区。
2. 将 `GridGeometryRange` 的每点数学原样迁移到本核记录写入；坐标、floor、偏移、权重表达式和 float 物化边界不变。
3. 构造 Gather 映射和八组权重；补齐槽使用已定义安全值。
4. 清零 raw，按四条规则行搬入每点邻域；先判有效域再形成地址。
5. 等输入、索引和权重就绪后，沿用 `GridNeedsFma32` 判别思想。检测只增加零 dummy，不擅自换成新的非有限值分类规则。
6. k=0…7：
   - Gather 对应邻居为 `[c,p]`；
   - 普通分支分别 Mul、Add；
   - 软件分支对每个有效输出调用原 `GridFma32Bits` 更新；
   - 不改树形归约，不替换为硬件 FMA。
7. 所有 504 个值完成后，以有效 **2016 B** 一次写出；等待 MTE3 完成。
8. 删除该域原 Geometry、Pack、Sample、Compact 的四阶段启动，接到一个真实 entry；不运行旧序列后再挑结果。

采用知识的实际影响：

- `planning.indexing.coordinate_neighborhood`：绑定本任务 G/B/H/F、真实 NCDHW stride 和 k 顺序；选择按需邻域，不假定空间窗口局部性。
- `planning.layout.transpose`：促使比较全量转换与消费者直接寻址，完整计入取消 pack 后的小块/Gather 代价。
- `memory-transfer.strided-pad`：给出 63 行、8 B 有效长、131064 B 间隙的合法表达；任意 grid 点之间不强行合并。
- `buffer-lifetime.reuse`：只复用已结束的 geometry scratch；不把生命周期下界冒充实际分配量。
- `vector-api.batch`：有效 count 与物理 512 槽分离；k 间存在累加依赖，不能直接合批成无序求和。
- `fusion-composition.vector_chain_residency` 仅采用本地生产消费和最后消费者原则，不宣称该逐元素链模板完整覆盖任意插值。
- 不使用 Compare/Select 新数值替换，因此不引入 Select 的 8 KiB scratch，也不借 Max/Min 改特殊值语义。

---

# 六、后继可复用摘要与待验证事项

### 当前状态

- 授权仅一轮纸面分析与 C2/C3 交接；未配置额外试验轮次。
- 当前保留实现仍是输入给出的四阶段父本。
- a：选择直接输出，预计消除 `2Y=16,515,072 B` 逻辑 GM 往返。
- b：选择单 owner 按需融合，预计删除全输入物化，算法 GM 请求模型为 18,240 B。
- 构建、完整正确性、运行检查、性能均为 **not_measured／未执行**；没有 production 晋升结论。

### 已分析路线

| 路线 | 结构结论 | 后继改变选择的条件 |
|---|---|---|
| a 保留 packed、直接输出 | `sa=S`，删除 compact 有明确等布局依据 | 实际接线或输出别名合同与所见源码不符时重审 |
| a 直接 NCDHW | 少全量准备，但输入发射约增四倍，并增加 Gather/UB padding | 若 packed 准备或实际外部流量主导，值得正式比较 |
| b 按需融合 | 只处理 8 点，准备量不再随全部 I 增长 | 若 Gather／Scalar 表构造成本异常高，比较更简单按需 Scalar 或两阶段版本 |
| b 独立 geometry＋按需采样 | 与主方案仅差 1024 B 几何往返及一次启动 | 几何迁移数值或融合合法性未闭合时优先回退 |

### 实施前必须补齐

1. 完整 Host、实际 tiling ABI、workspace 保留区和 entry/key 接线。
2. 目标 SDK 对实际 Gather、DataCopyPad、检测调用及位置的支持，真实可用 UB 和隐含预留。
3. 输出／输入别名合同；a 若继续融合 geometry，必须专门处理 grid 的读取窗口。
4. 源码和模板冻结身份；不能补造本轮未生成的 hash。

### 获准硬件验证时的判别项

- 完整 oracle：八邻居顺序、权重舍入、±0、次正规数、极值、NaN/Inf 合同及边界备用路径；
- a 的空间尾 tile、b 的 504/512 有效域、所有 fallback 和分派相邻边界；
- 实际启动序列、workspace 最大地址、UB 分配及 scratch 最后消费者；
- 统一端到端范围比较全部阶段，分别记录逻辑请求、HBM/L2 和时间，不能混算；
- 若整体无收益，先检查预期工作是否真正删除及新增调用、初始化、Gather 成本，不把未测或无效计时当作机制反证。