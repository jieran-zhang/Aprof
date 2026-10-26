## 结论与本轮状态

**本轮选择：在保持现有分核、坐标算法、间接取数和数值顺序的前提下，将三线性插值的逐元素 FP32 乘法与累加改为 UB 上的批量 Vector 计算，并统一按有效长度写回。**

这是一个注册 `action.vectorize_scalar_loop` 实例可以完整表达的方案；暂存、FP16 最终转换、连续写回和尾块是其必要实现步骤，不另凑 Action。

选择状态为 **`conditional_plan`**：
- 已形成源码可对应的 C2/C3 纸面方案；
- 实际 SDK、可分配 UB、浮点执行模式和编译分支尚未核验，实施前必须补齐；
- 不编译、不改文件、不调用 router 或其他工具、不测硬件；
- 正确性、性能均为 **`not_measured`**，原工程也不能据本次阅读标记为已通过。

下面的方案、计划和实例名称只是本文内的纸面身份，不表示已经生成文件、hash 或机器交接回执。

---

# 1. 当前实际执行过程及关键源码事实

## 1.1 算法与数值契约

令输入空间大小为 \(I=DHW\)，输出空间大小为 \(S=DoHoWo\)，输出元素数为 \(M=NCS\)。

每个输出 `Y[n,c,p]`：

1. 从 `grid[n,p,0:3]` 读取归一化的 `(x,y,z)`；
2. 按 `align_corners` 反归一化；
3. 执行 zeros、border 或 reflection 坐标处理；
4. nearest：三个轴 round-to-nearest-even，读一个体素；
5. bilinear：实际为三线性插值，按固定次序读取八个邻点并累加；
6. FP16 输入先扩成 FP32，坐标、权重及累加均为 FP32，最终输出缩回 FP16。

定义见 `docs/.../grid_sampler_3d_definition.md:14–34`，实际实现见 kernel `:44–134`。

**影响优化的数值事实：**

原三线性每一项执行的是：

```text
((sample * wx) * wy) * wz
result = result + term
```

八项顺序固定为 `000,001,010,011,100,101,110,111`，见 kernel `:125–132`。不能直接替换为预先计算 `wx*wy*wz`，也不能改为可跳过零权重的“稀疏求和”：例如有效样本为 Inf、权重为零时，原路径仍会产生 IEEE 特殊值行为。

## 1.2 Host、分核与启动

`op_host/grid_sampler_3d.asc`：

- 校验、解析 shape/dtype/属性后查询 `ACL_DEV_ATTR_VECTOR_CORE_NUM`，不是固定核数，见 `:45–53`。
- X、grid、Y 和 tiling 分别分配 GM；没有算法 workspace，见 `:54–65`。
- 只启动一次 `grid_sampler_3d_kernel`，随后同步 stream，再 D2H，见 `:66–74`。
- `data_utils.h` 只是文件读写，不参与设备计算。

tiling 使用连续输出线性分区：

\[
B=\min\left(A,\left\lceil M/a\right\rceil\right),\quad
L=\operatorname{AlignUp}\left(\left\lceil M/B\right\rceil,a\right)
\]

其中 FP16 的 \(a=32\) 元素，FP32 的 \(a=16\) 元素，即源码注明的 **64B GM owner 边界**。block \(b\) 拥有：

\[
[bL,\min((b+1)L,M))
\]

见 `grid_sampler_3d_tiling.h:40–45`。这些区间互斥并覆盖输出；极端小任务下，取整可能让末尾 block 无有效输出，kernel 会跳过循环。

没有跨核部分和、原子或归并。

## 1.3 实际两条 dtype 路径

| 路径 | 实际计算与数据流 |
|---|---|
| FP32 | 每个输出调用 `GridSampler3DOne<float>`，标量 GM 读 grid、标量随机读 X、标量计算、直接标量 GM 写 Y，kernel `:138–148` |
| FP16 | 每 tile 最多 1024 输出，仍逐元素标量调用 `GridSampler3DOne<half>`；FP32 结果逐个 `SetValue` 到 UB，再 Vector Cast、DataCopyPad 写回，`:151–188` |

