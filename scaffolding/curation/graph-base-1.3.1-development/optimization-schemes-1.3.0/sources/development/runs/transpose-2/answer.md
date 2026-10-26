## 结论与状态

**本轮选择形成“连续段 DMA 搬运＋非连续域地址递增”的完整方案，保留原输出分核和通用标量搬运能力。**目标是同时减少两类明确存在的源码工作：

- 输入、输出共同连续的内段：不再逐元素读写 GM，改为按有效段经 UB 批量搬运。
- 仍需离散读取的置换：保留逐元素数据搬运，但把每元素的完整坐标除模解码改成一次初始化、随后按坐标进位更新源地址。

这不是“已经实现的候选”。本轮仅完成静态理解、选择和 C2/C3 纸面交接，状态为 **`conditional_plan / not_measured`**。目标 SDK、可分配 UB 和生成代码仍有明确待核项；没有执行 router、计算源码 hash、构建、修改文件或测试硬件，也不声称通过正式交接校验。

---

# 1. 当前实际执行过程与关键源码事实

### 1.1 语义、Host 和实际分支

这是纯粹的 **bit-preserving 布局置换**：

\[
y[o_0,\ldots,o_{r-1}]
=x[i_0,\ldots,i_{r-1}],\quad i[P[d]]=o_d
\]

没有归约、广播、数值 Cast 或算术后处理。NaN payload、无穷、符号零和整数位模式都必须保持。定义见 `transpose_definition.md:3–10`；`verify_result.py:6–19` 以无符号原始位类型比较，要求零 mismatch，而不是浮点容差。

实际执行链为：

1. Host 解析 shape、perm、dtype，并将 dtype 转为元素字节宽度。
2. 查询 `ACL_DEV_ATTR_VECTOR_CORE_NUM`，计算 tiling。
3. 分别分配输入、输出、tiling 的 GM 空间；输入输出不别名。
4. H2D 输入和 tiling，启动一次 `transpose_kernel`。
5. stream 同步后 D2H、写文件。

定位：`op_host/transpose.asc:39–60`。文件 I/O、H2D/D2H、初始化和 kernel 时间是不同范围，当前没有计时证据可将它们混为算子设备耗时。

Kernel 唯一的实现分派是按 `itemBytes` 选择 `uint8_t/uint16_t/uint32_t/uint64_t`，不是按真实浮点类型进行计算（`transpose_kernel.asc:25–31`）。因此当前标量赋值天然避免浮点算术改变 payload。

### 1.2 当前分核与每元素工作

令总元素数为 \(N\)，查询得到的核数为 \(C\)。Host 使用：

\[
B=\max(1,\min(\max(1,C),\lceil N/4096\rceil)),\quad
L=\lceil N/B\rceil
\]

block \(b\) 处理：

\[
[bL,\min((b+1)L,N))
\]

见 `transpose_tiling.h:31–33`、`transpose_kernel.asc:10–13`。这些区间不重叠并覆盖 `[0,N)`，非末核通常等长，末核截短。源码没有“尾部集中多干一大块”的证据，也没有固定只启动少数核的策略。

每个输出元素均执行：

- 从输出线性下标开始；
- 对全部 rank 维度执行 `% outputShape[d]` 和 `/ outputShape[d]`；
- 累加 `coord * inputStride[perm[d]]`；
- 一次标量源读取、一次标量目标写入。

见 `transpose_kernel.asc:13–21`。源码层面是约 **\(N r\) 次轴处理，包含 \(Nr\) 次除法和 \(Nr\) 次取模**；编译器是否合并除模、缓存字段、特化或消除部分工作尚未知。

### 1.3 存储、流水与同步

当前代码没有 `GlobalTensor` 批量搬运、UB 分配、Vector 转置、队列、预取或核内事件。实际可见路径是 AIV 上的 Scalar 控制及 GM 标量访问；不能给它补画成已有的 `MTE2→UB→V→MTE3` 流水。

核间没有输出合并或通信。Host 的 `aclrtSynchronizeStream` 保护 kernel 完成后再取回结果，不是可删除的热循环屏障。

用户指定的 **910C/dav-2201** 是已知目标约束，不冒充设备探测；实际 SDK、构建选项、核数值、可用 UB 尚未提供。`910c-hardware.md` 支持 A3/2201 的适用解释，不支持迁入 3510 的 Compact、RegBase、SIMT 或直通能力。

