## 结论与本轮状态

本轮选择的完整方案是：

> **仅对同形 int8 路径，将“int8→half→float，float Max，float→half→int8”改为“int8→half，half Max，half→int8”。**  
> 保持核数、输出分区、4096 元素 tile、GM 搬运、有效尾长及队列生命周期不变；使用三个独立 half 临时区，不引入原地别名或双缓冲。

登记一个 `action.coalesce_cast` 实例即可。该方案针对的是 **case 6 的 134,217,728 个元素**，不是通过测试值域特判：全部 int8 值都能被 half 和 float 精确表示。

最强竞争方案是重构 float32 广播路径，消除 case 11、12、20 的逐元素多维解码和 Scalar 比较。它值得实施假设试验，并非因没有 profile 而否决；但它需要联合处理短行批量、广播映射、Compare 的 256B 执行粒度、predicate、NaN 传播以及 Select 的 8KB 临时区。本轮优先选择工作减少明确、覆盖大且新增执行代价较低的 int8 转换链方案。

**状态：纸面方案及 C2/C3 交接完成；未修改、未编译、未运行、未测量。** 以下实例和计划身份是本文的纸面标签，不是已生成或已校验的 runtime 产物。

---

# 1. 当前实际执行过程与改变选择的源码事实

## 1.1 数学与调用合同

目标是按右对齐广播规则计算：

\[
Y[o]=\operatorname{maximum}(X_1[offset_1(o)],X_2[offset_2(o)])
\]

输入来自二进制文件，视为连续 ND，同一请求只有一种 dtype。Host 分别分配两个输入和输出，当前直调方式没有输入输出别名，也没有计算 workspace。

实际调用链为：

1. 解析 shape、dtype；
2. 查询 `ACL_DEV_ATTR_VECTOR_CORE_NUM`；
3. `ComputeMaximumTiling` 产生广播 stride、总长度和核分区；
4. H2D 输入和 tiling；
5. 启动一次 `maximum_kernel`；
6. `aclrtSynchronizeStream` 后 D2H、写文件。

证据：`maximum/op_host/maximum.asc:42–60`。`data_utils.h` 仅负责文件 I/O，不在本轮 device 优化范围内。端到端时间包含这些工作，但不能据此推断 kernel 内部时间占比。

Oracle 是 `torch.maximum`。整数必须 exact；浮点还检查 NaN、正负无穷掩码及有限值误差，不能只看 `exact_match`，也不能因浮点误差容限存在而主动改变选择语义。证据：`scripts/verify_result.py:17–29`。

矩阵与 `cases.py` 一致描述了 20 个 case；矩阵是静态读取结果，不证明实际生成文件中的特殊值分布或任何正确性结果。

## 1.2 Tiling 与输出所有权

`maximum_tiling.h:35–54` 的实际策略为：

- 左补 1，按广播兼容性检查每轴；
- 输入维度为 1 时 stride 写为 0；
- `tileElements=4096`，所有 dtype 共用；
- 启动核数为查询核数与 `ceil(total/4096)` 的较小值，至少 1；
- `blockLength=ceil(total/blockNum)`；
- 核 \(c\) 拥有：

\[
[c\,blockLength,\ \min((c+1)blockLength,totalLength))
\]

有效区间不交叠且覆盖完整输出，没有归约或核间合并。非末核边界并未强制对齐到 32B；不能将该实现描述成“已采用对齐粒度均衡分区”。

核数实值、SDK、编译选项和可用 UB 未提供。用户指定的 **910C/dav-2201** 是已知目标约束，不是设备探测结果。

## 1.3 当前实际分支

| 实际路径 | 当前 case | 每元素/每段工作 |
|---|---|---|
| 同形 half、float32、int32 | 1、2、4、7、8、10、14、15、16 | 两次搬入，一次 Vector Max，一次搬出 |
| 同形 BF16 | 3、9、17 | 两次转 float、float Max、转回 BF16 |
| 同形 int8 | 6 | 六次 Cast、一次 float Max |
| 任意 int64 | 5、19 | `MaximumScalar`，逐输出完整坐标解码、Scalar 比较和写回 |
| 非同形 float32/int32 | 11、12、13、20 | 同上，使用零 stride 实现广播 |
| 非同形 half | 18 | 最内轴分段，Vector Max；每段重新搬入对应 B 片段 |

