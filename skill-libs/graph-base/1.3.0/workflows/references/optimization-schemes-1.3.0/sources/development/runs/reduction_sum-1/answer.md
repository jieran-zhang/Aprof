## 结论与本轮状态

**本轮选择保留当前实现，不安排性能改码。** 这不是因为“没有 profile 就不能优化”，而是当前固定 workload 已经采用单核全载、一次连续读入、一次批量 Sum、一次连续写回；源码中没有发现能够直接消除的重复读取、分段合并、碎片搬运或逐元素控制循环。

最值得保留的竞争方向是：**用基础四参数 `ReduceSum<float>` 实现短行归约，比较它与当前高阶 `Sum` 的固定开销。** 给定材料支持提出这个假设，但尚不能证明它减少工作：显式归约调用会从一次 Sum 变成三次 ReduceSum，还可能增加结果打包与同步；其 scratch 和紧凑输出地址合法性也未闭合。因此本轮不为它强行登记“归约策略失配”为 true。

以下给出可复用的源码理解、选择依据，以及 **C2/C3 纸面交接**。未调用工具、未修改文件、未编译、未测正确性或硬件性能；不声称完成正式 router、schema 校验或工程验收。

---

## 1. 当前实际执行过程与决定选择的源码事实

### 1.1 语义与实际输入输出

实际 kernel 为 `KernelMeanSum<float>`，名称虽有 Mean，但只执行逐行求和，没有除法：

\[
y[r]=\sum_{c=0}^{31}x[r,c],\qquad r=0,1,2
\]

证据：

- `sum.asc:151–153` 固定实例化 `float`。
- `sum.asc:78–81,114–116` 设置 `SumParams` 并调用 `AscendC::Sum`。
- `gen_data.py:46–63` 生成 float32 的 `[3,32]` 输入，参考结果按行递归二分求和。
- 输出物理长度为 8 个 float；前三个是归约结果，后五个 golden 为零。**这五个位置也被比较，不能把它们当作无需维护的不可见区域。**

生成器的输入是 `[-100,99]` 内整数转换为 FP32。对这一生成值域，任意子集和绝对值不超过 3200，远小于 FP32 连续整数精确表示范围，因此仅改变加法树不会产生整数舍入误差。不过：

- 这不是任意 float32 输入的等价证明；
- `fixed_sample=true` 不是输出常量化许可；
- 本次没有提供实际二进制输入内容，不能声称冻结了具体数值。

### 1.2 Host、tiling 与 launch

由 `GenerateTilingData` 得到：

| 字段 | 当前值 | 来源 |
|---|---:|---|
| `outter` | 3 | `M=3` |
| `inner` | 32 元素 | `PaddingAlign(32,4)` |
| `n` | 32 元素 | 实际归约长度 |
| `outInner` | 8 元素 | `PaddingAlign(3,4)` |
| `tmpBufSize` | 查询得到的 `minValue` 字节 | `GetSumMaxMinTmpSize` |

定位：`sum.asc:41–60,157–160`。

Host 分配输入 **384B**、输出 **32B**，执行一次 H2D、一次 kernel launch，流同步后 D2H 并比较，见 `sum.asc:217–238`。

`USED_CORE_NUM=1`，kernel 没有按 `GetBlockIdx()` 做偏移。**不能只把启动核数改为 3：那会让多个 block 处理并写回同一整块输出。**

### 1.3 核内数据流和生命周期

```text
输入 GM [96 个 float]
       │ 一次 DataCopy，384B
       ▼
VECIN / UB，单物理槽
       │ 输入队列交接
       ▼
Duplicate 输出 8 个 float 为 0
Sum：对 3 行分别归约，使用 VECCALC 临时区
       │ 输出队列交接
       ▼
VECOUT / UB，单物理槽
       │ 一次 DataCopy，32B
       ▼
输出 GM [8 个 float]
```

定位：`sum.asc:87–95,99–126`。

依据给定 `910c-hardware.md`：

- VECIN、VECOUT、VECCALC **都映射到 UB**，不是三个物理层级；
- GM→UB、UB→GM 分别属于 MTE2、MTE3 路径；
- 队列负责表达生产消费关系，不能由队列存在推断有效重叠。