### 1.4 Workload 中真正不同的路径

| 地址结构 | case | 对选择的影响 |
|---|---|---|
| 保留共同连续尾轴 | 1、14 | 尾长分别为 128、127，可以直接复制位模式，不需要局部转置 |
| 二维转置或可合并成批量二维转置 | 2–5、6–13、17–19 | 大部分输出相邻元素的源地址不连续，不能当连续 memcpy |
| 更复杂的多轴重排 | 15、16、20 | 不能不经证明就归成一次普通二维矩阵转置 |

具体推导：

- case 1 为 `[64,32,512,128]→[64,512,32,128]`，共同连续段长 128。
- case 14 共同连续段长 127，行有效字节为 `127×4=508B`，需要合法非对齐搬运。
- case 6 可视为两个 `[9,65536]→[65536,9]`，是小通道转置，不是广播。
- case 10 可合并为 `[363×367,373]→[373,363×367]`。
- case 12 为三个 `[91,4001]→[4001,91]`。
- case 13 为 14 个 `256×256` 转置。
- case 20 虽有两个可合并输入前轴，但输出还反转了这两个轴的内部次序，不能直接套普通矩阵转置。

原逻辑有效输入读与输出写总量始终为 **\(2Ns\) 字节**，不是实际 HBM 流量。仅 case 1、4、5 的这一数值就各为 512 MiB，case 10 为 397,531,464B。大数据量不能证明已经带宽饱和，尤其当前并非大包 DMA 实现。

其他接口边界：定义声明 rank 2–5，Host 实际接受 rank 1–8；Host 没有完整检查 shape 乘积和字节数溢出。当前 20 case 都是正维度且规模可表示，但不能据此声称任意 Host 可接受输入都已安全。

---

# 2. 方案选择、竞争替代与工作量比较

## 2.1 所选完整方案 S1

### 路径 A：共同连续段批量搬运

从已有 shape、perm、inputStride 推导输入和输出共同连续的最大尾段长度 \(E\)。对每核原输出区间，切成不跨以下边界的段：

- 当前共同连续段末端；
- 本核输出区间末端；
- UB tile 上限 \(T\)。

每段只解码一次源起点，然后以有效字节参数：

```text
GM 输入 → UB → GM 输出
```

不做 Vector 算术、不清零无消费者读取的 dummy、不引入 GM workspace。

本轮 DMA 实现域收窄为 **`itemBytes∈{2,4}` 且 `E>1`**，分别使用同宽的 half/float 搬运视图，不作数值转换。其余字节宽度保留路径 B。这覆盖当前 case 1、14，但条件来自真实元数据，不来自 case ID。

### 路径 B：通用标量地址递增

每核在 `begin` 处解码一次完整输出坐标与源地址。随后按输出坐标的混合进制进位更新地址，不再对每个元素完整做 rank 次除模。

数据搬运仍使用原 `Raw` 无符号类型：

```text
y[linear] = x[source]
```

这覆盖其余 18 case，也保留 Host 原 rank 范围内的一般置换路径。该路径**没有解决离散 GM 标量读取本身**，不能称为已经完成向量化转置。

## 2.2 减少、保留和新增的工作

| 项目 | 原实现 | S1 |
|---|---|---|
| 共同连续域坐标解码 | 每元素一次完整解码 | 每搬运段一次 |
| 共同连续域 GM 数据访问 | 每元素 Scalar 读写 | 每段一次搬入、一次搬出 |
| 非连续域坐标解码 | 每元素 rank 次除模 | 每核初始解码，之后进位更新 |
| 有效逻辑 GM 字节 | \(2Ns\) | 仍为 \(2Ns\) |
| 非连续域数据搬运 | 离散 Scalar 读、连续 Scalar 写 | 保留 |
| 新增代价 | 无显式 UB | UB、DMA 设置与完成等待、坐标状态和进位分支 |

对 case 1，原来有 134,217,728 次逐元素处理；以不跨 128 元素连续段为单位，约为 1,048,576 个搬运段，另加原分核边界造成的少量拆段。case 14 有 7,154 个完整连续段，尾长 127。这里说的是**源码调用粒度预测**，不是指令数或加速倍数。

