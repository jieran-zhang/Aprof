## 结论与交接状态

本轮选择两个**不同成本结构下的纸面候选**，均从题给当前实现出发：

- **子例 a：保留现有 paired 通道打包和采样，只让采样结果直接写最终 NCS 输出，跳过 Compact。**
- **子例 b：保留全域几何表，取消全输入打包；直接从 NCDHW 按通道批量读取邻域，在 UB 重排后沿用现有加权计算，最终由一个 owner 连续写输出，跳过 Compact。**

这不是按 Action 数量拼方案。a 的首选减少一段无须重新组织输入访问的输出中转；b 的首选针对“每次调用准备整个输入，却只消费 8 个空间点”的结构差异。

**状态：`conditional_plan / not_measured`。** 本文没有执行工具、修改源码、编译、运行或校验正式契约。下面的实例名、计划名是本轮纸面身份，不是已经登记的机器产物；不虚构源码/template hash。实际 Host、当前完整 tiling 结构、SDK 版本及可用 UB 尚未给出，须在进入 C3 实施前补齐对应接线与容量条件。

---

# 一、当前实现：两子例共用的理解基础

## 1. 实际路径，而不是原始逐输出算法

按用户指定的当前入口，执行顺序为：

```text
grid
  → GridGeometryRange：全 N×S 几何记录，GM
x[N,C,I]
  → GridPackChannels<float>：全输入 paired packed 副本，GM
几何表 + packed 输入
  → GridSampleChannels<float>：padded NCS 输出，GM
  → GridCompactOutput<float>(small=false)
  → 最终紧凑 NCS 输出
```

其中 \(I=DHW=32768\)，\(C=63\)，\(cp=64\)。

原始 `GridSampler3DOne` 每输出重新计算几何；**当前路径已经把几何生成降到每个 \((n,p)\) 一次**，不能再把“省去 C 倍几何计算”当作本轮收益。

题目给出了阶段次序，但没有完整 Host launch 源码。因此下文明确计算阶段和搬运变化，**不把四个阶段直接等同为已经核验的四次独立 launch**。

## 2. 数学与数值依赖

对每点 \(p\)，先保持源码中的反归一化：

\[
i_x=((g_x+1)W-1)\times 0.5
\]

其余两轴同理。随后生成 floor 坐标、8 个邻域偏移以及

\[
w_k=\operatorname{float}(\operatorname{float}(w_xw_y)w_z).
\]

- 几何 \(D[n,p]\) 依赖 grid、空间尺寸、padding、alignCorners、插值模式，**不依赖通道 c**。
- 输入值 \(X[n,c,i_k]\) 仍依赖 c；几何复用不是输入原值复用。
- 当前普通采样路径对已生成权重执行 `Mul`，再按 **k=0…7** 顺序 `Add`。
- `GridNeedsFma32` 对一个采样 tile 的邻域原值做 any 检查；一旦命中，影响的是**整个 tile 的软件计算路径**，不是只处理命中元素。
- 当前 x 在 \([-1,1]\)，通道补零也为零，故本 workload 不命中 \(\pm2^{124}\) 阈值。扫描仍实际执行，不能把“没有软件计算”写成“没有保护成本”。

本轮不改权重形成、Mul/Add/FMA 组织、k 顺序、输出 dtype 或特殊值处理。也不宣称当前加权组织与原始连续三个乘法表达式逐位等价；候选首先保持**当前实际计算路径**，最终仍须由原 oracle 验证。

## 3. paired packed 的实际含义

由 `GridPackChannels:1126–1135` 推导，以 float 元素计：

\[
P[n,i,0,c]=X[n,c,i],
\]

\[
P[n,i,1,c]=
\begin{cases}
X[n,c,i+HW],&i<I-HW\\
0,&\text{否则}.
\end{cases}
\]

c=63 为零，i=I 为零哨兵。其物理顺序为 `[n,I+1,2,cp]`。

这样，内部点的 x 相邻位置及 z 配对值可被采样器用**一次 API、两个 descriptor block**取回全部 8 邻居：