当前只有一次 CopyIn→Compute→CopyOut，没有跨 tile 的稳态流水窗口。保留队列协议，不把没有手写 flag 解释成没有同步。

令 \(A(B)=32\lceil B/32\rceil\)，当前显式静态分配为：

\[
U_{\text{explicit}}=A(384)+A(32)+A(S_{\min})
=416+A(S_{\min})\ {\rm B}
\]

这里尚未包括未见的编译器/API 额外预留。独立 `InitBuffer` 不会因为生命周期不同自动共享物理空间。

### 1.4 可算出的工作，不等于实测工作

- 输入逻辑读取：384B，一次。
- 输出物理写回：32B，一次，其中有效归约值为 12B。
- 合计 kernel 可见逻辑 GM 请求：**416B**，不是 HBM 实测字节。
- 三行各 32 个数，数学二叉归约需要 \(3\times31=93\) 次加法；这不是当前 Sum 的实际指令计数。
- 显式初始化：8 个 float。前三个随后被 Sum 结果覆盖，但初始化后五个输出位置仍有契约作用。

关键未知：

1. 未提供本工程构建配置及安装 SDK 版本；目标 dav-2201 来自用户与 workload，不是设备探测。
2. 未提供 Sum 的具体内部实现和完整 API 正文，不能断言内部按行循环次数、临时区数值或输出 padding 写入行为。
3. 因而目前能恢复的是**源码预期路径**，不是已验证的设备执行结果。

---

## 2. 所选方案、最强替代及工作量比较

### 2.1 所选方案：保留单核全载批量 Sum

方案标识可记为纸面身份 `R1-retain-singlecore-fullload-sum`，不是已生成文件或 hash。

保持：

- 一个 AIV block，独占全部输入和完整 32B 输出；
- AR 归约，`A1=3、R=32、A0=1`；
- 整个矩阵一次搬入；
- 当前 Sum 调用、查询得到的最小临时区；
- 输出清零及一次 32B 写回；
- 原 Host 接口、tiling ABI、oracle 和容差。

**没有减少或新增执行工作，优化影响域为空；完整正确性责任仍覆盖 8 个输出元素。** 本轮价值是完成机会筛选和可复用交接，不宣称性能改善。

### 2.2 最强竞争替代：基础 ReduceSum 短行实现

给定 `reduction/templates/fullload.md` 明确提供基础接口：

```cpp
AscendC::ReduceSum<float>(
    resultLocal, xLocal[row * rAlign], tmpFloat,
    static_cast<int32_t>(rValid));
```

本任务可代入 `rAlign=rValid=32`，每行输入起点相差 128B，保留单核所有权，不需要跨核合并。

| 项目 | 当前 Sum | 基础 ReduceSum 替代 |
|---|---|---|
| 输入搬运 | 一次，384B | 可保持一次，384B |
| 显式归约调用 | 一次，包含三行 | 三次，每次 count=32 |
| 必要求和工作 | 三行归约 | 相同 |
| 临时区 | 当前查询的 `uint8_t` 区 | `LocalTensor<float>`，空间规则待核验 |
| 结果布局 | 当前直接生成输出布局 | 须证明结果目的地址约束及三结果紧凑打包 |
| 输出 | 一次，32B | 可以保持一次，但须维护五个零 |
| 可能收益 | — | 避免高阶通用参数/内部调度成本 |
| 新增风险 | — | 更多 API 发射、打包、局部完成边、不同归约实现 |

**暂不采用的理由不是收益未知，而是净工作变化尚不占优。** “高阶 API 较通用”只支持性能假设，不能推出三次基础调用更便宜。尤其不能直接假设 `resultLocal=dstLocal[row]` 对所有 row 都满足基础归约的目的地址约束。

未来若目标 SDK 正文和编译产物证明：基础接口可直接合法形成紧凑输出，且确实消除了显著的高阶固定工作，这个方向应重开。

### 2.3 其他会影响选择的机制