路径 B 对一般矩阵转置，大多数元素只更新最内轴；行末再进位。rank≤8 时最坏仍可能检查多维，但避免了每元素固定执行全部维度除模。新增数组状态的实际寄存器、栈和 spill 由编译结果决定。

## 2.3 最有竞争力的替代

### 性能潜力最大的替代：规则矩形 UB 转置

对二维及可合轴域，沿连续输入行搬入矩形，在 UB 内进行保位重排，再按连续输出行搬出。它有机会同时解决地址解码和离散 Scalar 数据搬运，潜在上限高于 S1 的路径 B。

**暂不把它写成可直接落地的本轮实现，原因不是“收益未测”：**

- 给定 P 的 `layout/templates/transpose.md` 支持矩形所有权与成本比较，但未提供通用保位转置原语的具体重载。
- 提供的小通道 `TransDataTo5HD+Gather` 是特定组合，不足以证明全部 1/2/4/8B 类型、任意矩形和尾部。
- 本题要求 int64、int8、NaN payload；不能通过数值 Cast 或乘单位矩阵绕过缺失的保位转置 API 契约。
- 多轴反序域还需要另外证明局部映射。
- 还需计输入/输出矩形 padding、重排临时区、offset 表及所有同步，而非只计算有效 tile 字节。

因此保留为明确的 **API 合法性补证路线**，不是认定它无价值。若补到适配 dav-2201、保位、支持目标类型和尾部的具体原语，它可能成为下一轮更优方案。

### 最强的低实施代价替代：只改地址递增

它不需要 UB，覆盖所有 case，可立即形成相同地址序列的纸面证明；但 case 1 的 1.34 亿次 Scalar 数据复制仍然保留。共同连续段已经从源码可证明，提供的 DataCopyPad 正文又足以定义合法参数域，因此本轮值得把这两条路径一起组成一个完整候选，而不是只缓存字段。

### 其他重要机会的处理

- **输入驻留/删重复读**：置换为一一映射，每个输入逻辑元素只消费一次。`problem.insufficient_input_reuse` 和对应 recipe 的“同原值多消费者”条件不成立。
- **减少内存流量**：没有可删除的中间 GM 往返，不能把访问合并记成少搬有效字节。
- **缓存策略**：`problem.cache_policy_mismatch` 明确一次性访问不自动证明策略错误；当前原始指针路径也没有可直接套用的 GlobalTensor hint 实例。保留默认策略。
- **流水/缩小同步**：当前没有待重排的 queue/event 链或循环屏障。S1 新增的完成边先采用浅串行实现，不另加“流水优化”意图。
- **尾块、核数、分派**：当前不是只有尾部慢；分核已经随 \(N,C\) 变化。`problem.dynamic_shape_mismatch` 的正文要求先证明机制差异，不能因为有 20 case 就造阈值和 Key。
- **UB bank、buffer 复用、Cube/CV 融合**：原实现没有这些结构。所给正文分别要求真实地址/repeat、最后消费者、矩阵计算或多阶段交接，不能拿来制造本题不存在的机制。

---

# 3. 注册 Action 实例与依赖

采用两个实例，因为目标独立：一个改变连续域的数据搬运粒度，一个改变通用域的地址控制。不是按文件数或 API 数拆分。

## A1：`action.coalesce_contiguous_transfers`

- **目标**：共同连续尾段的输入读取和输出写回。
- **阶段**：kernel 数据搬运。
- **workload**：正维度、合法置换、连续输入输出、out-of-place；本轮 DMA 域 `itemBytes=2/4 && E>1`。
- **父实现**：输入所示 `transpose_kernel.asc:13–21`。
- **实施方法**：逐元素复制合并为有效段 DataCopyPad；必要的段起点解码是配套工作。
- `symptom.source.inner_loop_copy=true`：源码逐元素执行复制。
- `constraint.semantic_equivalence`：由连续段源/目标映射证明；不得 Cast。
- `constraint.capacity`：**条件成立，当前未确认实际可用值**。
- **代价**：UB、DMA 发射、完成等待、段切分；有效字节不减少。

这里没有把原 Scalar GM 访存伪称为已有“小 DMA 指令”。

## A2：`action.hoist_invariant_control`