FP16 显式用户 UB 数据区为：

\[
1024\times4+1024\times2=6144\text{ B}
\]

它不是“计算已经向量化”：**Vector 只承担最终 Cast，三线性主体仍是 Scalar。**

FP16 每 tile 有三次 `PipeBarrier<PIPE_ALL>()`：
- Scalar 写 FP32 UB → Cast；
- Cast → MTE3 写出；
- MTE3 读完输出槽 → 下一轮复用。

见 `:170–177`。源码没有双物理 buffer 或预取。

按提供的 `910c-hardware.md`，本 kernel 的 `__attribute__((aiv))` 对应 AIV；VECCALC/VECOUT 等均为 UB 标签，不是不同物理层级。当前没有 AIC、L1/L0 或 Cube 通路。

## 1.4 会改变选择的 workload 差异

- **三线性共 14 case**：1、2、4、6、7、9、10、11、13、14、16、17、19、20。
- **nearest 共 6 case**：3、5、8、12、15、18。
- 三线性源码每输出有 **24 次乘法、8 次累加**，另有坐标计算、边界检查和最多八次 X 读取。
- case17 输出约 **1.92048 亿元素**；case20 约 **6351 万元素**。其三线性数据算术工作规模使“只缓存几个 tiling 字段”不足以自动成为优先方向。
- case5 虽是大任务，输出有 **6710 万元素**，却是 nearest；本轮方案不解决它的坐标、reflection 和随机取数成本。
- case12 输入宽 4001，输出空间只有 \(7\times13\times17=1547\)，不能把输入、输出空间大小混用。
- case7/9/10/11/17/19/20 等有奇数尺寸，必须保留非整齐尾部。
- case13、14 要检查 Inf/NaN；case11 有 FP16 最大有限值量级。
- case15 的零值范围不是 Host 语义保证，不能据 case ID 做零填充特判。

矩阵与 `scripts/cases.py` 相符；但未提供实际输入生成结果，因此特殊值范围不能被解读为已经确认的特殊值分布。

### 继承的正确性疑点

定义支持特殊值传播，但 `GridFloor`、`GridRoundEven`、reflection 都涉及浮点转整数；**非有限 grid 坐标、或超出整数可表示范围的极端坐标，当前可见代码没有闭合处理契约**。原 20 case 的 grid 范围为有限的 `[-1,1]`，不能据此声称完整 API 的这一域已经正确。本轮不夹带修复，也不将它静默排除出接口。

---

# 2. 方案选择与最强替代比较

## 2.1 所选方案：三线性算术批量化

每个现有 owner 内按连续输出 tile：

1. **仍按原顺序标量生成每个输出的几何信息和读取八个样本**；
2. 将八路样本及六路轴权重分别写入连续 FP32 UB 数组；
3. 用 Vector `Mul`、`Add` 对整个 tile 执行原八项运算；
4. FP32 直接批量写出；FP16 保留最终 Cast 后写出。

不改变：
- 每个输出的 grid 地址、X 地址、输出地址；
- 坐标反归一化、reflection、floor、nearest 舍入；
- 八邻域读取顺序和每项乘法顺序；
- 每输出唯一写者；
- nearest 实现。

### 工作变化

对三线性有效元素数 \(M_b\)，tile 总数为各 owner 的 `ceil(ownerLength/T)` 之和，记 \(Q\)。

| 项目 | 原实现 | 候选 |
|---|---|---|
| 三线性数据算术 | Scalar 24\(M_b\) 次乘、8\(M_b\) 次加 | 每 tile 24 次 Vector Mul、8 次 Vector Add，内部有效算术量不变 |
| grid/X 逻辑读取 | 每输出 3 个 grid 值、最多 8 个 X 值 | 不变 |
| UB 暂存写入 | FP16 每输出写一次结果；FP32 无此暂存 | 每输出写 8 个样本、6 个轴权重，另初始化累加值 |
| 输出写入 | FP32 逐元素；FP16 已批量 | 两 dtype 均按连续有效段写出 |
| 转换 | FP16 标量扩位、末端批量缩位 | 保留，不宣称消除 Cast |