- 每 block 长 \(4cp\times4=1024\) B；
- 两个 block 对应两个 y 行；
- 源行间间隔为 \((W-2)2cp\times4=15360\) B；
- raw 中邻居槽为 `slot(k)=2*(k&3)+(k>>2)`。

因此，**内层已一次处理 cp 通道**。再提“把 63 次通道搬运合成一次”不符合当前源码。

## 4. 可复算的现状成本

以下均为**源码逻辑请求/分配字节**，不是 HBM 流量或时间。

| 项目 | 公式 | a：S=32768 | b：S=8 |
|---|---:|---:|---:|
| 源输入有效大小 | \(4CI\) | 8,257,536 B | 同左 |
| paired packed 区 | \(8(I+1)cp\) | 16,777,728 B | 同左 |
| 几何表，8偏移+8权重 | \(64S\) | 2,097,152 B | 512 B |
| 采样邻域读取 | \(8Scp\times4\) | 67,108,864 B | 16,384 B |
| 最终输出 | \(4CS=252S\) | 8,257,536 B | 2,016 B |
| padded 输出分配 | \(4C\,AlignUp(S,16)\) | 8,257,536 B | 4,032 B |
| Compact 有效读+写 | \(8CS=504S\) | 16,515,072 B | 4,032 B |

注意 b 的 padded 输出有空洞，但采样和 Compact 不因此读写整个 4,032 B 区两遍；有效访问仍按 2,016 B 计。

当前参数也能直接推导：

- Pack：`p_=224`，`pitch_=928B`，显式 UB 分配  
  \(59392+57344+57344=174080\) B；输入空间 tile 数为 147。
- Sample：初始 batch=64 不满足源码预算，减至 **48**；显式 UB 为 **163,840 B**。
  - a：683 个空间 tile，最后 count=32。
  - b：只有一个 count=8 的有效 tile，但仍申请 batch=48 的整套区。

源码中的 `188160B` 是现有预算常量，**不是本轮核验的目标可用 UB**。

---

# 二、子例 a：保留 paired 输入，直接写最终输出

## A1. 主要方案与选择理由

纸面方案名：`scheme.a.direct-final-output`。

a 中：

\[
sa=AlignUp(32768,16)=32768=S.
\]

因此 padded NCS 与最终 NCS **物理布局完全相同**。`GridSampleChannels:1174–1178` 已经把 `[p,cp]` 累加结果 Gather 为 `[c,batch]`，并只写 C 个有效通道；无需再把同一数据从 workspace 复制到 y。

方案仅改输出目的地：

```text
Geometry → Pack → Sample直接写y
                         × 不执行Compact
```

它减少的是已有 Compact 的有效读写，不是假设能消除整个采样阶段。没有新增全输入转换、算术、索引表或缓冲。

### 全部工作变化

- 保留：
  - 全域 geometry 生成及其 GM 写读；
  - 全输入 paired packing、哨兵和通道补零；
  - 每点一次内部邻域搬入、两个 block；
  - 范围扫描、普通/软件数值分支；
  - 现有 transpose Gather、8 次有序累加及有效输出写回。
- 删除：
  - Compact 对全部 \(CS\) 元素的一读一写：**16,515,072 B**；
  - Compact 的 UB→UB 拷贝和逐段控制；
  - padded 输出 workspace 段：**8,257,536 B**。
- 新增：
  - 采样器接收最终 `yAddr` 的参数/入口接线；
  - Host 元数据选择及跳过 Compact 的控制；
  - 不增加采样器显式 UB。

若把所有给定阶段的有效 GM 请求相加，原路径为：

\[
25,035,264+2944S=121,504,256\text{ B}.
\]

候选为 **104,989,184 B**。该差值只表示逻辑请求减少，不表示同比时延下降。

## A2. 最有竞争力替代：普通单份 packed + 直接输出

替代方案将输入布局改为 `[n,I+1,cp]`，不再保存 z 配对副本，仍直接写 y。

**减少：**

- packed 写入和容量由 16,777,728 B 降至 8,388,864 B；
- 相比主方案再省 **8,388,864 B** 准备写流量及同量 workspace。

**保留/新增：**