- **目标**：未走 A1 的置换路径，其输出坐标解码和源地址生成。
- **阶段**：kernel Scalar 地址控制。
- **workload/父实现**：原通用 Raw 路径，`transpose_kernel.asc:14–20`。
- **实施方法**：缓存本循环不变的输出维度与映射后源 stride；只在核起点做完整解码，随后等价进位。
- `symptom.source.control_metadata_overhead=true`：源码反复处理相同维度、stride 和完整解码结构；这不等于已经测得控制主导。
- `constraint.control_equivalence`：需按下节递推不变量审查。
- `constraint.semantic_equivalence`：数据操作及顺序保持。
- `constraint.capacity`：标量状态有界；实际寄存器/栈资源待编译确认。
- **代价**：坐标状态、进位分支、较长标量生存期。

A2 是地址控制变换，不是缓存派生数值张量，不借此授权任意数学预计算。

**依赖关系**：A1、A2 无结果依赖，互斥执行，共享同一分核和输出映射。容量不能相加；也不能把 A1 段解码减少和 A2 递推减少重复计到同一元素上。两实例均保持完整语义、唯一有效写回、合法容量/依赖/所有权。越过 owner、通路、workspace、dispatch 域或容量自由度应返回 C2。

---

# 4. C2 共同计划、边界、资源与 KEEP 判断

纸面计划身份记作 **`S1-P1`**，父本就是当前输入源码；未生成机器 hash。

### 共同骨架

- operator：transpose；family：layout；目标：用户指定 dav-2201。
- 保留原 `blockNum/blockLength` 公式和输出区间 owner。
- 无归约、无核间同步、无 GM 中间 workspace，`workspace_bytes=0`。
- 入口仍为 `transpose_kernel`。
- 不增加 Tiling Key；利用已有元数据在入口选择 A1/A2，Host/Kernel ABI 不变。
- 输入、输出均需保持 launch 期间有效且不别名；当前 Host 的独立分配满足该结构。

### 连续段判定

从输出末维向前，维护已合并长度 \(E=1\)。非单例轴满足：

\[
inputStride[perm[d]]=E
\]

时可并入，随后乘 `outputShape[d]`；单例轴可作为不改变地址集合的轴处理。遇到首个不满足的非单例轴即停止。所有乘法须先检查溢出。

这使每个长度 \(E\) 的输出段对应同长度连续输入区间。不能越过段末将不同输入行错误拼接。

### 参数和资源

初始纸面参数取 **\(T=1024\) 元素**，仅是有界初值，不是最优阈值。

单个 UB 数据区：

\[
U_{\rm data}=\operatorname{AlignUp}(T s,32)
\]

- 2B 路径：2048B；
- 4B 路径：4096B。

总预算必须满足：

\[
U_{\rm data}+U_{\rm framework/API/compiler}\le U_{\rm available}
\]

没有 Vector 算术 scratch、转换区、双槽或索引表。使用 TPipe 管理分配，不手工指定银行地址。不把材料中的物理 192KiB 当当前可分配 UB。

**许可自由度**：保持同一 owner、单槽、同一路径与有效域时，可缩小 \(T\)；不得自行加双缓冲、扩大 DMA 类型域、加入 GM workspace 或改分核。

### 输出边界

A1 整个调用均使用 DMA 写输出，不能在同一输出路径里任意混入 Scalar 头尾写。每段只写有效字节。原分核边界和 case 14 行边界可能非 32B 对齐，应按目标 UB→GM 非对齐重载审查，而非盲目补写或一律假定要 64B 对齐。

`strided-pad.md` 正文特别区分逻辑 owner、实际写 API 和物理覆盖：本计划依赖其“dummy 不写入 GM”的有效写出契约；实际 SDK 是否匹配是实施门禁。若不匹配，返回 C2，不现场扩大写范围。

### KEEP 判断

- **不是 P_KEEP**：虽然 owner 不变，但新增 GM→UB→GM 通路、UB 生命周期和路径选择，属于真实计划变化；当前也没有可引用的完整旧计划身份。
- 原分核的提取本身不算并行优化。
- A1、A2 均拟改变实现，不能记 O_KEEP。
- 缺少路由工具和正式引用不等于 KEEP；本轮也不是 NOOP。

P 正文采用 `layout/templates/transpose.md` 的输出 owner、合轴条件、完整通路及容量原则。未声称实际 router 命中或完整模板条件已自动满足。

