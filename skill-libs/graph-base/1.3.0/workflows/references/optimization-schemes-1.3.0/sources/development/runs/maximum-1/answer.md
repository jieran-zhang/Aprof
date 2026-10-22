## 结论与状态

本轮选择形成一个**条件化、可落地的完整方案：仅对同形 `int8` 路径，将“经 FP32 比较”的转换链改为“经 half 精确比较”**。使用一个注册 Action：`action.coalesce_cast`。

这不是依据“少改代码”选择：case 6 有 **134,217,728 个元素**，原实现每元素经过六次转换；候选可以在整个 `int8` 值域上证明只需三次转换，同时降低显式 UB 分配，不增加 GM 流量、广播展开或分派入口。广播 Scalar 路径是最有竞争力的替代机会，下面单独比较，未因缺少性能数据而否决。

本报告仅完成源码理解、方案选择及 C2/C3 **纸面交接**。未调用工具、未修改工程、未编译、未验证正确性、未测硬件；无真实 router 回执、源码 hash 或候选产物。状态为 **`conditional_plan / not_measured`**，不是 C3 completed 或性能接纳。

---

# 1. 当前实际执行过程与关键源码事实

本节先独立说明现状，不把静态结构写成已测瓶颈。

## 1.1 数学与输入输出合同

目标为右对齐广播后的逐元素：

\[
y[o]=\operatorname{maximum}(x_1[offset_1(o)],x_2[offset_2(o)])
\]

- CLI 接收 shape、统一 dtype 和二进制文件，没有接收任意物理 stride；可见接口对应连续张量。
- tiling 左补 1，检查每轴相等或某侧为 1，生成输出 shape 和广播零 stride：`maximum_tiling.h:39–50`。
- reference 为 `torch.maximum`：`verify_result.py:17–29`。整数要求精确相等；浮点还检查 NaN、正负 Inf 的位置，并检查有限值误差。
- `matrix-20.json` 与 `cases.py` 的二十组输入相互对应。矩阵是静态解析结果，不证明数据生成和特殊值实际分布；未给出的生成器不能补猜。

需区分 **oracle 语义**与当前实现：Scalar 使用 `av > bv ? av : bv`，相等时选第二输入；浮点 NaN 情况不自动等同 `torch.maximum`。现有 Vector `Max` 的 NaN、符号零行为也不能只凭名字认证。

## 1.2 Host、分核和启动

`maximum.asc:42–59`：

1. 解析 shape/dtype，计算输入字节。
2. 初始化 ACL，查询 `ACL_DEV_ATTR_VECTOR_CORE_NUM`。
3. 计算 tiling，分配独立输入、输出和 tiling GM。
4. 文件读入、H2D。
5. **一次** `maximum_kernel<<<tiling.blockNum,...>>>`。
6. stream 同步后 D2H、写文件。

因此当前没有多 kernel 生产消费链，也没有算法 GM workspace。tiling GM 不是 partial workspace。`data_utils.h` 只是文件读写，不参与设备计算。

令输出元素数为 \(N\)、查询核数为 \(C_{\rm avail}\)：

\[
C=\max(1,\min(C_{\rm avail},\max(1,\lceil N/4096\rceil)))
\]
\[
L=\lceil N/C\rceil
\]

核 \(c\) 处理 `[cL,min((c+1)L,N))`，核内 tile 固定 **4096 元素**。这是 `maximum_tiling.h:37,52–54` 和 kernel 起止地址共同给出的划分，不是固定 SKU 核数，也不是已证明最优的 tile。

## 1.3 实际分支覆盖

| 实际路径 | workload | 当前核内工作 |
|---|---|---|
| 同形 half/float/int32 | 1、2、4、7、8、10、14、15、16 | 两路 DataCopyPad → Vector Max → DataCopyPad |
| 同形 BF16 | 3、9、17 | 两路 BF16→float，float Max，再转回 BF16 |
| 同形 int8 | 6 | 两路 int8→half→float，float Max，float→half→int8 |
| int64，不论是否同形 | 5、19 | `MaximumScalar`，逐元素多维解码、GM 读取、比较、写回 |
| 非同形 float/int32 等 | 11、12、13、20 | 同上 Scalar 通用索引路径 |
| 非同形 half | 18 | 连续末轴分段，向量 Max；每段重新读取对应广播源 |

依据：`maximum_kernel.asc:32–67,99–115,125–170`。

