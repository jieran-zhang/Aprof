# 算子诊断的证据语义

只读取当前假设需要的视图，保留观测差异、公式、缺失字段与备选解释。工具输出不能单独确定唯一瓶颈。

| 问题 | 主要视图 | 解释边界 |
| --- | --- | --- |
| Scalar、Vector、搬运活跃度 | `PipeUtilization.csv` | 活跃比例可重叠，不是同一时间线的互斥份额 |
| 搬运大小、GM 流量 | `Memory.csv` | 比较 workload 所需字节与对应 Core/task 聚合，不乘猜测核数 |
| Vector 算术 | `ArithmeticUtilization.csv` | 没有操作数与硬件分母时不是完整 roofline |
| 等待、资源冲突 | `ResourceConflictRatio.csv` | 等待不自动等于 bank 冲突，按字段真实定义 |
| UB/L0 访问 | `MemoryUB.csv`、`MemoryL0.csv` | 保留 AIV/AIC 适用范围和缺失计数器 |
| 缓存行为 | `L2Cache.csv` | 字段存在时保留读/写与 local/far 区分 |
| 流水重叠、间隙 | `PipeTrace.json` | 只有采样到的完整区间，限制见下文 |
| kernel 身份、任务耗时 | `summary.jsonl` / `OpInfoSummary` | 属于单个结果的身份、block 数、耗时，不是 Core 行样本 |
| 设备、频率 | `HardwareInfo.jsonl` | 绑定实际芯片/ISA/频率，不能仅凭 DAV_2201 判断 910C |

## 单位、缺失值与分组

- CSV 按 `block_id`、`sub_block_id`（`cubeN` 或 `vectorN`）匹配 Core 语义，不按行号。文件同名不允许合并不同结果、workload、kernel 或重复采集。
- `ratio` 是未缩放比值，`(%)` 是百分比；比值大于 1 也不能擅自除以 100。
- CSV `NA`、JSONL `null` 表示不可用或不适用，不是零。记录排除单元格，区分 Core 不匹配、计数缺失、分母/频率无效与已知不支持。计数器与分母存在时，零才是实测值。
- 固定上游版本的 `aiv_mte3_active_bw(GB/s)`、`aiv_ub_to_gm_bw(GB/s)`、`UB_to_GM_datas(KB)`、`UB_to_GM_bw_usage_rate(%)`、`aiv_ub_read_bw_gm(GB/s)` 不可用，不能据此推断没有写操作。
- `PipeUtilization` 可能缺活跃带宽计数，需要时同时采 `Memory`。
- 数据量 KB 为 `bytes / 1024`；所述 GB 带宽为 `bytes * 1e6 / 1024^3 / duration_us`。比较 workload 下界时保持相同约定。
- `aic_time(us)` / `aiv_time(us)` 是该行 cycle 除相应 MHz，不是 `Task Duration(us)`。混合 kernel 的内存计算可能用 task-log 时间，保留后端/版本语义。
- 工具理论峰值属于该工具/配置证据；上游 950 样例的 1600 GB/s 不是 910C/A3 已验证峰值，不能变为架构常量。

## summary 与独立采集

`summary.jsonl` 各 Section 对有效 task 值取平均，各字段有效数可能不同，不能恢复逐 Block 行。最终 `OpInfoSummary` 提供 kernel、device、block 数、频率与耗时，不可用字段保留 null。

Section 均值和逐 Core CSV 聚合是不同指标。先在单次采集中归并选定 Core，再由独立采集构成重复样本。数千 Core 行或内部 replay 不等于五次独立机制采集。runtime 验证来源、单位、聚合和稳定性后才判机制方向；这些样本和 task-log 时间不自动满足 [统一计时协议](../../ascendc-aprof-profiling/references/unified-timing.md)，也不能被解释成旧 30 对配对证据。

## Pipeline 采样限制

`PipeTrace.json` 记录完整忙碌区间（`ph="X"`）。`ts`、`dur` 单位是**微秒**，即使 `displayTimeUnit` 为 `ns`。跨轨道事件可重叠，忙碌时间求和不是 kernel 总耗时。

轨道包含 group/Core，有时有 process/result/device/replay 前缀；不同 replay 不证明共享连续全局时间线。group ID 为 0 至 5，最多六个采样组，各有观测到的 `cubecore`、`veccore0`、`veccore1`。数量不代表全部活跃核、blockDim 或核覆盖，`pid` 不提供 Block ID。

只有起止完整的区间才输出；空/缺轨道不证明硬件空闲、流水不支持或无瓶颈。用本地检查器确认结构与实际轨道，只在兼容来源/轨道/时间域内推断重叠，结合源码、workload 与 PMU 再归因。