---

# 5. C3 具体实施交接、API 与数值约束

以下是后续获准实施时的步骤，本轮没有执行。

## 5.1 修改位置和顺序

1. 在 `transpose_kernel.asc` 保留原 `TransposeScalar<Raw>` 作为可恢复对照。
2. 新增连续段判定与入口分支；只使用现有 tiling 字段，不重排结构或改变序列化。
3. 实现 A2 地址递推路径。
4. 实现 A1 单 UB 区有效段搬运路径。
5. 最终一次审查整个候选的覆盖、地址、生命周期和资源，而非要求每个中间步骤分别测量。

### A2 的准确递推不变量

设：

\[
D_d=outputShape[d],\qquad a_d=inputStride[perm[d]]
\]

每次数据复制前保持：

\[
linear=\operatorname{Flatten}(coord,D),\quad
source=\sum_d coord_d a_d,\quad 0\le coord_d<D_d
\]

核起点用原算法初始化。复制后，若还有下一元素，从末维向前：

```text
若 coord[d]+1 < D[d]：
    coord[d] += 1
    source += a[d]
    停止进位
否则：
    source -= coord[d] * a[d]
    coord[d] = 0
    继续向前进位
```

回绕减去的是该维当前贡献，避免用可能下溢的无符号“负 stride”。最后一个有效元素后不再更新。空核不做坐标解码。状态数组按最大 rank 8 定长，不把数组声明字节数冒充 UB 占用或实际 spill。

### A1 的段构造

在当前 `linear` 处：

\[
v=\min(T,\ end-linear,\ E-linear\bmod E)
\]

仅当 \(v>0\) 执行。用原坐标公式解码本段源起点；段内源地址由共同连续性证明为 `source+k`，目标为 `linear+k`。下一段重新确定起点，绝不直接假定跨行输入连续。

## 5.2 采用的 API 及硬约束

采用提供材料中 A2/A3 **无 `PaddingMode`** 的 DataCopyPad 重载：

- `GlobalTensor<T>` 绑定完整合法 GM 区间；
- `TPipe::InitBuffer` 为 VECIN TBuf 分配 `AlignUp(T*sizeof(T),32)` **字节**；
- `TBuf::Get<T>(T)` 的长度为 **元素**；
- GM→UB：
  `DataCopyPad(local, xGm[source], cp, pad)`；
- UB→GM：
  `DataCopyPad(yGm[linear], local, cp)`。

单段参数：

```text
cp.blockCount = 1
cp.blockLen   = v * sizeof(T)   // 有效字节
cp.srcStride = 0
cp.dstStride = 0
cp.rsv        = 0
pad.isPad     = false
```

约束：

- `blockCount` 在 A2/A3 的 0…4095 范围，本方案恒为 1；
- 有效 `blockLen>0`、小于 \(2^{21}\)，且为元素宽度倍数；
- UB 首址 32B 对齐，容量不小于向上对齐后的本段字节；
- 首末 GM 地址和乘加均先用宽整数检查；
- 不用 UB 对齐长度扩大 GM 读取或输出长度；
- `isPad=false` 不保证 dummy 为零；本方案不消费 dummy，因此不需清零；
- 不使用 950 Compact、负 stride、GM→VECCALC 扩展。

**同步采用最浅方案**：搬入后 `PipeBarrier<PIPE_ALL>()`，再搬出；搬出后再次等待完成，才复用该 UB 区。这里没有 Vector 消费者，不能机械套用只保护 V 的事件边。这个保守实现有同步代价，但完成关系清楚；后续缩小同步或多槽预取若超出本计划应重开 C2。

## 5.3 数值约束

- A2 继续使用原无符号 Raw 数据类型。
- A1 使用 half/float 仅作为同宽 DMA 视图；**不执行 Cast、Add、Mmad 或任何浮点处理**。
- 不修改 verifier、CTRL 饱和模式或输入域。
- case 15 的 NaN、case 14 的无穷范围、case 16 的全零都不能成为常量折叠或省略输入读取的理由。
- 完整验证应继续使用原始位比较，包含不同 NaN payload、±0、次正规数和整数极值，而不只沿用随机数值范围。

## 5.4 P/O 正文实际怎样改变了选择