| 方向 | 源码证据与正文如何影响判断 |
|---|---|
| 按行增加到最多三核 | `problem.underused_task_parallelism.md` 要先看独立外轴，但也明确微小任务可能付不起并行成本。这里只有每行 128B 输入、一个标量结果；新增核还会拆散当前同 owner 的整块输出。暂缓，不把“只开一核”直接判为欠并行瓶颈。 |
| 沿 R 拆 partial | `reduction/templates/split.md` 要计 partial 写读、合并、同步及 launch。R 只有 32，原本没有 partial；该方案主要是在增加工作，不选。 |
| 合并搬运、合并写回 | `problem.tiny_transfer_setup_amplification.md` 明确单次全载不能仅因包小就推导可合并；`problem.fragmented_writeback.md` 明确标量归约输出小不等于碎片化。当前两方向分别已只有一次调用。 |
| 输入驻留、减少 GM 流量、链融合 | `input-tile-residency.md` 的 R=1 情形没有删读依据；当前也没有 GM 中间值或第二个 kernel。不能用“驻留”重复计一次已存在的输入全载。 |
| 双缓冲、预取、缩小同步 | `problem.pipeline_serialization.md` 与 `pipeline.md` 均要求有独立 next tile。当前只有一个全载批次；主动拆成三行会增加搬运/控制，不能只拿理想重叠模型算收益。Host 流同步保护结果回读，也不应删除。 |
| 控制外提、字段缓存 | `problem.control_metadata_overhead.md` 和 `tilingdata-access.md` 指向热循环重复工作。当前 tiling 只有五个 uint32 字段，按值传入并在 Init 中读取，没有可见热循环；不选“容易证明等价”的缓存动作。 |
| Cache hint | `problem.cache_policy_mismatch.md`、`cache-hint.md` 允许一次性流式输入比较 NORMAL/DISABLE，但单次 kernel 读一次不等于跨调用无复用。这里只有 384B 输入，也无竞争工作集证据，暂不优先。 |
| UB 复用、bank padding | `reuse.md` 要有真实不交叠生命周期及 alias 许可；Sum 期间输入、输出、scratch 均有用途。`arch22-bank-layout.md` 要看实际地址与内部 repeat，不能给高阶 Sum 随手加 32B padding。容量合法性未知也不能反推“容量压力”。 |
| Cast、广播、Compare/Select、Cube/CV | 当前实际路径没有这些运算或阶段。相关正文的 dtype、8KB Select 临时区、Fixpipe/跨核协议等约束不产生本任务的采用理由；不引入它们来处理简单 Sum。 |
| 输出尾部、初始化缩减 | 没有逐元素尾慢路径。前三个零可能被覆盖，但五个 padding 零必须维护；把整块 Duplicate 改成从 `dst[3]` 开始的短初始化，需要独立核验地址/mask，且可能增加调用。不能直接删除清零。 |

历史 exp、sigmoid、norm 案例仅用于理解 tile、槽数、partial 和失败归因边界，**其常量、倍率及验收状态均不迁入本任务**。

---

## 3. 注册 Action 实例与依赖

### 本轮正式拟采用实例：**零个**

本轮选择保留，因此不为了填交接表制造实例：

- 不把固定一核写成已确认的 `fixed_or_undersubscribed_tasking` 性能机制；
- 不把短 R 的高阶 Sum 自动写成 `reduction_strategy_mismatch=true`；
- 不把一次小写回写成 `fragmented_writeback=true`；
- 不把初始化前三个有效结果的位置写成可消除 GM 流量。

**注册意图边界：** 单纯“在相同全载、owner 和归约结构下，把 Sum 换成基础 ReduceSum”主要是局部计算原语替换。现有 `restructure_reduction` 更直接描述全载/切分及合并结构，`batch_vector_api_calls` 也不能准确描述“一次变三次”。若后续只有 API 替换而不改变分解，应明确补充意图归属，而不是借现有 Action 名称夹带实施。

没有成员间依赖。后续若重开基础 ReduceSum，必要依赖为：

1. 明确合法 Action 意图；
2. 目标 SDK 的基础 ReduceSum scratch、地址、别名和完成语义；
3. 三个结果到完整 8 元素输出的合法布局；
4. C2 明确许可归约实现及数值顺序变化；
5. 容量闭合后，才进入实际 C3。