有两个会改变后续选择的事实：

- **int64 同形也没有绕过多维解码**。case 5 仍逐元素遍历 rank，而不是线性比较。
- **half 广播类不是通用广播 fallback**：它假设 x1 可按完整输出线性读取，x2 只有一条末轴向量。该假设适用于 case 18，但不能认证任意合法 half 广播；例如交换大、小输入就可能不成立。此次保留源码不等于确认其通用正确性。

## 1.4 数据位置、容量与依赖

同形向量路径为：

```text
GM x1/x2 --MTE2--> UB 输入队列
                    ↓ Cast/Max（V）
GM y      <--MTE3-- UB 输出队列
```

VECIN、VECCALC、VECOUT 都属于 UB，而不是三个独立容量池。每条队列 `InitBuffer(...,1,...)` 只有一个物理块，模板 depth 也为 1。EnQue/DeQue、FreeTensor 表达生产消费和复用协议；不能由“有队列”断言已经有效重叠，也不能把当前路径简单描述为所有流水完全串行。

按 `T=4096` 计算可见显式分配：

| 同形 dtype | 显式 UB 字节，不含框架/API 预留 |
|---|---:|
| half | \(3×2T=24,576\) |
| float/int32 | \(3×4T=49,152\) |
| BF16 | \(3×2T+3×4T=73,728\) |
| int8 | \(3T+3×4T+2T=69,632\) |

来源为 `maximum_kernel.asc:19–27`。这些是实际独立分配之和，不能因为临时值使用时刻不同就自动扣除空间。

DataCopyPad 当前使用单块有效字节 `count*sizeof(T)`；尾块不向上扩展 GM 范围。依据给定 `910c-hardware.md` 的 A3 重载说明：UB 仍需 32B 对齐容量，`isPad=false` 不保证 dummy 为零。现有 Max/Cast 只使用有效 count，不应把 dummy 加入数学输出。

**尚未确认：**目标 SDK、构建选项、实际核数、可用 UB、生成指令和自动同步细节。用户指定的 910C/dav-2201 是已知目标范围，不冒充设备探测。

---

# 2. 机会比较、所选方案与最强替代

## 2.1 所选：int8 精确中间类型收缩

原链，见 `maximum_kernel.asc:50–59`：

```text
a: int8 → half → float ┐
                       Max(float) → half → int8
b: int8 → half → float ┘
```

候选链：

```text
a: int8 → half ┐
               Max(half) → int8
b: int8 → half ┘
```

### 数值理由

对任意有符号 int8 值：

- `[-128,127]` 的全部整数都能由 half 精确表示；
- 两个 half 整数的最大值必是其中一个输入，不产生新舍入值；
- 结果仍在 int8 范围，使用原有 `CAST_RINT` 转回，结果精确；
- int8 不含 NaN、Inf、符号零或次正规数，不存在浮点异常值选择差异。

这不是依赖 case 6 随机取值范围的近似，也不是任意“降精度”：它覆盖**完整 int8 值域**。

### 工作变化

设实际总 tile 数为 \(S=\sum_c\lceil N_c/T\rceil\)。

| 项目 | 原实现 | 候选 |
|---|---:|---:|
| Cast 调用 | \(6S\) | \(3S\) |
| Cast 有效元素处理量 | \(6N\) | \(3N\) |
| Max | float、\(N\) 元素 | half、\(N\) 元素 |
| 有效 GM 读写 | \(3N\) 字节 | 不变 |
| 显式 UB | \(17T\) 字节 | \(9T\) 字节 |

case 6 的 \(N=134,217,728\)，因此预测删除 **402,653,184 次“元素转换处理”**。这是逻辑工作计数，不是等量 Scalar 指令或时间。

候选保留三个 int8 队列，增加/重组为三个独立 half 临时区：

\[
U_{\rm new}=3A(T)+3A(2T)+B_{\rm other}
\]

其中 \(A(x)=AlignUp(x,32)\)。在 `T=4096` 下，显式数据区为 **36,864B**，比原来少 **32,768B**。不顺带扩大 tile或增加槽数，避免把另一方向夹入本轮。

新增代价是三个 half 临时值的分配/生命周期管理，以及必要的 V 内完成边。输出、分核、GM 流量、launch 数和缓存策略均不变。

## 2.2 最有竞争力的替代：广播 Scalar 路径连续段化并向量选择

这是严重而真实的残余机会，不只是字段缓存。