**预测**：显著减少三线性数据算术的 Scalar 发射工作，并减少 FP32 输出标量 store。  
**竞争代价**：增加大量 Scalar→UB 写入、UB 本地读写、Vector 调用与依赖屏障；随机源读取和坐标处理完全保留。净收益未知。

## 2.2 最有竞争力的替代：跨通道复用几何

源码的几何只依赖 `(n,p)`，不依赖 `c`；当前却为每个通道重复反归一化、padding、floor/round 和权重构造。

提供的 P 正文：

`indexing/templates/coordinate_neighborhood.md`

明确支持比较“复用轴块 × 空间块”，其几何构造次数可由：

\[
NCS \rightarrow NS\left\lceil C/C_t\right\rceil
\]

新增几何记录、读取、跨通道访问次序与任务数量代价。对 C=128/256 的 case3/5/6，以及 reflection case5/9/17，这是一项强机会。

**本轮不选它进入正式实施的原因不是收益未测，而是注册意图缺口：**

- 保存的是坐标、索引及权重等**派生数学状态**；
- 不能冒充 `reuse_input_tiles` 的原始输入值驻留；
- 也不能把整套插值预计算塞入 `hoist_invariant_control`。

这一边界同时由 `coordinate_neighborhood.md`、`buffer-lifetime/recipes/reuse.md` 和 `scalar-control/recipes/constant-lifetime.md` 正文明确指出。当前目录没有准确覆盖该独立变换的注册 Action。应保留为任务内提案，补注册意图后再与本轮候选竞争，而不是借联合方案夹带。

即使只驻留原始 grid，也只能减少重复读取，不能同时把几何重算节省记入该 Action。

## 2.3 其他主要竞争机会及处理

| 机会 | 源码与正文判断 | 本轮处理 |
|---|---|---|
| 标量地址解码、热点字段缓存 | `problem.control_metadata_overhead.md` 与 `hot-loop-address.md` 支持按连续段减少除模；当前每输出有线性解码，编译器 CSE 未知 | 可行的低资源替代，但只处理控制，不消除大规模数据算术；暂缓，不附带加入 |
| FP32 批量写回 | `problem.fragmented_writeback.md`、`memory-transfer/coalesce.md` 支持同 owner 连续输出汇总 | 已成为所选 Vector 结果的必要搬出方式，不另登记一个重复收益成员 |
| FP16 缩窄同步/双槽流水 | `problem.excessive_sync_scope.md`、`problem.pipeline_serialization.md` 支持按真实完成边比较 | 当前主要计算仍是 Scalar，且没有规则输入 DMA 阶段；不是给输出加两槽就能隐藏随机取数。本轮保留保守同步 |
| X 连续窗口/strided 搬入 | `problem.noncontiguous_access.md` 明确数据相关稀疏读取不能由输出连续推成源连续；`strided-pad.md` 不支持任意 gather | 不采用；整行/窗口载入会新增未用字节，当前无邻域局部性证据 |
| L2 hint/访问顺序 | `problem.cache_policy_mismatch.md` 与 `cache-hint.md` 要按 tensor 复用判断；X/grid 当前为裸 GM 标量指针，不能拿 GlobalTensor hint 配方直接证明这些访问受控 | 不改缓存；尤其不能统一 DISABLE |
| 增核、尾块均衡、shape 分派 | 当前已查询核数并线性切分；`underused_task_parallelism`、`core_tail_imbalance`、`dynamic_shape_mismatch` 正文不足以从“shape 多”推出新策略 | 无足够结构理由新增分派或动态调度 |
| Cast 合并 | `problem.redundant_cast.md`、`vector-api/cast.md`：当前扩位及最终缩位承担契约，没有已证冗余链 | 不删转换 |
| Cube、融合、归约、workspace、bank/spill | 当前单 AIV kernel，无 GM 中间张量、跨核归约或矩阵块；UB bank/spill 缺实际地址/编译证据 | 对应正文限定了适用条件，不能作为当前已成立机制 |