- 源输入仍完整读一遍，仍需通道转置、补零和哨兵；
- 每个输出点分两个 z 层取数：每层一次两行 descriptor，blockLen 为 \(2cp\times4=512\) B；
- 内部邻域 API 从 \(S\) 次增至 \(2S\) 次，descriptor block 从 \(2S\) 增至 \(4S\)；
- 对 a 即多 **32,768 次 API**和 **65,536 个 descriptor block**；
- raw 邻域映射、workspace 偏移和边界路径都须重写，必要邻域读取字节并不减少。

**为何本轮先选主方案：**主方案消除 16.5 MB 输出中转，而不增加采样内层发射、不改输入布局。替代方案有明确试验价值，但其额外 8.39 MB 准备节省必须偿还 32,768 次额外邻域 API 及新布局控制。当前无延迟数据，不能认定哪一边净胜；本轮优先选择不带该交换代价的完整消除项，而不是断言 paired 是最优。

另外，完全直接读 NCDHW 可进一步免掉全输入准备，但内部点通常需要每点 4 个跨通道 descriptor，每个含 63 个 8B block：a 为 **131,072 次 API、8,257,536 个 block**，而当前为 32,768 次 API、65,536 个 block。这解释了为何不能仅凭“packed 多一份”就统一取消 a 的打包。

## A3. Action 实例

采用已给注册意图：

**`A-a-output = action.reduce_memory_traffic`**

- parent：题给当前 `GridSampleChannels<float> → GridCompactOutput<float>`。
- target：padded NCS 中间输出及其 Compact 读回。
- stage：Sample CopyOut 到最终输出。
- workload：题给 FP32、N=1、C=63、D=H=W=32、S=32768、bilinear/zeros/alignCorners=false。
- `traffic_reducible`：由 \(sa=S\) 和相同 NCS 地址映射证明。
- 语义：只改变目标 GM 地址，不改变任何计算结果位模式。
- 容量：不新增 Sample UB；实际目标容量仍待核验。

不额外挂 `batch_writeback`：采样写回的批量和调用数并未改变。也不挂 `reuse_derived_results`：几何早已生成一次并共享。

## A4. C2 共同计划

计划名：`plan.a.direct-final-output`，**P_CHANGE**。

- **输出 owner**：保留现有空间 tile owner。tile 拥有全部 C 通道的 `[point,point+count)`。
- **布局**：最终偏移为 `n*C*S+c*S+point`，与旧 `n*C*sa+c*sa+point` 相同。
- **物理边界**：point 为 48 的倍数，即 16 元素的倍数；所有通道行跨度、tile 起点和有效写长均为 64B 倍数，末块 count=32。
- **workspace**：
  \[
  W_a=8N(I+1)cp+64NS
  =18,874,880\text{ B},
  \]
  不含框架保留区及段间实际对齐。原链所需三段合计为 27,132,416 B。
- **同步**：保留 geometry→sample、pack→sample 的阶段完成依赖；保留 Sample 核内全部已有完成边。删除的仅是 Compact 及其读者，不在本轮顺便缩窄屏障。
- **容量**：Sample 显式 163,840 B、Pack 显式 174,080 B 分阶段核算，不能相加为同核同时存活 UB；各自仍须满足目标实际可用容量。
- **KEEP 依据**：没有可引用的完整父计划，不能正式标 P_KEEP；且输出通路和 workspace 所有权确实变化。未变的任务划分是“提取已有计划”，不记为并行优化。

## A5. C3 准确步骤及正文影响

1. 增加明确的最终输出参数，不能继续依赖 `work+packedSize` 隐式定位 y。
2. 在已冻结的 a 元数据域使用 `S` 作为 GM 通道跨度；保留原 Gather 和 `DataCopyPad` 参数的有效长度。
3. Host 对该域不再安排 Compact；workspace 分配与 kernel 偏移同步删去输出段。
4. 其他元数据仍走原链，不把 `sa==S` 单独扩张成全算子新资格。
5. 保留原输入、几何、保护分支和算术代码。

纸面 P/O 选择：