- case 11、12、20 共 **21,285,024 个 FP32 输出**。
- case 13 有 **7,864,320 个 int32 输出**。
- 当前这些路径每输出执行 rank 级除模/stride 解码和 Scalar 数据处理。
- case 5、19 另有 **18,870,783 个 int64 输出**走 Scalar。

`problem.scalar_control_hot_loop.md` 支持把合法逐元素数据处理改为批量向量；`problem.broadcast_strategy_mismatch.md` 又要求区分解码、展开和源复用，而不是把所有广播都解释为“多读 GM”。

可行替代骨架是按连续内轴解码一次，保留广播映射，再批量计算。但具体成本明显分化：

- case 11：`H=513`，源行 2052B，不能靠 UB padding 假装满足静态 axis=0 Broadcast 的原始源 shape 32B 条件。
- case 12：内轴 37；case 20：内轴 101。逐行向量化可能制造大量短调用，需要比较行组合、展开与驻留。
- 若用 FP32 `Compare(GT)+Select` 保留原三元选择，A3 Compare 必须补到 64 元素粒度，Select 模式2还需 **8KB API 临时区**。单行 37 元素要比较 64，101 元素要比较128；初始化和 predicate 成本不能漏算。
- 该组合**不能直接承接 int32 大小比较或 int64**：给定正文明确 A3 int32 Compare 仅 EQ，Select 只支持 half/float。不能利用矩阵中的小整数范围，偷偷把一般 int32/int64 转成 float。
- FP32 三元选择和 `torch.maximum` 的 NaN 合同仍需分开处理，不能用一种替换同时宣称两者已等价。

**本轮为何选 int8：**广播方案可能更有关键路径收益，但需要更复杂的布局、短行组合、特殊值与 API 路径证明；int8 方案在大工作量上能直接删除转换链，新增存储反而更少，使用的转换方向也已出现在父源码中。这里不是拿 Cast 次数与 Scalar 迭代次数作跨单位排名，而是权衡了减少工作的规模、可证明范围与联合新增成本。

若后续发现 int8 路径主要受必要 GM 流量限制、转换减少未落入关键路径，或同步开销抵消收益，应优先重开广播连续段方案，而不是继续机械缩减临时区。

## 2.3 其他会影响判断的方向

| 机会 | 当前判断与正文对选择的影响 |
|---|---|
| int64 地址外提 | 很有价值的独立替代：同形线性索引、广播按行/段解码，可保持精确 int64 Scalar 比较。`hot-loop-address.md` 支持地址递增，但不解决数据本身的 Scalar 访存/比较。本轮未并入无依赖方向。 |
| 同形路径双缓冲 | `problem.pipeline_serialization.md`、`pipeline.md` 要求实际物理槽、独立 next tile、完成边与容量共同闭合。当前单槽提供候选依据，但未知已有跨流水重叠；不把加槽当确定收益。 |
| 放大 tile | `tile-amortization.md` 和 exp 条目支持摊薄每 tile 设置的假设，但 8192 及历史收益不迁移。int8 原来每 tile 已有大量转换，本轮先删除可证明冗余工作，不同时扩大工作集。 |
| BF16 删转换 | 原 BF16→float→BF16 是当前比较的类型边界；未给出可替代的 A3 BF16 Max 支持依据。不能照搬 int8 的证明。 |
| 缓存策略 | `problem.cache_policy_mismatch.md`、`cache-hint.md` 区分一次性输入与共享广播源，NORMAL/DISABLE 都不是收益保证。当前没有策略错误证据，也不能把逻辑请求当 HBM 字节。暂缓。 |
| 输入驻留 | case 18 确有重复广播源读取；可比较每 owner 驻留。`input-tile-residency.md` 要求同原值、有效地址域、最后消费者及完整容量，不代表全芯片只读一次。它不适用于同形 int8 两路不同输入。 |
| bank/padding、资源错峰 | `arch22-bank-layout.md` 和相关 Problem 要求实际地址、repeat 和目标映射。不能凭三个 InitBuffer 顺序认定冲突，更不能随手加32B。 |
| 融合、GM 中间往返、归约/merge、Cube | 当前一次 launch、Cast 中间值已在 UB，无归约、partial 或 Cube。所给 Cube/Fixpipe、CV 多阶段、Vector 链正文不适用于新增变换；不能为 maximum 创造这些阶段。 |
| 尾块、欠并行、失衡 | 向量路径已有有效 count 尾处理；没有独立 Scalar 尾慢路径。核数随 N 和查询核数变化，尚无集中重尾或欠并行依据，不优先改 owner。 |
| 元数据缓存、spill | `tilingdata-access.md` 明确要求与主要数据工作比较。当前已是 GM tiling 指针直读，没有整结构拷栈证据；重复字段是否已 CSE、是否 spill 未知。不能因容易证明等价就先做。 |

