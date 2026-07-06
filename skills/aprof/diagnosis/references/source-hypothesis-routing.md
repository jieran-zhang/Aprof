# Source Hypothesis Routing

本文用于 `aprof-diagnosis-agent` 在只有 kernel 源码时，把代码形态映射到性能问题族和优先硬件 metric。源码阶段只产生假设，最终结论必须由 profiling 数据验证。

## 路由原则

- 先找最强源码证据：循环结构、DataCopy 粒度、buffer/queue 配置、同步、API 调用路径、blockDim/tile 参数。
- 再映射到现有 6 个问题族：`tiling`、`data_movement`、`pipeline_parallel`、`onchip_memory`、`ai_core_utilization`、`api_algorithm`。
- 最多保留 3 个假设，最多选择 3 个 metric。
- 优先选择能区分多个假设的 metric，例如 `PipeUtilization.csv` 的 pipe 占比、`Memory.csv` 的搬运粒度、trace 的重叠率。

## 源码模式映射

| 源码模式 | 可能问题族 | 优先 Metric | 需要的数据 |
| -------- | ---------- | ----------- | ---------- |
| `blockDim` 固定，未随 shape / tile 数变化 | `tiling`、`ai_core_utilization` | 核利用率、头开销占比、核间耗时不均衡 | `OpBasicInfo.csv: Block Dim/Task Duration`、`PipeUtilization.csv`、平台核数 |
| `tileLength` 很小或 tile 循环层级很多 | `tiling`、`data_movement` | 单次搬入/搬出粒度、MTE 指令密度、MTE2/MTE3 Bound | `Memory.csv`、`PipeUtilization.csv`、shape/dtype |
| tail 分支复杂或最后一核单独处理大量剩余数据 | `tiling`、`ai_core_utilization` | 核间耗时不均衡、最慢核定位、tail case 对比 | `PipeUtilization.csv` 逐核数据、多 shape profiling |
| `DataCopy` 在内层循环重复执行，或中间结果频繁写回 GM/workspace | `data_movement`、`onchip_memory` | 读写流量放大、MTE2/MTE3 占比、单次搬运粒度 | `Memory.csv`、`PipeUtilization.csv`、理论读写量 |
| `InitBuffer(..., 1)`、缺少 DoubleBuffer、EnQue/DeQue/FreeTensor 顺序串行 | `pipeline_parallel` | MTE/Compute 重叠率、MTE wait、流水线气泡 | trace/timeline、`ResourceConflictRatio.csv`、`PipeUtilization.csv` |
| `SyncAll`、`WaitFlag`、`PipeBarrier` 在 tile 循环内频繁出现 | `pipeline_parallel`、`api_algorithm` | 同步等待占比、重叠率、各 pipe wait ratio | trace/timeline、`ResourceConflictRatio.csv` |
| LocalTensor 临时 buffer 多、UB/L1/L0 切分公式接近容量上限 | `onchip_memory`、`tiling` | UB/L1/L0 带宽、UB 冲突、buffer 占用与容量比 | `MemoryUB.csv`、`MemoryL0.csv`、`ResourceConflictRatio.csv`、平台容量 |
| 使用 Scalar 循环、逐元素 `GetValue/SetValue`、小粒度 Cast 或重复 Cast | `api_algorithm`、`ai_core_utilization` | SCALAR Bound、Vector 理论利用率、指令类型占比 | `PipeUtilization.csv`、`ArithmeticUtilization.csv`、代码片段 |
| MatMul/FA/GMM 中 Cube 循环和后处理配比不清，AIC/AIV 等待明显可能 | `ai_core_utilization`、`pipeline_parallel` | AIC/AIV 时间差、CUBE Bound、Fixpipe 占比、理论算力利用率 | `PipeUtilization.csv`、`ArithmeticUtilization.csv`、trace/timeline |
| CacheMode、切分轴或访问顺序可能破坏局部性 | `data_movement`、`onchip_memory` | L2 命中率、读流量放大、MTE2 时间 | `L2Cache.csv`、`Memory.csv`、shape/dtype |

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