- P：`planning.indexing.coordinate_neighborhood`，绑定源码 G/B/H/F；不是把采样冒充同形 elementwise。
- P：`planning.layout.transpose` 的“转换仅服务消费者时检查能否直接消费”原则，支持确认旧输出已是最终布局，**不新增转置**。
- O：`memory-transfer/strided-pad`、`tiling-tail/valid-length`，决定有效 blockLen、双端 stride 单位及只写 C 通道。
- O：`precision-boundaries/numeric`，明确禁止顺便改权重或累加组织。

这里没有正式 router 运行或已生成 patch；这些是正文支持的实施选择。

---

# 三、子例 b：不打包全输入，直接读取 NCDHW 邻域

## B1. 主要方案

纸面方案名：`scheme.b.direct-source-and-final-output`。

```text
GridGeometryRange全域
        ↓
直接读取原始NCDHW邻域 → UB重排 → 原加权路径 → 连续写最终y
        × 全输入Pack
        × Compact
```

保留几何 GM 表，是为了不把取消全输入准备与几何融合混成一个必须同时成立的大方案。其总写读仅 1,024 B；本轮主要变化不是这部分。

### 直接读取如何批量表达

对一个内部点，8 邻居可按四个 `(z,y)` 行组织，每行含相邻两个 x 值。对每个行对，使用：

```text
blockCount = 63
blockLen   = 2*sizeof(float) = 8B
srcStride  = (I-2)*sizeof(float) = 131064B
dstStride  = 0
```

源地址为：

\[
X[cI+i_{\text{pair}}],\quad c=0,\ldots,62.
\]

一次 API 搬入所有有效通道，但它是 **63 个跨 stride 的 8B block**，不是一段连续 cp 通道。

A3 普通 GM→UB DataCopyPad 每块按 32B 对齐，形成：

```text
staging[p, r=0..3, c=0..63, lane=0..7]
```

实际只消费每行 lane 0、1。c=63 的对应行显式置零。随后用整数 Gather 偏移表重排成现有 raw 所要求的 `[p,slot(k),cp]`：

\[
\text{srcIndex}
=\big((p\cdot4+\lfloor k/2\rfloor)cp+c\big)\cdot8+(k\bmod2).
\]

目的槽仍为 `slot(k)=2*(k&3)+(k>>2)`，因此后续 Apply 和软件分支可保持原邻居映射。

### 数据相关安全路径

“grid 严格内部”是本 workload 的已知事实，**不是 Host 可由 shape 推出的条件**。

同一元数据分支必须保留非内部点处理：若不能组成合法 x 相邻对，则逐 k、逐有效 c，先检查几何偏移是否为哨兵，再用当前支持的标量读取方式填充 raw；无效邻居填零，dummy 通道也填零。之后仍进入相同的范围扫描和加权路径。

该备用路径不在题给 b 中触发；其工作上界为每受影响点 \(8C\) 次标量源读取，不能宣称它高效，也不能先越界读再乘零。

## B2. 全部工作变化与收支

### 删除

每次调用删除：

- 源输入全量准备读取：**8,257,536 B**；
- paired packed 全量写入：**16,777,728 B**；
- Pack 的通道转置、索引生成、初始化、147 个输入空间 tile 的控制；
- packed workspace：**16,777,728 B**；
- Compact 有效读写：**4,032 B**；
- padded 输出 workspace：**4,032 B**。

### 保留

- 8 点 geometry：grid 读 96 B、geometry 写 512 B、Sample 读 512 B；
- 每通道每点 8 项有序加权；
- `GridNeedsFma32` 和软件保护实现；
- 最终输出 2,016 B。

### 新增或改变

- 邻域 API：原来 \(S=8\) 次，变为 \(4S=32\) 次；
- descriptor block：原来 16 个，变为 \(4SC=2016\) 个；
- 有效邻域读取从 16,384 B 降为 **16,128 B**，仅省 dummy 通道；
- 新增 padded staging 的 UB 写入、一次 raw Gather、Gather 偏移表构造及对应完成边；
- 一次连续最终输出 DMA，替代原按通道 padded 写回再压紧；
- Sample 的参数化 batch 从 48 改为 8，不能把减少的无效初始化误算为减少必要数学工作。

原路径有效逻辑 GM 请求为 **25,058,816 B**；候选为：

\[
96+512+512+16128+2016=\boxed{19,264\text{ B}}.
\]