以上使用了所给 Problem 正文作机制比较；其中“原硬前提”的历史清单不覆盖本轮注册目录。实施条件以用户提供的**当前 Action 实例目录**为准，未把历史 profile 前提伪造为 true。

---

# 3. Action 实例与必要依赖

## 方案身份

- **方案：**`S1-int8-half-exact-max`
- **分析父本：**本次输入源码全文，未生成 hash。
- **目标：**910C / dav-2201，用户指定。
- **优化域：**`DispatchMaximum<int8_t>` 的 `sameShape=true` 分支；覆盖任意合法连续同形 int8 输入，不按 case ID 分派。
- **当前 workload 优化覆盖：**case 6。
- **完整回归覆盖：**二十组，不把未改变组称作优化收益覆盖。

## 唯一成员 A1

`action.coalesce_cast`——合并 Cast 与中间类型边界。

| 必要绑定 | 本实例内容 |
|---|---|
| target | `KernelMaximumSame<int8_t>` 的扩位、Max、缩位链 |
| stage | 核内 Compute |
| workload | 连续同形 int8；当前矩阵 case 6 |
| implementation | `maximum_kernel.asc:19–27,50–59`，父源码身份为本次输入 |
| 参数 | `T=4096`；三条 int8 单槽队列；三个独立 half 临时区 |
| 预期效果 | 删除两路 half→float 和结果 float→half，保留精确整数选择 |

### 条件审查

- `symptom.source.redundant_cast=true`：对 int8 的完整值域，FP32 中间比较不承担必要数值边界；源码链清晰。
- `constraint.precision=true`：上述精确表示与值域闭合证明成立。
- `constraint.semantic_equivalence=true`：逐元素结果与原 int8 比较一致；输出映射、读取集合不变。
- `constraint.capacity`：**条件成立，尚未核验目标实值**。公式已给出，候选显式分配低于父本；但父本本身没有构建/资源通过证据，不能据此宣称总容量已通过。

必要依赖是本实例内部步骤，不额外拆 Action：

```text
int8 输入搬入完成
→ 两份独立 half 输入转换完成
→ half Max 完成
→ half→int8 完成
→ 输出搬出；临时区允许下一 tile 覆写
```

没有第二个独立优化目标，不注册 `reuse_disjoint_onchip_buffers`、`reduce_memory_traffic` 或 `dispatch_by_workload` 来重复计功。

---

# 4. C2 共同计划、边界、资源与 KEEP 判断

## 4.1 共同计划快照

纸面计划标识：`P-S1-int8-half-v1`，阶段为 **execution**；不改变算法分解。

- 保留 `maximum_kernel` entry 和现有 dtype/sameShape 路由。
- 保留现有 blockNum、blockLength 公式及连续输出 owner。
- 保留 tile 4096、每队列一个物理块。
- 输入只读，输出与输入由当前 Host 独立分配；不增加原地/部分重叠别名支持。
- 无归约、无跨核同步、无 GM workspace。
- 仅同形 int8 的 Compute 改为精确 half 中间表示。
- 其余路径逐字保留的意图明确，但不因此获得新增正确性资格。

P 正文采用：

- `elementwise/templates/continuous.md`：用于核对连续 owner、按字节计容量、有效尾和实际队列槽。
- `elementwise/templates/broadcast.md`：用于比较广播替代的三种骨架及静态 Broadcast 限制，**未采用广播变换**。
- `elementwise/fallback.md`：用于界定“保留父路径”与“已验证 fallback”的区别。当前没有已验证父本，不能伪称通用 fallback 已成立。

## 4.2 资源合同

\[
U_{\rm alloc}=3A(T)+3A(2T)+B_{\rm framework/API/other}
\le U_{\rm available}
\]

- `T=4096` 时六个独立区域均为32B倍数，显式合计36,864B。
- 不做物理 alias，不用理想活跃下界替代实际 InitBuffer 总量。
- 没有 Select，因此**不引入其8KB临时区**。
- 不需要 L1/L0、跨核事件或新的全局槽。
- Scalar 寄存器变化须由未来编译报告核验，不把局部变量字节算进 UB。