证据：`maximum_kernel.asc:31–67、99–115、125–170`。

特别需要保留的理解边界：

- half 非同形分支实际假定 **X1 是完整输出、X2 是末轴向量**，`x2_` 长度直接设为末轴长度，未使用通用 stride。它适用于 case 18，但 **Host 接受的任意 half 广播形状并不因此都受支持**。
- `MaximumScalar` 使用 `av > bv ? av : bv`；浮点遇 NaN 时不自动等价于 `torch.maximum`。当前矩阵中广播浮点范围为有限值，但不能把这个事实扩成通用浮点广播合同。
- 同形 Vector Max 的特殊值行为也不能仅凭 API 名称认定正确或错误。case 14、15、16 需要原 oracle 核验，当前没有结果。

## 1.4 数据位置、分配与依赖

同形 Vector 路径是：

```text
GM 输入 → MTE2 → UB 输入队列
                    ↓ Cast/Max，Vector
GM 输出 ← MTE3 ← UB 输出队列
```

`VECIN/VECCALC/VECOUT` 都映射到 UB，不是三个物理存储层。三个队列均为 `TQue<...,1>`，且 `InitBuffer(...,1,...)` 只分配一物理槽。代码每轮搬入、计算、搬出，不能凭队列存在宣称已经获得跨 tile 重叠。

队列协议保护输入就绪、输出就绪及槽位回收；转换临时区的 V 内依赖仍须由目标 SDK 的同步规则和编译审查闭合。本文不把顺序发射当作所有异步操作均已完成。

令 \(A(x)=AlignUp(x,32)\)，只计可见用户分配：

| 同形路径 | 显式 UB 公式 | T=4096 |
|---|---:|---:|
| half | \(3A(2T)\) | 24,576B |
| float32/int32 | \(3A(4T)\) | 49,152B |
| BF16 | \(3A(2T)+3A(4T)\) | 73,728B |
| int8 | \(3A(T)+3A(4T)+A(2T)\) | 69,632B |

这些不是完整编译资源报告，尚不包含未知的框架/API 预留。

上述解释采用 `910c-hardware.md` 中 A3/2201 的路径、InitBuffer 单位、物理槽与队列深度区别，以及 DataCopyPad 有效字节约束。Add 示例用于纠正“队列/BUFFER_NUM 即重叠”的推理；Cube 示例没有成为本算子的执行路径证据。

---

# 2. 候选机制、完整方案与最强替代

## 2.1 选择比较

| 机会 | 支持与预计减少的工作 | 新增代价、反证或限制 | 本轮判断 |
|---|---|---|---|
| **int8 转换链收缩** | 六次 Cast 降至三次；float Max 改 half Max；三个 float 临时区和一个 half 临时区改为三个 half 区 | 保留两次扩位和一次缩位；需核验目标 SDK 的调用与同步。当前整数值均可精确表示，无近似 | **选中** |
| **float32 广播连续段/短行批量化** | case 11/12/20 共 21,285,024 个输出；源码约 93,587,070 次轴处理，每轴含除模和 stride 累加，可降为按行/批次解码 | UB 布局、短行 padding、广播展开、Compare/Select、NaN 修正及同步成本 | **最强替代，保留具体方案** |
| int64 去除逐元素通用解码 | case 5 同形仍执行 rank 解码；case 19 可按行缓存 B 地址 | 可先简化地址，但 Scalar 数据比较仍在；不能用 float 转换覆盖完整 int64 域 | 暂缓；不是已解决 |
| half case 18 保留 B | 同一 B[8193] 被 255 行重复消费，可在本 owner 内驻留 | 常驻区至少 \(A(8193×2)=16416\)B，需明确跨分段生命周期；跨核仍各自读取 | 有依据，但覆盖和减少工作小于本轮主方案 |
| 同形路径双物理槽/流水 | 当前单槽限制可重叠窗口，多 tile 独立 | int8 原分配全双槽需 \(6A(T)+3A(4T)+A(2T)=81920\)B；需排程和完成边，不只是改 depth | 值得后续比较，不与本轮无依赖地叠加 |
| 增大 tile、cache hint | 可摊销调用；一次性输入可比较 NORMAL/DISABLE | 必要 GM 字节不减少；全序列复用、实际 cache 状态和容量未知 | 不作为本轮主方向 |