这些是具体实施缺项，不是要求先测出收益。

---

## 4. C2 共同计划、边界、资源与 KEEP 判断

### 4.1 提取已有计划

纸面计划 `P0-extracted-AR-3x32`：

| 项目 | 冻结内容 |
|---|---|
| 适用域 | 用户给定 dav-2201、float32、物理 `[3,32]`、`n=32`、输出 8 元素 |
| 算法 | AR 全载，三行独立 sum |
| 任务与 owner | 一个任务、一个 AIV block，拥有三个有效结果及五个输出零位置 |
| 归约 | 保留现有 Sum 实现；不拆 R、不生成跨核 partial |
| 数据通路 | GM→UB→Vector→UB→GM |
| 同步 | 保留输入/输出 TQue 生命周期和 Host 流同步 |
| GM workspace | 可见源码未申请算法中间 workspace，记 0B；不等于断言无框架预留 |
| UB | `416+A(Smin)` B 显式分配，加必要隐含预留 |
| dispatch | 现有直调 `sum_custom`，一个 block；不新增 key/entry |

资源安全域写为：

\[
416+A(S_{\min})+U_{\text{extra}}\le U_{\text{available}}
\]

实际 \(S_{\min}\)、可用 UB、额外预留本次均未查询，不能填成某个 SKU 常量。不过本轮不增分配、不改变参数，也没有凭未知容量授权新特化。

### 4.2 P/O 正文采用关系

- **P：`reduction/templates/fullload.md`**  
  采用其 AR 行所有权、全载容量方程和有效/对齐长度分离原则。它使本任务归入“完整行能否容纳及 owner 是否合理”的判断，而非见到一核就 Split-R。
- **P：`reduction/templates/split.md`**  
  用其完整 partial→merge 成本排除本轮跨 R 拆分，不采用其执行结构。
- **O：`memory-transfer/recipes/coalesce.md`**  
  用其合法连续区间和调用计数核对，确认当前已有一次连续输入与一次输出，未发现合并余量。
- **O：`pipeline-sync/recipes/pipeline.md`**  
  用其单 tile 边界保留浅路径，而非追加两槽。
- **O：`precision-boundaries/recipes/{numeric,bounds}.md`**  
  保留有效 count、五个零输出、dtype、原容差与所有地址边界。
- **O：`buffer-lifetime/recipes/reuse.md`**  
  按独立静态分配计账，不以逻辑存活期推算出不存在的物理复用。

这是正文对当前选择的实际影响，不是声称执行了 router 命中或采用了所有变换。

### 4.3 KEEP 的准确表述

当前没有输入正式父计划，因此：

- 若按给定契约落盘，首次建立计划应记 **P_CHANGE：提取已有计划**，不能统计为并行优化。
- 在该计划身份及证据合法冻结之后，原样沿用才可记 P_KEEP。
- 本轮实现处置是“保留原源码”，不是用文档缺失或空路由冒充成员 O_KEEP。
- **本次不声称已经形成正式 `P_KEEP + 全成员 O_KEEP` 的 NOOP 回执。** 工程效果确实是零改动，但正式身份链尚未生成。

---

## 5. C3 具体交接：零改动执行，以及替代方案的实施门槛

### 5.1 本轮可执行的 C3 指令

1. **不修改** `sum.asc`、`gen_data.py`、tiling 结构及 launch。
2. 保留当前接口：
   - `GetSumMaxMinTmpSize(n, sizeof(uint32_t), false, maxValue, minValue)`；
   - `tmpBufSize=minValue`，单位为字节；
   - `Sum(dstLocal, srcLocal, sharedTmpBuffer, params)`；
   - 两次 DataCopy 的长度分别为 **96、8 个 float 元素**；
   - Duplicate 长度为 **8 个 float 元素**。