其中，八项局部累加不等于应切成跨核归约；将它矩阵化还会引入 gather/布局、填充及特殊值约束，Cube/Fixpipe 和 CV 资料不能证明这种改写值得或等价。

---

# 3. 注册 Action 实例与依赖

## 实例 `GS3D-R1-A1`

- **注册 ID**：`action.vectorize_scalar_loop`
- **方案身份**：`GS3D-R1-trilinear-vector`
- **target**：`GridSampler3DOne` 中 `GRID_BILINEAR` 的八邻域 FP32 乘法/累加，以及其结果输出
- **stage**：AIV kernel 内三线性数据计算
- **workload**：FP16/FP32，zeros/border/reflection，align_corners 两种取值；当前矩阵实际优化覆盖上述 14 个 bilinear case
- **implementation**：输入所给 kernel `:119–132`，及两条调用/写回路径 `:138–188`
- **family 提示**：indexing；执行提示为 Vector/API、有效长度、精度边界、连续写回
- **状态**：条件化纸面实例，未正式路由、未实施

### 当前版本前提核验

| 前提 | 判断 |
|---|---|
| `symptom.source.scalar_element_loop=true` | 源码成立：两 dtype 的三线性主体均逐元素执行 |
| `constraint.semantic_equivalence` | 原运算图、顺序、边界值可以逐项绑定；目标 SDK 浮点执行模式及实际编译仍待核验，不能填写无条件已通过 |
| `constraint.capacity` | 已有准确容量公式，目标可用 UB 与隐含预留未知，条件成立而非当前 true |

适用不变量：
- 完整语义、精度不变；
- 有效输出完整覆盖且唯一写回；
- UB 容量、Scalar/V/MTE3 依赖与所有权合法。

**必要依赖不是其他 Action，而是实现步骤保证：**
1. 原样坐标/读数阶段为每个有效 lane 定义全部 14 路输入；
2. Scalar 写 UB 完成后才能启动 Vector；
3. 完整八项累加完成后才能转换/写出；
4. MTE3 最后读取完成后才能覆盖输出区。

性能 `scalar_hot`、收益大小、实际 bubble 均保持未知。注册目录是本轮条件依据；Problem 正文中的历史 profile 前提不能重新加回，也不能伪造为 true。

---

# 4. C2 共同计划、资源与 KEEP 判断

## 4.1 共同骨架

**计划身份：`GS3D-R1-P1`，目标平台由任务绑定为 910C/dav-2201；不是设备探测结果。**

- 保留原 blockNum/blockLength 公式、输出线性 owner 和单次 AIV launch。
- 每个 owner 按连续输出段分 tile，tile 可跨通道或 batch 边界；每个 lane 仍独立使用原地址公式。
- 不新增 GM workspace：`workspace_bytes=0`。
- 不新增跨核通信、原子或归并。
- nearest 保留原实现。
- 三线性先标量准备输入，再 Vector 运算，最后有效段搬出。

### P 模板采用

主参考是 `coordinate_neighborhood.md` 的：

> 输出连续空间块、独立生成几何。

绑定为：
- G：kernel `GridUnnormalize`；
- B：`GridApplyPadding`/`GridReflect`；
- H：原 floor、六轴权重、八邻点及原有效判界；
- F：从 +0 开始、固定八项、每项三次顺序乘法后加到 FP32 状态。

这里**不采用其跨 c 几何驻留变体**。原 block 可能跨多个 n/c，规划时只是将其看作相邻独占子段的组合，不把 GatherElements 的同形索引语义移植过来。

## 4.2 联合资源账

采用独立、无别名分配，令 \(A(x)=AlignUp(x,32)\)。

| 对象 | 数量及大小 | 生命周期 |
|---|---:|---|
| 八路邻点值 | \(8A(4T)\) | Scalar 准备至对应 Vector 最后读 |
| 六路轴权重 | \(6A(4T)\) | Scalar 准备至八项全部消费完成 |
| term 临时区 | \(A(4T)\) | 每项三次 Mul 至本项 Add 完成 |
| FP32 累加/输出区 | \(A(4T)\) | 初始化至 FP32 搬出或 FP16 Cast 读完 |
| FP16 输出区 | FP16 分支 \(A(2T)\) | Cast 写入至 MTE3 读完 |