### 为什么不是只缓存 tiling 字段

`MaximumScalar` 的数据处理和 rank 解码是真正的逐元素循环；缓存少数 `tileElements/rank/stride` 并未消除这类工作。`problem.control_metadata_overhead.md` 和 `tilingdata-access.md` 明确要求将字段 load 与逐元素数据处理区分，并考虑 CSE、寄存器生存期。因此本轮没有把容易证明等价的字段缓存置于主要机会之前。

### 为什么不选其他机制

- 无归约、partial 或 merge：归约重构、chunk 合并不适用。
- 只有一次 kernel launch，转换中间值已经在 UB：没有可消除的跨 kernel 链或 GM 中间往返；Cube/Matmul/Fixpipe、CV 多阶段交接正文不提供本轮采用依据。
- 当前输出基本按 tile 写回，Scalar 广播则逐元素写回；其碎片化是广播重构的组成成本，不另登记重复收益。
- 未知可用 UB 不等于已经确认容量压力；未知编译报告不等于 spill。
- 没有实际 UB 地址、repeat 指令或冲突观测，不能从 4096 这个 tile 推定 bank 冲突。`arch22-bank-layout.md` 的场景还表明“加 32B”可能变坏，故不照搬固定地址或 padding。
- 没有持续带宽基准，不裁定带宽饱和。逻辑 GM 请求也不作为 HBM 字节。

这些判断分别遵循已提供 Problem 正文中的适用域、反证和替代解释，而不是按 Action 数量筛选。

## 2.2 所选方案的共同工作账

原 int8 每 tile：

```text
a → half → float ┐
                 float Max → half → int8
b → half → float ┘
```

候选：

```text
a → half ┐
          half Max → int8
b → half ┘
```

对 case 6，\(N=134217728\)：

- Cast 的逻辑处理元素次数：\(6N→3N\)；
- Max 仍处理 \(N\) 个元素；
- 输入输出有效 GM 流量均为 \(3N=402653184\)B，不减少；
- 显式 UB：69,632B → 36,864B，减少 32,768B；
- 不增加广播展开、predicate、初始化或额外 GM 搬运；
- 不把“Cast 减半”解释成执行时间减半。

候选 UB：

\[
U_{\text{candidate}}=3A(T)+3A(2T)
\]

没有依赖独立生命周期复用来凑容量，因此不需添加 buffer reuse Action。

## 2.3 最强替代为何暂列第二

float32 广播的结构机会很大，具体可采用：

- **case 11 类 `[R,H]` 与 `[H]`**：B 在本 owner 中驻留，A 按行/段搬运；不能将 H=513 的源伪装成满足 axis=0 静态 Broadcast 对齐要求的原始 shape。
- **case 12/20 类 `[P,K,H]` 与 `[K,1]`**：按若干连续行组成 UB 批次，B 的每行标量通过合法 axis=1 广播展开；A/Y 的 GM 有效行宽仍为 H。
- 条件选择使用 GT predicate 和 Select 模式2；要覆盖通用 maximum 的 NaN 传播，还需显式修正，不能只把 `a>b?a:b` 改写为一次选择。

`compare-select-tail.md` 改变了本轮成本判断：

- A3 Compare count 只计算完整 256B；
- FP32 必须按 \(c=64\lceil n/64\rceil\) 建立已定义输入域；
- H=37、101 分别至少对应 64、128 个比较元素，不能靠 DataCopyPad 的 32B dummy 自动满足；
- predicate 按 bit 计，并按 32B 分配；
- Select 模式1/2需计入 8KB UB API 临时区；
- int32 仅支持 EQ Compare，Select 仅 half/float，故该方法不能直接覆盖 case 13，更不能覆盖 int64。

这不是笼统的“API 未知”，而是已知的具体准备成本。结合本轮 int8 域的 134M 元素、三次 Cast 删除及无新热循环准备工作，我选择 int8 链收缩先试。**若后续有效分阶段时间表明上述广播 Scalar 路径主导整个评测，广播方案优先级应提高；当前没有时间权重足以断言哪一个更快。**