## 4.3 许可自由度与重规划边界

C3 可以：

- 重新组织 int8 分支的三个 half TBuf；
- 缓存本分支需要的 count；
- 在既定核内依赖上使用必要 V barrier；
- 实现完全相同的有效 count 和尾部。

C3 不可以顺带：

- 改核数/owner、扩大 tile、增加物理槽；
- 扩展广播分派、添加 case 特判或新的数值路径；
- 改缓存策略、增加 workspace 或手工 bank arena；
- 修改 oracle 或放宽误差。

任何上述变化均返回 C2。

## 4.4 KEEP

**本轮不能登记 P_KEEP。**输入没有可引用、覆盖全部目标的有效既有共同计划。应先建立“提取现有分核/通路”的计划记录；按提供的契约可编码为 P_CHANGE，但注明**只是提取已有骨架，不计为并行优化**。

A1 的 O 为实际改变，不是 O_KEEP。未选中的广播、流水等方向不建立成员，自然不存在用 O_KEEP 填数量的问题。本方案不是 NOOP。

本工程是 kernel 直调，**不添加 `TILING_KEY_IS`**。`dispatch.md` 明确该宏不能机械移入直调工程。当前选择仍由 `dtype==MAX_INT8` 和 `sameShape` 决定，无新增 key 或入口。

---

# 5. C3 具体实现交接与 API/数值约束

以下是未来获准修改时的具体步骤，不代表本轮已有 patch。

## 5.1 修改位置和顺序

### 步骤一：分离 BF16 与 int8 临时分配

修改 `KernelMaximumSame::Init` 的类型分支：

- BF16 保留三个 float 临时区及原计算。
- int8 不再分配 `tmp1_/tmp2_/tmpOut_` 的 float 存储。
- int8 分配三个独立 half 区，每个 `AlignUp(T*sizeof(half),32)` 字节。
- 三个 int8 队列仍各一槽，分配长度按最大 T，而不是当前尾长。

不能只是“不再使用 float 变量”却保留其 InitBuffer；否则不能扣除其物理分配。

### 步骤二：替换 int8 Compute

采用既有公共接口形式：

```cpp
AscendC::Cast(ah, a, AscendC::RoundMode::CAST_NONE, count);
AscendC::Cast(bh, b, AscendC::RoundMode::CAST_NONE, count);
AscendC::PipeBarrier<PIPE_V>();

AscendC::Max(oh, ah, bh, count);
AscendC::PipeBarrier<PIPE_V>();

AscendC::Cast(out, oh, AscendC::RoundMode::CAST_RINT, count);
AscendC::PipeBarrier<PIPE_V>();  // 明确临时区最后读完成后才允许复用
```

这里 `ah/bh/oh` 是三个独立 half LocalTensor，不能复用原来唯一 `tmpHalf_` 同时保存两个输入。上述保守 V 完成边计入候选成本；它们不替代 MTE2→V、V→MTE3 的队列依赖，也不宣称跨 tile overlap。

未来若目标 SDK 能证明现有自动同步已完整覆盖某些 V 依赖，可以在同一计划内收敛冗余 barrier，但必须记录具体保证，不直接删除等待碰碰运气。

### 步骤三：保留搬运和有效尾

继续使用：

```cpp
DataCopyExtParams{1, count*sizeof(int8_t), 0, 0, 0}
DataCopyPadExtParams<int8_t>{false,0,0,0}
```

- 输入只读有效 `count` 字节，输出只写有效 `count` 字节。
- `count` 是元素数，不是 mask 或 repeat。
- `count=0` 不调用转换/Max/DMA。
- half 临时区容量按 `2T` 字节，不使用 int8 队列的字节容量作为 half 容量。
- 不清零整个 tile；本方案没有消费者需要读取 `[count,T)`。

## 5.2 API 与数值核验清单

给定材料支持的准确约束：

- `InitBuffer` 长度为字节、num 为物理块数，内部32B上取整；`Get<half>(T)` 的 T 为元素。
- A3 DataCopyPad 使用无 mode 重载；单块有效 `blockLen<2^21`。这里最大4096B，远低于上限。
- 普通 Vector repeat 为256B；half 为128元素、float为64元素，但本方案使用 count 重载，不能把4096写入 mask。
- `CAST_NONE` **不普遍表示无舍入**；本例精确是因为 int8 每个值都可由 half 表示。
- half→int8 沿用 `CAST_RINT`，结果已证在目标范围，无需饱和或截断假设。
- 三个 half 区与输入/输出物理存储独立，不依赖未证明的原地 overlap。