因此：

\[
U_{\rm FP32}=16A(4T)+U_{\rm extra}
\]

\[
U_{\rm FP16}=16A(4T)+A(2T)+U_{\rm extra}
\]

`U_extra` 包含实际 API 临时区、框架/编译器保留及其他真实分配，不能默认为零。

纸面起始候选 **T=1024**：
- FP32 显式数据区 65,536B；
- FP16 显式数据区 67,584B。

许可参数为 `T∈{256,512,1024}`，实施时满足：

\[
U_{\rm dtype}(T)\le U_{\rm plan}\le U_{\rm available}
\]

T 取 32 元素的倍数，保持现有 64B owner 边界内的整 tile 写回。该集合是有界实现选择，不是最优参数结论；没有容量证据时不得承诺 T=1024 可分配。

**不做 buffer alias**：term、acc、样本与权重可能同时存活。`buffer-lifetime/reuse.md` 的最后消费者规则使本轮选择独立区，而不是为省 UB 引入另一风险方向。

## 4.3 分派与边界

- 继续使用现有直调 entry：`grid_sampler_3d_kernel`。
- 只在既有 dtype/interpolation 分支接入候选；padding/align 保持原参数化路径。
- 不新增生产 Tiling Key、shape 阈值或 case 特判。
- 直调工程不使用 `TILING_KEY_IS`，依据 `tiling-tail/recipes/dispatch.md` 的明确限制。
- 若记录系统需要 group/key，可将现有 dtype×interpolation 四组赋予逻辑标识；这些不是新增 kernel ABI 或性能分派条件。

原通用路径保留为显式可恢复父本；不能候选失败后悄悄改跑旧实现并计入候选结果。

## 4.4 KEEP 判断

- **不是 P_KEEP**：没有输入提供的完整冻结计划可引用，而且本轮新增 UB 数据布局及 Scalar→Vector→MTE3 通路。先提取原计划，再记录实际改变；不能将“提取原计划”统计成并行收益。
- **A1 不是 O_KEEP**：明确要求替换三线性算术实现。
- nearest 是保持原样的域，不是另一个必须登记 O_KEEP 的成员。
- 因此本轮不是 NOOP，但目前只是纸面 P_CHANGE/O_CHANGE 意图。

越过以下边界必须返回 C2：改 owner、跨 c 几何复用、跨核共享表、GM 几何 workspace、改变累加顺序、增加预取槽或同步拓扑、改变 dispatch 域。

---

# 5. C3 具体实现交接与 API/数值约束

## 5.1 修改步骤

### 步骤一：保留父本与 ABI

保留原 kernel 为分析父本，沿用 `GridSampler3DTilingData` 字段及 Host 序列化，不为本轮增加 shape 特化。正式实施时记录分析父本与实际候选的不同源码身份；本轮没有计算 hash。

### 步骤二：拆出“准备一个三线性 lane”

从原 `GridSampler3DOne` 的 bilinear 部分提取：

- 原线性解码；
- 三个 grid 读取与手工 FP16 扩位；
- 原坐标变换、padding、floor；
- `wx0/dx、wy0/dy、wz0/dz`；
- 八次原 `GridRead<T>`。

按 lane 索引写入八个样本数组、六个权重数组。

重要限制：
- 无效邻点仍先判界，再返回 `+0.0f`，禁止先越界读取后 mask。
- border/reflection 后的 `x1/y1/z1` 仍可能越界，不能无条件 clamp 所有邻点读取。
- 不跳过零权重邻点。
- 不将八邻域合为预乘权重。
- 本轮不替换 `GridToFloat<half>`，避免同时引入次正规数/NaN 转换行为变化。

### 步骤三：分配与位置

全部 `InitBuffer` 只在 Init 阶段执行一次：