---

# 3. 注册 Action 实例与必要依赖

## 实例 A1：`R1-A1-int8-cast-chain`

- **注册 Action**：`action.coalesce_cast`
- **target**：`KernelMaximumSame<int8_t>` 的转换与 Max 链
- **stage**：核内 Compute
- **workload**：连续、同形 int8 输入；当前命中 case 6
- **implementation**：输入提供的 `maximum_kernel.asc:50–59`，父本为本次源码文本
- **scheme**：`R1-S1-int8-half-max`
- **实际意图**：删除不承担可见精度边界的 float 扩位/缩位，让 Max 在精确 half 表示上执行

### 所绑定目录前提逐项审查

| 前提 | 当前判断 |
|---|---|
| `symptom.source.redundant_cast` | 有源码与数值依据：half 中的 int8 值扩至 float，再选择后缩回 half，不改变这些值 |
| `constraint.precision` | 数学证明成立：int8 全域均为 half/float 可精确表示的整数，Max 只选择已有值，不产生中间算术溢出 |
| `constraint.semantic_equivalence` | 对该域成立；输入输出 dtype、整数结果、有效 count 和选定数值均不变。目标 API 落地仍需 SDK 核验 |
| `constraint.capacity` | 已给出比原分配更小的字节公式；目标可用 UB 与预留实值未提供，**实施前仍需闭合** |

目录为当前绑定版本；Problem 正文中的历史 profile 前提不冒充本轮已测事实，也不覆盖当前注册目录。

**必要依赖只有两个门禁，不是新增 Action：**

1. C2 批准精确表示域上的计算中间类型调整，并冻结资源/分区；
2. C3 核验 half Max、两种 Cast 及其依赖在安装 SDK 上合法，且总资源满足预算。

不添加 `vectorize_scalar_loop`、`reduce_memory_traffic` 或 `reuse_disjoint_onchip_buffers`：本方案没有优化 Scalar 广播、没有删除 GM 字节，也没有共享临时区。

---

# 4. C2 共同计划、边界、资源与 KEEP 判断

## 4.1 共同骨架

纸面计划：`R1-P1-int8-half-max`。

| 项目 | 冻结内容 |
|---|---|
| 算法 | 两输入逐元素 maximum，无归约 |
| 任务/owner | 保留当前 `blockNum/blockLength` 和连续输出区间 |
| tile | T=4096 元素；本轮不放大 |
| 数值 | int8 输入输出；两个 half 输入临时值、一个 half Max 结果；转换模式见 C3 |
| 通路 | GM→VECIN→VECCALC/VECOUT→GM |
| 缓冲 | 输入 A/B、输出各一物理队列槽；三个独立 half TBuf |
| 同步 | 保留队列生产消费协议，闭合 Cast→Max→Cast 的 V 内依赖及临时区下一轮覆盖 |
| workspace | 计算 workspace 为 0；tiling 存储不混算为计算 workspace |
| 未变域 | 其余所有 dtype、广播与 int64 路径 |

输入输出无别名由当前 Host 的独立分配支持；本计划不扩大为支持任意外部重叠 view。

## 4.2 资源门禁与自由度

\[
3A(T)+3A(2T)+S_{\text{API}}+R_{\text{framework}}
\le U_{\text{available}}
\]

T=4096 时可见数据为 36,864B。未知的预留不得取零作为事实。相对原路径显式分配下降可支持可行性判断，但 baseline 未经构建，不能据此宣布容量已验证。

C3 允许：

- 删除不再使用的 float 分配；
- 在本分支增加三个独立 half 临时区；
- 实现上述转换链和必要 V 内完成边；
- 缓存本地 count 等普通实现细节。

不允许：

- 改核分区、核数、tile、物理槽数；
- 新增预取、buffer alias、自定义物理地址；
- 改 cache hint；
- 将方案推广到 BF16、int32、int64；
- 新增 shape 性能阈值。

越界返回 C2。

## 4.3 Dispatch 与 KEEP