3. 保留 `SumParams{inner=32,outter=3,n=32}` 的字段解释。不得把输出对齐长度 8 用作归约 count。
4. 保留两个队列的 depth=1、物理槽数=1，以及独立 scratch；不删队列、不手工复用地址。
5. 不引入 `TILING_KEY_IS`。`tiling-tail/recipes/dispatch.md` 明确其宏不直接用于本类 kernel 直调工程；当前无需创建分派路径。
6. C3 状态记录为：**paper_only / unchanged / not_built / correctness_not_run / performance_not_measured**，不能记 completed implementation。

### 5.2 基础 ReduceSum 路线若获后续授权

可按以下顺序实施，但本轮没有实施：

1. 保持一次 384B 输入搬入和一个输出 owner。
2. 对 row=0、1、2 使用四参数基础接口，第四参数为 `int32_t(32)`，**不添加第五个 `false`**。
3. 使用该接口要求的 `LocalTensor<float>` 临时区；不能直接把当前 `uint8_t` scratch 当作空间和对齐已经满足。
4. 在接口正文核验结果目的起址、结果写入跨度和源是否可能被破坏；未闭合前不直接写 `dstLocal[row]`。
5. 选择合法的三结果打包方式，重新计算新增结果槽、打包操作及完成边；不能只比较归约调用。
6. 最终仍形成 `[sum0,sum1,sum2,0,0,0,0,0]`，一次写出 32B。
7. 若修改归约树或结果布局超出冻结自由度，返回 C2；不把局部 API 调优当作自动许可。

此路线具体缺的不是“泛泛 API 不明”，而是**基础归约临时区规则、目的布局限制及打包成本**。给定 FullLoad 正文提供了准确函数形态，但没有给出这些参数的完整规则，故不能凭经验填写 scratch 常数。

### 5.3 原始 oracle 和工程信任限制

后续验证需保留原 oracle，同时留意：

- `CompareResult` 比较全部 8 元素，判错条件为 `ae>1e-4 && re>1e-4`，不是单一绝对误差。
- NaN 可能绕过该比较条件；不能据现有比较器声称特殊值已验证。
- `ReadFile` 允许文件短于 buffer，并改写传入的 `fileSize`；Host 未检查输入读取返回值。后续应确认输入恰为 384B、golden 恰为 32B，并保存内容身份，避免短文件被误当候选错误或正确结果。
- 程序即使比较失败也返回 0，见 `sum.asc:250–255`；不能只凭退出码判定正确性。
- 这些是验收接入限制，本轮不把 I/O、验证器修改混入性能方案。

以后获得运行授权，应先完成目标构建/API 审查和完整输出正确性，再做同源 A/B；Task 时间与 Host 初始化、文件 I/O 时间分开。具体计时协议正文本次未提供，不补造采样数、异常阈值或加速门槛。

---

## 6. 下一轮可直接复用的三部分简短摘要

### 当前状态

用户只授权一轮纸面分析；未改码、未编译、未测硬件。当前保留原始 `reduction_sum/sum.asc`。workload 为 dav-2201、FP32 `[3,32]`，输出 8 元素全部可见。已恢复单核 AR 全载路径：一次 384B 读、一次 Sum、一次 32B 写；baseline 为 assumed，性能 `not_measured`。纸面计划为 `P0-extracted-AR-3x32`，尚无工具生成的 hash 或正式验收产物。

### 已尝试路线

仅完成静态比较，没有实现 attempt。选择保留当前全载批量 Sum。基础四参数 ReduceSum 为最强探索替代，但一次变三次调用，scratch、结果布局和打包成本未闭合；没有把它登记为已成立的归约策略失配。多核、Split-R、流水、缓存、复用、搬运合并和控制外提均按当前实际工作量比较后暂缓或判为结构不适用。

### 剩余机会

优先补齐基础 ReduceSum 的目标 SDK 契约，并检查当前 Sum 编译后的内部固定工作；若三次基础归约能合法直接形成紧凑输出、明显减少控制，则重开短行原语替换及 Action 意图归属。若未来 workload 增大，再重新比较外轴分核、批次大小与流水，不能沿用本次“微小任务保留单核”的结论。

**未测限制：** 当前无 baseline 正确性记录、实际 scratch 数值、构建/SDK 身份、UB 可用量、指令或 timeline 证据；这些不等于性能反证，也不构成任何加速、回归或正式接纳结论。