- 样本、权重、term：VECCALC；
- FP32 结果及 FP16 缩位结果：使用所选搬出重载明确支持的 VECOUT；
- 一个 TPipe 管理，不构造未经预留的固定 UB 地址；
- 数据区互不重叠，不依赖部分原地 alias。

`InitBuffer` 的长度单位为字节；`Get<float>(T)` 的长度单位为元素。来源是 `910c-hardware.md`、`buffer-lifetime/reuse.md`，不能把 `16T` 个 float 写成 `16T` 字节。

### 步骤四：执行原算术图

对 `v=min(T,end-offset)>0` 个有效元素：

1. 将 `acc[0:v]` 初始化为 `+0.0f`。最保守实现可使用原工程已有的 `SetValue`；这 **v 次标量初始化必须计入代价**，不假设免费。
2. Scalar 准备完成后保留本核 `PipeBarrier<PIPE_ALL>()`。
3. 对八项依次执行：

```text
Mul(term, sample[k], wx[k], v)
Mul(term, term,      wy[k], v)
Mul(term, term,      wz[k], v)
Add(acc,  acc,       term,  v)
```

每条存在真实 V 读写依赖的位置使用 `PipeBarrier<PIPE_V>()`。`term` 的原地 Mul、`acc` 的原地 Add 必须按安装 SDK 的具体 alias 契约核验；若不能证明，则在 C2 容量账内增加独立 ping-pong 临时区并重新审查，不能猜测合法。

这里的 `wx[k]` 等是本文数学映射，不是虚构 SDK API。

所采用的真实计算接口是：

```cpp
AscendC::Mul(dst, src0, src1, validCount);
AscendC::Add(dst, src0, src1, validCount);
```

`validCount` 单位为元素，不是 mask/repeat。`vector-api/batch.md` 提供 count 与 repeat 的区别：普通 FP32 一 repeat 为 64 元素，显式高维 repeat 上限 255；本方案优先 count，不手工拼长 mask。

### 步骤五：转换与有效写回

FP16：
```cpp
AscendC::Cast(raw, acc, AscendC::RoundMode::CAST_NONE, v);
```

保留原工程模式。`vector-api/cast.md` 与 `precision-boundaries/numeric.md` 明确：这里 `CAST_NONE` 不代表无舍入，不能随意替成其他模式。

两 dtype 的搬出分别构造：

```cpp
AscendC::DataCopyExtParams cp{1, validBytes, 0, 0, 0};
AscendC::DataCopyPad(yGm[offset], outputLocal, cp);
```

约束：
- `validBytes=v*sizeof(outputType)`；
- `blockCount=1`；
- `blockLen` 为有效字节，满足该重载字段范围及 `<2^21`；
- UB 首址 32B 对齐，分配按最大 T 对齐；
- 不增加 GM 写入长度；
- 输出就绪前、MTE3 最后读完后分别保留必要的保守全流水完成边；
- FP16 Cast 前也必须等待累加完成。

`memory-transfer/coalesce.md`、`valid-length.md` 和 A3 DataCopyPad 正文改变了这里的实现选择：**尾部使用有效字节搬出，而不是把 GM 长度向上补齐。**

不在本轮删除屏障或引入双槽；后续若做流水，需重新比较增加的事件、物理槽和缩 tile 成本。

## 5.2 精度约束与验证交接

必须沿用 `scripts/verify_result.py`，不改门限：

- FP16 threshold：\(2^{-10}\)，absolute floor：\(2^{-9}\)；
- FP32 threshold：\(2^{-13}\)，absolute floor：
  \[
  \max(2\times10^{-6},4\epsilon_{\rm FP32}\max|x_{\rm finite}|)
  \]
- `mere < threshold` 且 `rel_max < 10*threshold`；
- NaN、正 Inf、负 Inf mask 分别完全一致。

`exact_match` 是报告字段，不是当前脚本的唯一通过条件。

额外应覆盖：
- `v=1`、32B 边界附近、T−1/T/T+1；
- owner 起点、末核和空 owner；
- tile 跨 c/n 边界；
- nearest ties-to-even 保持不变；
- 三轴边界、尺寸为 1、重复 reflection；
- 大值抵消、±0、次正规数、Inf×0、NaN；
- 非有限 grid 的继承缺口单列，不通过修改 oracle 掩盖。