沿用一个实际 C entry：`maximum_kernel`。其内部 int8 同形分支变化，不新增 launch entry，也不使用不适合当前直调工程的 `TILING_KEY_IS`。

如后续生成机器计划，可用互斥的“同形 int8／其他域”组记录方法差异，key 只是计划身份，不能宣称当前工程已经传递或执行了这些 key。Host 的 dtype/sameShape 与实际分支必须一起核对。

**不记 P_KEEP：**

- 未提供覆盖本次目标的有效父计划身份和许可自由度；
- 需要显式批准 float→half 的计算中间类型调整。

应分别记录“提取现有分区骨架”和“批准本次数值实现变化”，不能将前者统计为并行优化。A1 为 **O_CHANGE**；本轮不是 NOOP。其余源码保持原样，也不等于那些路径已取得正确性或 KEEP 资格。

---

# 5. C3 实现交接：具体步骤、API 与数值约束

## 5.1 计划中的实现步骤

只在未来获得实施授权后，在隔离副本中执行：

1. **保留父本、理解和本决策身份。** 当前没有计算 hash，不补造。
2. 在 `Init` 的 int8 分支，将 `tmp1_/tmp2_/tmpOut_` 的 float 分配和共用 `tmpHalf_` 替换为三个独立 half 区；BF16 分支保持原样。
3. 仅替换 int8 Compute 的六 Cast 链，调用形态为：

```cpp
// ah、bh、oh：独立、32B 对齐的 half LocalTensor，容量各至少 T。
// a、b、out：当前队列实际分配的 int8 tensor；count 为有效元素数。
AscendC::Cast(ah, a, AscendC::RoundMode::CAST_NONE, count);
AscendC::Cast(bh, b, AscendC::RoundMode::CAST_NONE, count);
// 按目标 SDK 同步契约保证两次 Cast 的结果可供 Max 读取。
AscendC::Max(oh, ah, bh, count);
// 保证 Max 结果可供缩位读取。
AscendC::Cast(out, oh, AscendC::RoundMode::CAST_RINT, count);
```

这只是拟采用的计算片段，**不是已构建代码**。若安装 SDK 要求显式 V 内屏障，在两处真实依赖间使用合法 `PipeBarrier<PIPE_V>()`；不得把它当作跨流水完成边。跨轮重用 `oh` 前还必须保证上轮缩位已经读完。

4. 保留现有队列 EnQue/DeQue/Free 的合法顺序和 DataCopyPad。
5. 更新资源表，确认原 float TBuf 的实际 `InitBuffer` 已删除；不能只改视图后仍声称省了分配。
6. 完成静态审查后才构建、跑完整原 oracle；当前授权不执行这些步骤。

## 5.2 准确单位和边界

- `count` 是**元素数**，满足 `0<count≤4096`；空 owner 不发计算和 DMA。
- int8 搬运 `blockLen=count*sizeof(int8_t)`，单位字节，最大 4096B，小于 A3 单块 \(2^{21}\) 字节限制。
- `DataCopyExtParams{1, validBytes, 0, 0, 0}`，GM→UB 使用无 mode 的 `DataCopyPadExtParams<int8_t>{false,0,0,0}`；UB→GM 不传 pad 参数。
- UB 申请按最大 T 对齐，尾部只搬运和计算有效 count；不将对齐长度扩成 GM 有效范围。
- `isPad=false` 不代表 dummy 为零；本方案不消费 dummy。
- 继续使用 count 重载，不手工将 count 塞进 mask/repeat，也不触碰 255-repeat 字段上限。
- 输入、输出和三个 half 临时区均独立，不依赖未知的部分重叠支持。

## 5.3 数值证明与验证要求

对任意 \(a,b\in[-128,127]\)，令 \(h\) 和 \(f\) 分别为精确 half、float 表示：

\[
h(a),h(b),f(a),f(b)
\]

均无表示误差，且顺序一致。因此：

\[
\operatorname{int8}(\max(h(a),h(b)))
=
\operatorname{int8}(\max(f(a),f(b)))
=
\max(a,b)
\]

输出始终在 int8 范围内。RINT 不改变这些整数。该证明不依赖 case 6 的随机分布，也不适用于任意 float→half→float 往返。

未来验证应包含：

