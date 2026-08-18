# Source Hypothesis Routing

本文是 seed SkillGraph 的人读 expert-prior source。它帮助 `aprof-diagnosis-agent` 在只有 kernel 源码时，把代码形态映射到一个或多个 anchor facets、provisional mechanisms 和优先硬件 metric。源码阶段只产生证据，最终 route 必须由发布图和 runtime 记录。

## 路由原则

- 先找最强源码证据：循环结构、DataCopy 粒度、buffer/queue 配置、同步、API 调用路径、blockDim/tile 参数。
- 再映射到现有 6 个非互斥 facets：`tiling`、`data_movement`、`pipeline_parallel`、`onchip_memory`、`ai_core_utilization`、`api_algorithm`；它们不是根因标签。
- 最多保留 3 个假设，最多选择 3 个 metric。
- 优先选择能区分多个假设的 metric，例如 `PipeUtilization.csv` 的 pipe 占比、`Memory.csv` 的搬运粒度、trace 的重叠率。
- 涉及 `blockDim`、UB 占用或 AI Core 利用率时，先记录 shape/dtype/total elements；最终判断必须交给 workload-aware predicate 和 graph route，不得仅凭低利用率下结论。
- 若源码或 profiling 已经呈现 Scalar / Memory / Vec / CUBE / no-bound 现象，读取
  [bound-deep-routing.md](bound-deep-routing.md) 做二级分流；仍然把输出落到六类 problem family。
- 不直接打开 CANNBot 大型 `SKILL.md`。只有 AProf 本地 reference 明确需要 API 或算子族细节时，才按
  [cannbot-knowledge-index.md](cannbot-knowledge-index.md) 点读单个具体 reference。

## 源码模式映射