**为何 b 值得选直接源路径：**32 次小而规则的跨通道 API 需要支付额外 block/setup 和 UB 重排，但其竞争对象是每次完整调用都要做的约 25 MB 全输入准备，而非一个已经存在、可免费复用的 packed 副本。S=8 没有跨调用摊销，故本轮优先取消准备。这里仍没有把字节差换算成时间。

## B3. 最有竞争力替代：单份 packed + 直接输出

该替代比当前 paired 更节省，但仍需：

- 全输入读 8,257,536 B；
- 单份 packed 写 8,388,864 B；
- Sample 约 16 次 API、32 个 block；
- 全输入 Pack 的转置和初始化；
- packed workspace 8,388,864 B。

它比主方案少约 16 次邻域 API，descriptor block 也少得多，却仍需每调用约 **16.65 MB** 全输入准备。b 的 8 点消费不足以在静态工作模型中为这笔准备提供有力摊销依据。因此不作为首选。

若后续出现如下事实，替代才应重开：直接 NCDHW 的大量 8B block 导致异常高的目标延迟，或存在本题明确排除的上游预打包副本/跨调用复用。不能凭空假定其中任何一项成立。

纯粹增加 b 的核数也不是首选：当前只有一个空间 tile，但输出仅 504 个元素。拆 C 会增加状态复制、短写边界审计和调度；不存在必须拆分的归约，不能以“空核”直接推导多核更快。

## B4. Action 实例

本方案有两个独立的流量目标，使用同一注册 Action 的两个实例，不把共享收益重复记账：

### `A-b-source = action.reduce_memory_traffic`

- target：全输入 paired packed 中间表示及其准备读取。
- stage：Pack→Sample 输入通路。
- parent：当前 `GridPackChannels<float>` 与 `GridSampleChannels<float>`。
- 等价值关系：
  \[
  P[i,0,c]=X[cI+i],\quad P[i,1,c]=X[cI+i+HW].
  \]
  直接读取必须逐项保持该映射，边界先判再读。
- 减少量：全输入准备 25,035,264 B；必要邻域原值仍须读取。
- 新代价：跨通道短 block、staging、Gather、偏移表和同步。

### `A-b-output = action.reduce_memory_traffic`

- target：padded NCS 输出中转。
- stage：采样结果→最终 y。
- 等价值关系：UB 中 `[c,p]` 已形成，唯一 owner 可连续写 \(CS=504\) 个 float。
- 减少量：4,032 B Compact 有效读写。
- 它依赖新 owner 的输出组织，但不依赖取消 Pack 才能在数学上成立。

无需新增 Action；也不使用 `reuse_input_tiles`，因为本轮没有证明多个输出点读取相同源地址，更没有建立原值驻留窗口。

## B5. C2 统一计划

计划名：`plan.b.direct-ncdhw`，**P_CHANGE**。

### 所有权与布局

- 一个 AIV owner 处理 N=1、全部 C=63、全部 S=8。
- 输出没有 partial、原子或跨核归并。
- 输入/geometry 只读；最终 y 与 x、grid、workspace 不得破坏性别名。
- 最终输出先 Gather 为 `[c,8]`，只取前 63 行，连续写 504 个 float。
- 只有这个 owner 写 y，因此 2,016 B 末尾不是与其他核共享的短写边界；不混用 Scalar 和 DMA 写同一输出区。

### UB 完整显式预算

取 batch=8、cp=64、gTile=64；全部按独立 TBuf 计，不假设自动复用：

| 区域 | 字节 |
|---|---:|
| staging：\(4\times8\times64\times32\) | 65,536 |
| raw：\(8\times8\times64\times4\) | 16,384 |
| raw Gather 偏移表 | 16,384 |
| values，两个槽 | 4,096 |
| 广播权重 | 2,048 |
| acc | 2,048 |
| geometry 本地区 | 4,096 |
| 输出 transpose 偏移表 | 2,048 |
| **合计** | **112,640 B** |

另加实际 SDK/API 隐含资源及框架预留。合法域为：

\[
112640+B_{\rm hidden}\le U_{\rm available}.
\]