- 完整 20-case，检查未变分支的回归；
- int8 的 65,536 个输入值对，覆盖相等、-128、127、正负交叉；
- 长度 1、31/32/33、4095/4096/4097、多个 tile、非整齐核分区及重复运行；
- 资源和最后消费者检查，确认临时区无跨 tile 污染。

全值对测试是补充，不替代实际 kernel、分区和原 oracle 的完整验证。

## 5.4 P/O 正文怎样实际影响了选择

- **P `elementwise/templates/continuous.md`**：要求分区与 tile 分开计数、按真实物理槽和转换区计字节；因此保留现有 owner 和 T，不夹带增核或双槽。
- **P `broadcast.md`**：使广播替代按真实零 stride、源块和展开块分别建账；拒绝将 513 元素源简单 padding 后冒充合法 axis=0 原始 shape。
- **O `vector-api/recipes/cast.md`**：只允许删除经值域证明不承担可见舍入的转换；因此选 int8 全域精确链，不删 BF16 的 float 路径，也不把 int64 转 float。
- **O `precision-boundaries/numeric.md`**：Max 与三元选择不能按名字互换；因此广播替代计入 NaN、相等值和符号零的专门核验，而不是承诺一次 GT+Select 已完整等价。
- **O `compare-select-tail.md`**：256B Compare、模式2 predicate 和 8KB 临时区进入了替代方案成本，直接影响本轮排序。
- **O `buffer-lifetime/reuse.md` 与 fallback**：独立分配不会因逻辑生存期结束自动共享；因此本轮使用独立 half 区，不虚报 alias 节省。
- **O `valid-length.md`、`bounds.md`、搬运正文**：保持有效 count、对齐存储和 DMA 字节各自计数，禁止通过补齐 GM 范围减少尾处理。
- **流水正文及历史案例**：支持未来比较物理双槽，但不允许借 sigmoid/exp 的历史倍率推断 maximum 收益；本轮不叠加无必要依赖的流水变换。

**知识缺口说明：**本输入没有提供可实际运行的 router、条目 frontmatter 的完整版本/hash、安装 SDK 支持表及构建配置。本文完成的是基于所给正文的人工路径选择与必要内容快照，不声称执行过 retrieve/route、schema 校验或代码审查工具。P v0003、O v0006 是材料声明的知识版本，不能据此编造单条目 hash。当前没有注册意图缺口；正式实施资格仍受具体 SDK 与容量门禁约束。

---

# 6. 下一轮可复用的三部分简短摘要

## 当前状态

- 授权范围：一轮、只读纸面分析；禁止工具、修改、编译和硬件测试。
- 保留实现：输入原始源码，baseline 仅为 assumed，未证明正确或性能。
- 选定方案 `R1-S1`：同形 int8 精确 half Max 链；计划 `R1-P1`，一个 `action.coalesce_cast` 实例。
- 结果：**not_measured / not_implemented**；没有候选 binary、正确性结果、加速比或正式接纳。

## 已尝试路线

- 仅完成静态比较及 C2/C3 交接，没有实际 patch 或运行 attempt。
- 静态预测：case 6 每元素六次 Cast 降为三次；可见 UB 69,632B→36,864B；必要 GM 字节不变。
- 未回答：目标 SDK 合法性、完整资源、编译后指令变化及净 Task 收益。

## 剩余机会

- 最强替代：case 11/12/20 的 float32 广播连续段/短行批量化；需兑现 Compare 256B 域、predicate、8KB Select 临时区和 NaN 语义。
- 残余 Scalar：case 13 int32、case 5/19 int64；不能借 half/float Compare 组合直接覆盖。
- 其他有据方向：case 18 的 B 驻留，同形多 tile 的物理双槽/流水，以及容量允许的 tile 摊销。
- 正确性边界：通用 half 广播未被专用分支覆盖，浮点特殊值尚无目标验证。它们需保留为独立问题，不能被本轮 int8 方案的潜在成功掩盖。

下一轮若允许实施，应先补 **SDK/API、可用 UB 与预留、构建身份**，再按冻结计划实现一次完整候选；完整正确性通过之后才进入有效计时。当前没有任何测量支持“已加速”或“机制已证实”的结论。