| 源码模式 | 可能问题族 | 优先 Metric | 需要的数据 |
| -------- | ---------- | ----------- | ---------- |
| `blockDim` 固定，未随 shape / tile 数变化 | `tiling`、`ai_core_utilization` | 核利用率、头开销占比、核间耗时不均衡、每核元素数 | `OpBasicInfo.csv: Block Dim/Task Duration`、`PipeUtilization.csv`、平台核数、shape/dtype |
| `tileLength` 很小或 tile 循环层级很多 | `tiling`、`data_movement` | 单次搬入/搬出粒度、MTE 指令密度、MTE2/MTE3 Bound | `Memory.csv`、`PipeUtilization.csv`、shape/dtype |
| tail 分支复杂或最后一核单独处理大量剩余数据 | `tiling`、`ai_core_utilization` | 核间耗时不均衡、最慢核定位、tail case 对比 | `PipeUtilization.csv` 逐核数据、多 shape profiling |
| `DataCopy` 在内层循环重复执行，或中间结果频繁写回 GM/workspace | `data_movement`、`onchip_memory` | 读写流量放大、MTE2/MTE3 占比、单次搬运粒度 | `Memory.csv`、`PipeUtilization.csv`、理论读写量 |
| `InitBuffer(..., 1)`、缺少 DoubleBuffer、EnQue/DeQue/FreeTensor 顺序串行 | `pipeline_parallel` | MTE/Compute 重叠率、MTE wait、流水线气泡 | trace/timeline、`ResourceConflictRatio.csv`、`PipeUtilization.csv` |
| `SyncAll`、`WaitFlag`、`PipeBarrier` 在 tile 循环内频繁出现 | `pipeline_parallel`、`api_algorithm` | 同步等待占比、重叠率、各 pipe wait ratio | trace/timeline、`ResourceConflictRatio.csv` |
| LocalTensor 临时 buffer 多、UB/L1/L0 切分公式接近容量上限 | `onchip_memory`、`tiling` | UB/L1/L0 带宽、UB 冲突、buffer 占用与容量比 | `MemoryUB.csv`、`MemoryL0.csv`、`ResourceConflictRatio.csv`、平台容量 |
| 使用 Scalar 循环、逐元素 `GetValue/SetValue`、小粒度 Cast 或重复 Cast | `api_algorithm`、`ai_core_utilization` | SCALAR Bound、Vector 理论利用率、指令类型占比 | `PipeUtilization.csv`、`ArithmeticUtilization.csv`、代码片段 |
| MatMul/FA/GMM 中 Cube 循环和后处理配比不清，AIC/AIV 等待明显可能 | `ai_core_utilization`、`pipeline_parallel` | AIC/AIV 时间差、CUBE Bound、Fixpipe 占比、理论算力利用率 | `PipeUtilization.csv`、`ArithmeticUtilization.csv`、trace/timeline |
| CacheMode、切分轴或访问顺序可能破坏局部性 | `data_movement`、`onchip_memory` | L2 命中率、读流量放大、MTE2 时间 | `L2Cache.csv`、`Memory.csv`、shape/dtype |
| `SetFlag` 后立即 `WaitFlag`，或 pingpong 变量存在但无预取/稳态/收尾循环 | `pipeline_parallel` | overlap、wait ratio、PING/PONG gap | trace/timeline、`ResourceConflictRatio.csv` |
| 连续分配多个 UB buffer，Vector API 多操作数读写，或 `blk_stride` 呈周期值 | `onchip_memory`、`api_algorithm` | UB bank/resource conflict、Vector 理论利用率偏低 | `ResourceConflictRatio.csv`、UB offset/stride 公式 |
| 结构体数组动态下标、隐式状态机循环、hot loop 主尾分支混杂、大结构体/多级指针 | `api_algorithm` | Scalar LoadStore、ICache miss、Scalar time | `PipeUtilization.csv`、trace 指令类型、源码审查 |
| 多步 Vector 链中间结果 `CopyOut` 到 GM 后再 `CopyIn` | `data_movement`、`api_algorithm`、`onchip_memory` | 读写流量放大、MTE2/MTE3 高、UB 融合缺失 | `Memory.csv`、trace/timeline |
| MatMul MN 任务数不足但 K 很长 | `ai_core_utilization`、`tiling` | AIC 核利用率、K loop 长度、workspace reduce 需求 | shape/TilingData、`PipeUtilization.csv` |
| MatMul pingpong 已启用但 MTE2 PING/PONG 间存在确定 gap | `pipeline_parallel` | MTE2 preload gap、各 pipe busy 都不高 | trace/timeline |
| Softmax/FA S2 loop 内反复分配 max/sum/exp 状态 buffer | `onchip_memory`、`pipeline_parallel` | PipeBarrier 数量、UB resident 预算、MTE3 overlap | 源码、trace、UB 预算 |
| Sort/TopK 大数据多遍扫描且低位桶/稀疏输出走标量路径 | `api_algorithm`、`pipeline_parallel` | Scalar 高、SyncAll 等待、MTE2 多遍扫描 | trace、多 N 对比 |

## Metric 选择顺序

1. **全局定位**：`PipeUtilization.csv` 的 VEC/CUBE/MTE/SCALAR/Fixpipe 占比和逐核时间。
2. **搬运验证**：`Memory.csv` 的 GM↔UB 数据量、MTE 指令数、带宽利用率、主存读写量。
3. **流水验证**：trace/timeline 的 MTE 与 Compute 重叠率、同步等待、阶段串行度。
4. **计算验证**：`ArithmeticUtilization.csv` 的 Vector/Cube fops、指令类型占比、理论算力利用率。
5. **冲突与片上验证**：`ResourceConflictRatio.csv`、`MemoryUB.csv`、`MemoryL0.csv`、`L2Cache.csv`。

## 输出检查

`diagnosis_hypotheses.json` 中每个 metric 必须写清：

- 来源文件或 trace。
- 字段名或公式。
- 支撑哪个假设。
- 证据等级：`direct`、`derived`、`trace` 或 `source-hypothesis`。
- 对小 workload，metric 的 `diagnosis_use` 必须写清“验证是否超过 workload 可达上限”，不能写成“利用率低即问题”。