本轮没有可用 UB 的实值，故不能把 `capacity=true` 当成已完成事实。

只需初始化消费者真正读取而 producer 没定义的区域：

- 内部快路 staging 的 4×8 个 dummy 通道行，共 **1,024 B**；
- raw 全部由 Gather 或备用填充路径定义；
- 不为“安全”把 staging 所有 padding 每次清零。
- Compare 的 raw 执行域为 4096 个 float，恰为 64 的倍数，无额外比较尾区。

### Workspace 与同步

- 算法 workspace 仅保留 geometry：**512 B**，实际分配另计对齐和框架保留。
- Geometry 阶段完成后 Sample 才读表；不能用核内 barrier 代替该阶段依赖。
- 核内：
  1. staging 初始化/DMA 完成；
  2. Gather 读 staging；
  3. raw 完成后范围扫描、取值和加权；
  4. 最后 Add 完成后输出 Gather；
  5. 最终 MTE3 读完后才退出/释放。
- 首版保留保守完成边，不额外引入双缓冲；b 单 tile 没有稳态跨 tile 流水收益依据。

### KEEP 判断

owner、输入通路、UB 布局、workspace 和输出通路均改变，**不能 P_KEEP**。算术代码原样复用只表示没有追加局部数值优化，不等于整体 NOOP。

## B6. C3 准确实施步骤及正文影响

1. 建立新直接源采样 entry，显式接收 `x/grid或geometry/y`；不再把 work 首段解释成 packed 输入。
2. 采用上述独立 TBuf 布局，一次 Init；宽整数核验所有偏移和字段范围后再窄化。
3. 搬入原几何记录，保持原权重位模式。
4. 对内部点发四个跨通道 DataCopyPad；不把 c=63 当作源输入通道读取。
5. 构造并保存整数 Gather 偏移表，保持 raw 的 `slot(k)` 映射；非内部点走先判界的备用填充路径。
6. 原样调用范围检测、软件保护和有序 Apply；不因本 workload x 范围已知而删掉保护。
7. 将 acc Gather 成 `[64,8]`，仅连续搬出前 \(63\times8\times4=2016\) B。
8. Host 在该域跳过 Pack 和 Compact，workspace 改为 geometry 段；其他域保留原调用链。

纸面 P/O 选择及实际作用：

- **P `planning.indexing.coordinate_neighborhood`**：把 owner 固定为全部 C×8 点，绑定真实 G/B/H/F；禁止由输出连续推断源邻域连续。
- **P `planning.layout.transpose`**：将 NCDHW 的通道 stride、UB 行 pitch 和最终 NCS 映射分开，要求把转换准备计入方案。
- **O `memory-transfer.strided-pad`**：直接决定 63 个 8B block 的合法表达、131064B 源间隔及每块 32B UB 跨度；这是本方案关键 API 依据。
- **O `buffer-lifetime.reuse`**：本轮主要用于审计最后消费者和“独立分配不能取 max”，不实际添加存储复用。
- **O `precision-boundaries.numeric/bounds`**：保持 k 顺序、特殊值路径、哨兵先判和只写有效输出。
- **O `tiling-tail.valid-length`**：最终写 2016B，不扩大成 2048B；UB 对齐空间不成为 GM 有效范围。

不采用 950 的 NDDMA、Compact mode、RegBase/VF，也不新增 Compare+Select，因而没有理由引入 Select 的 8KB 临时区。

---

# 四、分派、能力缺口与其他主要机会

## 1. 分派范围

纸面冻结互斥谓词：

- a：给定 FP32、N=1、C=63、D=H=W=32、S=32768 及三个模式；
- b：同上但 S=8；
- 其余所有元数据：原通用 fallback。

只用真实元数据，不按 case 名、x 数值范围或“grid 看起来内部”选择入口。a/b 的内容相关边界和数值保护由 kernel 保留。

当前 Host/key 命名空间未给出，故不伪造已占用/可用的 TilingKey。C2 的接线要求是上述唯一选择关系；C3 前须绑定实际 launch 方式、entry、字段 ABI 和唯一 uint64 key（若工程使用该机制）。**接线缺项不是 KEEP，也不是已完成分派。**

