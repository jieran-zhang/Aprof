# Profiling Metric Bundles

本文把 diagnosis 的问题族反推为 profiling 采集包。使用时从最小包开始，再按问题族扩展。

## 问题族

| 问题族 | 典型源码/现象 | 必需证据 | 扩展证据 |
| ------ | ------------- | -------- | -------- |
| `tiling` | blockDim 固定、tileLength 过大/过小、tail 集中 | `OpBasicInfo.csv`、`PipeUtilization.csv`、shape/dtype、TilingData、平台核数 | `Memory.csv`、trace/timeline、多 shape 对比 |
| `data_movement` | DataCopy 频繁、GM 往返、中间结果落 GM | `PipeUtilization.csv`、`Memory.csv`、shape/dtype、理论读写量 | `L2Cache.csv`、trace/timeline、CacheMode |
| `pipeline_parallel` | DoubleBuffer 未生效、同步多、CopyIn/Compute/CopyOut 串行 | trace/timeline、`PipeUtilization.csv` | `ResourceConflictRatio.csv`、queue/buffer 配置 |
| `onchip_memory` | UB/L1/L0 复用不足、临时 tensor 多、workspace slot 过多 | `Memory.csv`、buffer 公式、平台容量 | `MemoryUB.csv`、`MemoryL0.csv`、`ResourceConflictRatio.csv` |
| `ai_core_utilization` | VEC/CUBE 占比低、空闲核、负载不均 | `OpBasicInfo.csv`、`PipeUtilization.csv`、平台核数 | `ArithmeticUtilization.csv`、trace/timeline |
| `api_algorithm` | Scalar 循环、GetValue/SetValue、重复 Cast、低效 Reduce/Matmul | `PipeUtilization.csv`、关键代码片段 | `ArithmeticUtilization.csv`、`Memory.csv`、`*_code_exe_*.csv` |

## 最小采集包

用于用户只说“性能差”或 diagnosis 只给初始假设时：

- `OpBasicInfo.csv`：`Task Duration`、`Block Dim`。
- `PipeUtilization.csv`：逐 `block_id` 的 `aiv_time(us)`、`aic_time(us)`、VEC/CUBE/MTE/SCALAR/Fixpipe 占比。
- `Memory.csv`：GM↔UB、GM→L1、L0C→GM、主存读写、MTE 指令数和带宽字段。
- shape、dtype、format、输入输出个数。
- blockDim、tileLength、tileNum、tail、bufferNum、workspace。
- `/npu-arch` 分母：AIV/AIC 核数、UB/L1/L0/L2 容量、频率、理论带宽和理论算力。

## Metric 字段速查

| Metric | 文件 | 字段/公式 | 用途 |
| ------ | ---- | --------- | ---- |
| 核利用率 | `OpBasicInfo.csv` + `/npu-arch` | `Block Dim / coreNum` | 判断过少/过多开核 |
| 核间耗时不均衡 | `PipeUtilization.csv` | `(max(ai*_time) - min(ai*_time)) / max(ai*_time)` | 判断 tail 集中和切分不均 |
| MTE2/MTE3 Bound | `PipeUtilization.csv` | `ai*_mte2_ratio`、`ai*_mte3_ratio` | 判断搬入/搬出主导 |
| 单次搬入粒度 | `Memory.csv` | `GM_to_UB_datas(KB) * 1024 / ai*_mte2_instructions` | 判断 DataCopy 粒度过小 |
| 单次搬出粒度 | `Memory.csv` | `UB_to_GM_datas(KB) * 1024 / ai*_mte3_instructions` | 判断 tail 小块写回 |
| 读/写流量放大 | `Memory.csv` + shape/dtype | `read/write_main_memory_datas / 理论必要读写量` | 判断重复搬运或 workspace 往返 |
| MTE/Compute 重叠率 | trace/timeline | `overlap(MTE, Compute) / min(MTE_time, Compute_time)` | 判断流水并行是否生效 |
| SCALAR Bound | `PipeUtilization.csv` | `ai*_scalar_ratio` | 判断 Scalar 循环或控制开销 |
| Vector/Cube 理论利用率 | `ArithmeticUtilization.csv` + `/npu-arch` | `fops / (time * peak_flops)` | 判断计算 API 是否打满 |
| UB 冲突 | `ResourceConflictRatio.csv` | `aiv_vec_total_cflt_ratio` | 判断 UB bank/resource conflict |
| L2 命中率 | `L2Cache.csv` | `ai*_total_hit_rate(%)` | 判断局部性和 CacheMode |

## 采集包选择

- 若 3 个 metric 都来自 msopprof 8 CSV，选择 `hw-op`。
- 若需要 7 组 aic-metrics、sample 或对比摘要，选择 `hw-msprof`。
- 若主要 metric 是 trace/timeline、源码热点或 simulator 指令热点，选择 `sim`。
- 若一个计划同时需要 8 CSV 和 trace，优先拆成两个采集计划：`hw-op` 用于硬件计数，`sim` 用于 timeline proxy。