不能仅凭“都用 FP32”宣称等价。实际 Scalar/Vector 的 FTZ、饱和、编译浮点重排和 FMA 策略需要结合 SDK/编译条件核验，完整 oracle 才能给正确性结果。

## 5.3 P/O 正文如何实际影响了选择

不是只列路径，关键影响如下：

1. **`coordinate_neighborhood.md`**  
   使跨 c 几何复用进入强替代比较，但其“派生状态不等于原输入驻留”限制阻止错误套用 Action；本轮采用不共享几何的连续输出骨架。

2. **`vector-api/batch.md`、`cast.md`**  
   决定优先使用连续 count 接口，保留 FP16 最终舍入边界，不把当前一次 1024 元素 Cast 误诊为 Vector 碎片化。

3. **`compare-select-tail.md`**  
   A3 Compare 的完整 256B 执行域、Select 模式及 8KB 临时区表明：若连 padding/clamp 也向量化，会新增明确工作和容量。本轮不顺手加入 Compare/Select；保留原标量边界函数。

4. **`memory-transfer/coalesce.md`、`strided-pad.md`**  
   前者支持连续输出批量写回；后者明确规则 stride 不能表达任意 X gather，故不将随机读伪装成多块 DMA。

5. **`buffer-lifetime/reuse.md`、`pipeline-sync/pipeline.md`**  
   决定按物理分配和最后消费者记账，初版保留独立区及保守完成边；不将“变量不再使用”当作 DMA 已结束。

6. **`precision-boundaries/numeric.md`、Cube/Fixpipe/CV 正文**  
   保留三次顺序乘法、八次顺序累加和特殊值检查；当前没有矩阵数据流，不能借 Cube 例子得到采样算子的实现资格或收益结论。

提供的 P 模板自称条件化推导，并非现成 GridSampler 实现。本文没有运行 P/O router；条目版本/hash、正式 handoff/v4 和 action-decision/v3 校验仍未生成，不能称为已完成机器准入。

---

# 6. 下一轮可复用的三部分简短摘要

## 当前状态

- 外部授权：一轮只读方案分析及 C2/C3 纸面交接；禁止工具、改工程、编译和硬件。
- 原始基线保持不变；没有候选源码、二进制或通过正确性的探索父本。
- 目标 910C/dav-2201 来自任务约束。实际 SDK、编译目标、可用 UB/核数未探测。
- 本文选定 `GS3D-R1-trilinear-vector`，状态 `conditional_plan`；正确性、性能均 `not_measured`。

## 已尝试路线

| 路线 | 本轮实际完成 | 限制 |
|---|---|---|
| 三线性 Scalar 算术向量化 | 源码工作量比较、单 Action 绑定、C2 资源/owner 计划、C3 API 与数值交接 | 未写代码、未审查编译产物、未验证正确性或收益 |
| 跨通道几何复用 | 确认几何不依赖 c，形成有工作量公式的强替代 | 缺准确注册意图；没有冒充输入驻留或控制外提 |

## 剩余机会

- **先补实施合法性**：SDK 支持与 alias 契约、实际 UB 预算、Scalar/Vector 浮点模式；然后才可实施本轮方案。
- **仍未解决**：nearest，特别是大 case5；所有路径的坐标重算、随机 X 读取和 FP16 标量扩位。
- **可能改变后续选择的事实**：
  - 若新增 UB 写入/Vector 依赖成本抵消 Scalar 算术减少，应重开地址控制或几何复用方案；
  - 若几何复用注册意图补齐，需重新比较其任务数、状态容量和跨通道访问代价；
  - 若编译证据表明控制字段已被外提，不再把源码重复字段计作独立收益；
  - 若发现原基线数值缺陷，先区分继承问题与候选引入问题。

**最终限制：本轮证明的是方案结构、工作量关系与条件边界，不是目标设备的瓶颈、正确性通过或加速比。**