## 2. 其他机会为何本轮不选

- **几何融合/UB 直通**：可进一步少掉 geometry 写读 \(128S\)：a 为 4,194,304 B，b 为 1,024 B。但需改变生成位置与阶段边界，核验实际 launch/owner；不应错误宣传为再次省 C 倍生成。本轮两个主方案不依赖它。
- **软件流水/缩窄屏障**：a 有多 tile，具备研究价值，但需新增槽、重算峰值和事件闭环；b 单 tile 不宜机械加槽。本轮先消除明确中转/准备，不把存在 `PIPE_ALL` 自动判为瓶颈。
- **缓存 hint**：实际 L2/HBM、竞争工作集和后继消费者未知；保留原设置。不能用 NORMAL 保证命中，也不使用 PERSISTENT。
- **bank padding**：没有实际 UB 地址和 repeat 映射证据，不凭常数随手加 32B。
- **几何向量化或累加树改变**：前者尚需完整坐标/floor/异常值 API 证明，后者直接触及舍入顺序。本轮不以近似误差小替代数值门禁。
- **仅缩 workspace**：已读正文要求区分纯预留和实际触及。本轮减少的是实际 Pack/Compact 工作；空间减少是伴随结果，不是用分配大小推导时延。

---

# 五、后继可直接复用的摘要与验证事项

## 当前状态

- 授权：一轮纸面分析及 C2/C3 交接；未修改、未编译、未运行。
- 当前保留实现：题给原链，未被候选替换。
- a 候选：保留 paired 输入，Sample 直写 y。
- b 候选：保留几何表，直接读 NCDHW，单 owner 直写 y。
- 所有性能结果：**not_measured**；没有正确性通过或正式接纳结论。

## 已分析路线

| 路线 | 静态预测 | 新代价/限制 | 改变后继选择的证据 |
|---|---|---|---|
| a 直接最终输出 | 删除 16,515,072B Compact 请求，不增加采样内层发射 | Host/输出参数和 workspace 接线 | 若旧 Compact 已被实际调用端省略，则该减少项失去依据 |
| a 单份 packed 替代 | 比主方案再少 8,388,864B 准备写入 | 多 32,768 次邻域 API、65,536 block | 准备写成本与额外采样发射的同范围结果 |
| b 直接源+最终输出 | 不再每调用准备全部输入；逻辑 GM 请求约 19,264B | 32 次 API、2016 个短 block、112,640B 显式 UB及重排 | 若短 block/setup 成为主成本，重比普通 packed 或其他分块 |
| 几何本地化 | 删除 geometry GM 写读，不减少当前几何生成次数 | 新生成位置、阶段及生命周期 | 实际 launch/owner 证据和完整数值保持能力 |

## 实施前必须补齐的安全/结构项

1. 当前完整 Host、tiling ABI、实际阶段 entry 与执行依赖；原始头文件未包含当前 `geometryLength` 等完整字段。
2. 目标 SDK 对实际使用重载的支持、字段范围及 Gather 别名/位置要求。
3. 目标可用 UB 与隐含资源；分别闭合 a 原有分配和 b 的 112,640B 新分配。
4. x、grid、y、workspace 的别名及生命周期契约。
5. 原 oracle 的完整输出判据；不能自行放宽，也不能以当前父本 assumed 替代验证。

## 获得实施权限后的验证重点

- a：确认实际跳过 Compact、输出偏移完全一致、末 tile=32、全部输出唯一写回。
- b：核对四组 pair 地址和 8 邻居槽映射、dummy 通道、单点/重复点、非内部备用路径、最大合法地址及最后 2016B 写回。
- 两者：\(\pm0\)、次正规数、抵消、极值、NaN/Inf 及触发软件路径的整 tile 行为；不由本次 \([-1,1]\) 测试范围缩小算子数值合同。
- 所有未列元数据及相邻边界必须命中原 fallback，不能让新 entry 误吞未知域。
- 正确性和存储条件闭合后，再以**完整调用序列**比较端到端成本；分别观察准备、采样和输出变化。即使整体改善，也不能把联合结果任意分配给某个成员，更不能从逻辑字节差推出确定加速比。