**剩余具体 API 缺口：**父源码已有 int8→half、half→int8 和 half Max 的调用，但没有提供目标安装 SDK 的完整 Max 支持表和编译结果。实际 half/VECCALC/count 组合、自动同步及隐含预留仍须目标 SDK 核验。源码中出现 API 不等于已证明目标编译通过。该缺口阻止宣布 C3 实施就绪/完成，不阻止形成当前精确方案。

## 5.3 正文怎样实际影响方法

- `vector-api/recipes/cast.md`：促使先逐边检查舍入，选择完整 int8 值域证明；没有把一般 float→half→float 当恒等。
- `buffer-lifetime/recipes/reuse.md` 与 fallback：决定采用独立 half 区，不用 C++ 作用域假装复用，也不引入手工 alias。
- `precision-boundaries/numeric.md`：阻止把 Scalar 三元选择直接换成“名字相似”的 Max，并要求保留 NaN/Inf/±0回归；本次仅整数域消除了这些选择歧义。
- `compare-select-tail.md`：其 A3 截尾规则、类型支持和8KB临时区实质改变了广播替代的成本判断；本方案**未采用 Compare/Select**。
- `memory-transfer/coalesce.md`、`strided-pad.md`：帮助区分发射减少、有效字节减少与 UB padding；此次没有可宣称删除的 int8 GM 流量。
- `pipeline.md`、`slots.md`：决定不把临时区节省自动转成双缓冲，也不为普通 Vector 添加全局槽。
- `valid-length.md`、`bounds.md`：决定有效 count、分配容量和 DMA 字节分别计数，所有乘加先宽整数检查。
- exp、sigmoid、预取及 UB accumulator 历史条目只用于保留“结构变化不保证性能、失败不可错归因”的限制，其倍率和旧门槛均不迁入本任务。

所给 P/O router 正文可支持上述人工路由判断；未执行内部 router，也没有生成叶版本/hash。因此这里只记录**拟采用的方法及必要正文快照**，不伪造正式命中或实施回执。

## 5.4 下一次允许执行时的验证边界

先审查、构建，再完整 oracle；正确性前不计时排名。

重点补充：

- int8 全值域：可覆盖全部256×256输入对。
- 长度 `1、31、32、33、127、128、129、4095、4096、4097`，多 tile、最后核、非整齐分核边界。
- 正负极值、相等值、跨 tile 临时区复用和重复运行。
- 二十组全部验证；case 14/15 的 Inf/NaN结果不能因本轮未改变就跳过。
- 一般 half 广播超出现有专用路径的合法性问题另存，不能用父路径充当未经验证的全域 fallback。

若完整验证发现父本已有失败，应区分既有语义问题、候选引入错误和环境缺失，不修改 verifier 掩盖。未来性能评价采用任务当时冻结的统一协议，不复用历史实验门槛。

---

# 6. 下一轮可复用的三部分简短摘要

## 当前状态

用户仅授权一轮纸面分析；无工具、无修改、无编译及硬件测量。原始源码仍是唯一保留实现，正确性和性能均未验证。目标910C/dav-2201。已完成当前执行路径理解；方案 `S1-int8-half-exact-max`、计划 `P-S1-int8-half-v1` 为本文纸面标识，尚无 hash/落盘产物。状态 `conditional_plan / not_measured`。

## 已尝试路线

本轮只比较、未实施：选择同形 int8 的六 Cast 链改为三 Cast、half Max；当前矩阵优化覆盖 case 6，完整 int8 值域等价证明成立。显式 UB 预测69,632B→36,864B，GM有效字节不变。目标SDK支持、完整容量、同步、正确性及净收益未验证；未测结果不是机制反证。

## 剩余机会

最强替代为广播 Scalar 连续段化/源复用，尤其 FP32 的 case 11/12/20；必须计入短行补齐、predicate、Select 8KB及特殊值合同。int64 同形线性索引和广播段级解码也值得独立比较，不能窄化为float。流水、tile放大、case18输入驻留与缓存策略保留为候选；有实际编译/正确性/计时反馈后，再比较残余工作与新增代价，不因本轮已选 int8 而自动继续同一路线。