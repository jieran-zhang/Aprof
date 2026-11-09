# 任务并行与计算指标字典

本文件维护现行指标名称、公式、字段映射和消费者。诊断与优化入口引用这里的定义。每条原始证据保留文件 SHA-256、工具/SDK 版本、device、PID、kernel 身份、调用序号、时间窗口与明确的表头。

## 原始字段与来源

- `block_dim` 读取 `OpBasicInfo.csv` 的 `Block Dim`，`task_duration_us` 读取 `Task Duration(us)`。主核与副核的 `Mix Block Dim` 分别保留。缺列时补采并保持 unknown。
- `available_cores` 取已初始化设备的 `PlatformAscendC.GetCoreNumAiv()` 或 `GetCoreNumAic()`。记录所选核类型和实际可见设备资源。技能名称用于找到操作方法，实际数值绑定 API 或设备探测回执。
- `total_tasks`、`used_core_num`、`total_elements`、`dtype_bytes` 从同源 Host Tiling、TilingData 和 workload 推导，记录公式与输入位置。
- 每核耗时来自 `PipeUtilization.csv` 的 `aiv_time(us)` 或 `aic_time(us)`，按明确的 `block_id` 和 `sub_block_id` 匹配同次调用。表头变体须在采集回执中显式映射，保留原表头。只拿到活跃 block 时，空闲比例保持 unknown。
- `aiv_vec_ratio`、`aic_cube_ratio` 与各核类型的 MTE 比例均保留引擎名和原单位。比率单位按后端声明转换。`Memory.csv` 的流量字段按真实版本与读写层级显式映射，字段族或通配符仅作为检索线索。

## 统一公式

`active_cores_attainable = min(block_dim, total_tasks, available_cores)`，三项都必须属于同一核类型。`block_dim` 是逻辑启动量，实际活跃核数另由完整 block 覆盖记录推导。混合 kernel 分别计算 AIC 和 AIV，并检查两侧工作配比。

`elements_per_core = ceil(total_elements / active_cores_attainable)`，仅在任务等工作量时作为规划估算。分母为 0 时将该 case 标为无有效工作或输入无效，保留具体原因。`useful_bytes_per_core = elements_per_core * dtype_bytes`，实际字节还需要计入输入、输出数量和复用。

`launch_coverage = min(block_dim, available_cores) / available_cores`，`attainable_coverage = active_cores_attainable / available_cores`。这两项描述启动与可达覆盖，计算吞吐另用引擎耗时或运算计数评估。

`imbalance = (max(core_time) - min(core_time)) / max(core_time)`。保存全部预期 block 的覆盖情况及每核工作量，分别展示含空闲核与仅活跃核的分布。全零耗时保持 unknown。经验筛查采用大于 0.10 为关注、大于 0.30 为严重候选，阈值只触发进一步分析。

`idle_fraction = idle_blocks / launched_blocks`，必须有全部启动 block 的完成或无工作证据。`head_fraction = (task_duration_us - max(core_time_us)) / task_duration_us` 仅在双方计时覆盖关系已确认时估算，出现负值则检查窗口与单位。

## 计算主导与架构边界

当前硬件收益证据主要覆盖 910C/A3 Vector。纯 Vector kernel 使用 AIV 引擎指标和 AIV 峰值，纯 Cube kernel 使用 AIC 指标，混合 kernel 分别报告两侧活动、相依关系和关键路径。流水活动时间可以重叠，逐项相加前须确认互斥性。

Vector 活动比例只能支持 Vector 阶段的判断。涉及 MatMul、FA 或混合 kernel 时还须核对 `aic_cube_ratio`、`aic_cube_fops`、Cube 时间和同步等待。MTE 冲突同样绑定核类型、引擎、读写方向和存储层级。

## 证据分类与消费者

CSV 字段是原始观察，Tiling/shape 公式是派生观察，trace 和多 shape 对比是机制判断材料。使用现行 claim basis `code_fact`、`mechanism_inference`、`case_support` 等枚举时，另记采集来源及测量性质。simulator 输出保留 proxy 身份。

C1 使用定义形成假设，C2 实例化任务和容量公式，C3 核对实际 patch，C4 采集并比较相同口径的指标，独立 reviewer 核验来源与覆盖。自动检查可使用[并行指标工具](../../../tools/review_parallel_metrics.py)，缺失字段保持 unknown，格式或作用域冲突判为 invalid。

## 历史名称迁移

旧 `availableCores`、`activeCores`、`totalTasks`、`usedCoreNum` 分别映射为 `available_cores`、`active_cores_attainable`、`total_tasks`、`used_core_num`。`blockDim` 映射为 `block_dim`。

历史 workload class `tiny/small/normal/large` 保留四个合法标签，但阈值来自任务显式配置。旧 `tiny-limited` 统一记录为 `workload_limited`，要求有可达并行度及工作量证据。缺少阈值配置时保留规模数值并标注 class unknown。

版本化知识保留对应历史定义用于回放。新任务引用本字典的现行定义，遇到历史计数或分母差异时，在分析记录中明确版本、差异和采用依据。