| 正文 | 对本轮的具体影响 |
|---|---|
| P `layout/templates/transpose.md` | 使方案从“所有 permute 都批量 memcpy”收敛为共同连续段与一般映射两路；保留输出唯一 owner，拒绝把 case 20 误合成普通矩阵转置 |
| O `memory-transfer/coalesce.md`、`strided-pad.md` | 规定只合并真实连续地址；case 14 用 508B 有效长度，而不是 512B GM 读写 |
| O `tiling-tail/valid-length.md`、`precision-boundaries/bounds.md` | 将有效量、UB 对齐跨度、API 字节字段分别计算；要求宽整数预检和末地址证明 |
| O `scalar-control/hot-loop-address.md` | 支持等价地址递增和边界推演；但不把逻辑除模减少直接当成耗时同比减少 |
| O `scalar-control/tilingdata-access.md`、`constant-lifetime.md` | 当前已是 GM tiling 指针直读，没有整结构拷栈可删除；只缓存必要字段，防止入口缓存全部内容增加 spill |
| O `pipeline-sync/pipeline.md`、fallback | 选择单槽浅路径，不以 `num=2` 或历史 sigmoid 倍率为本题流水收益证据 |
| O `buffer-lifetime/reuse.md`、arch22 bank 正文 | 当前无可节省的独立临时区；不添加自定义 arena、固定 padding 或样例 UB 地址 |
| Cube、fusion、Cast、Compare/Select 正文 | 它们不是本题所需的保位置换原语；其数值、临时区和平台限制阻止用不等价计算拼装“转置” |

所给 exp、sigmoid、预取和 UB accumulator 历史记录仅用于校正“调用变少不等于同比提速”“直接父本与原基线分开”“未测/流程失败不等于性能反例”的判断，没有迁移任何速度、门槛或资格。

### 实施前仍须补齐的合法性证据

1. 安装 SDK 中上述 **VECIN TBuf→GM 的 DataCopyPad 重载**、half/float 类型和非对齐写出行为与材料一致。
2. 当前可用 UB及框架预留足以容纳选定参数。
3. 目标编译分支确为 dav-2201，生成代码资源合法。
4. 最终源码确实兑现所有分支覆盖、地址递推和完成边。

其中前三项不能由本轮纸面分析伪填 true。编译器是否已经优化原除模、S1 是否更快，是后续预测检查，不是相同性质的安全门禁。

---

# 6. 下一轮可复用三部分摘要与未测限制

## 当前状态

用户只授权本轮无工具纸面分析。原工程未修改，仍为唯一实际父本。目标 910C/dav-2201，20-case workload 未变。已形成 S1-P1：保持原输出分核，2/4B 共同连续尾段使用单槽 DMA，其余路径使用标量地址进位。正确性、构建、性能、正式准入均 **not_measured / not_evaluated**。

## 已尝试路线

| 路线 | 本轮实际完成 | 状态与限制 |
|---|---|---|
| S1 连续段搬运＋通用地址递增 | 源码理解、工作量比较、两 Action 实例、C2/C3 纸面交接 | 未修改、未构建、未跑 oracle；资源和目标 SDK 重载待核验 |
| 矩形 UB 保位转置 | 比较适用域、通路与必要 API 条件 | 未实施；具体通用转置原语、类型/尾部契约缺失，不是性能反证 |

## 剩余机会

| 残余工作 | 下一轮选择敏感条件 |
|---|---|
| 路径 B 仍逐元素离散读 GM | 若获得合法保位矩形转置原语，优先重新比较其额外重排成本与 S1 |
| 地址状态可能增加 spill | 编译后若寄存器/栈代价抵消除模减少，应调整缓存集合或恢复原解码 |
| A1 单槽同步和短段发射 | 正确性闭合后，依据 Task/timeline 决定是否值得流水化；不默认加槽 |
| 非 workload 的零维、极大乘积和 rank 边界 | 先明确接口契约与 Host 检查，不借 fallback 掩盖非法地址 |

未来获准实验时，应先审查、构建并运行原 oracle 全集及边界，再按当前统一计时协议评价整个 S1。没有消融不妨碍评价联合方案，但不能将整体收益分别归给 A1、A2。**本轮没有任何正确性通过、硬件瓶颈确认或加速比结论。**