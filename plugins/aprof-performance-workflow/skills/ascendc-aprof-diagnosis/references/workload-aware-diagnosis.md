# Workload-Aware Diagnosis

本文件用于在读取六类诊断矩阵前建立 workload 与可达上限模型，防止把小 workload 的低利用率误判为可优化瓶颈。

## Mandatory Gate

最终诊断前必须先构造 `workload_model`：

- `total_elements`、输入/输出 shape、dtype bytes、输入输出个数。
- `operator_family` 与每元素计算量估计，例如 elementwise 的 `ops_per_element_estimate`。
- 理论最低 GM 读写量：`min_read_bytes`、`min_write_bytes`。
- `block_dim`、可用 AIV/AIC core、`elements_per_active_core`。
- UB/L1/L0 footprint 与必要 buffer 深度；未知时写 `unknown`，不要硬编码。
- `workload_class`：`tiny`、`small`、`normal`、`large`。

建议分类：

| Class | 参考条件 | 解释 |
| --- | --- | --- |
| `tiny` | elementwise 总元素数 `<= 4096` 或每核有效元素很少 | 启动、调度、标量和 MTE setup 很容易主导，低利用率通常不可避免 |
| `small` | 数据量不足以让大部分 core 拿到稳定 tile | 需要谨慎比较减核、合并任务和保持通用性 |
| `normal` | 每核有多个有效 tile，搬运/计算可被稳定采样 | 可按六类矩阵做常规诊断 |
| `large` | 工作量足以覆盖多数 core 且多轮 tile | 低利用率更可能是真瓶颈，但仍需 metric 佐证 |

## Attainable Utilization

不要用绝对阈值直接判定 “UB 利用率低” 或 “AI Core 利用率低”。先估算可达利用率：

```text
active_cores_attainable = min(block_dim, total_tasks_or_tiles, available_cores)
elements_per_core = ceil(total_elements / max(active_cores_attainable, 1))
useful_bytes_per_core = elements_per_core * dtype_bytes * useful_tensor_count
ub_attainable_ratio = useful_ub_bytes_needed / ub_bytes_per_core
core_attainable_ratio = active_cores_attainable / available_cores
```

若 workload 是 `tiny`/`small`，且 observed utilization 接近可达上限，输出：

- `diagnosis_type=workload_limited`
- `problem_family` 可保留原观测族，但不要写成 `true_bottleneck`
- recommendation 应强调“无需仅为利用率优化”，除非有额外证据指向真实开销

## When Low Utilization Is a Real Problem

低利用率只有在绑定以下证据时才可定为 `true_bottleneck`：

- `Memory.csv` 显示读写流量明显高于理论下限，或 MTE 指令密度异常。
- `PipeUtilization.csv` 显示特定 pipe 长时间 bound，且不是 workload 太小导致的头开销。
- `ResourceConflictRatio.csv` 显示 UB bank/resource conflict，而不是 UB footprint 本身小。
- trace 显示明显 pipeline bubble、同步等待或 tail 慢路径。
- 多 shape 对比显示问题随规模变化仍存在，不只是 tiny case 特征。

## UB Utilization Interpretation

UB 占用低不等于片上内存问题。对 elementwise 小 shape，例如 `total_elements=2048`：

- 理论有效数据只有几个 KB，远小于单核 UB 容量。
- 低 UB 占用通常来自 workload 本身，不代表需要强行增加 UB 使用。
- 只有当低 UB 占用导致 tile 过小、重复 GM 往返、额外 copy 或 pipeline 无法重叠时，才转入 `onchip_memory` 或 `data_movement` 真瓶颈诊断。

## Output Rules

- 每个 `diagnoses[]` 写 `diagnosis_type`：`true_bottleneck`、`workload_limited`、`measurement_limited`、`code_quality_risk` 或 `optimization_not_recommended`。
- `workload_limited` 可以有优化建议，但必须是保守建议，例如保持 production-safe、避免为了 benchmark 特化。
- 缺 repeat 或 CV 不稳定时优先输出 `measurement_limited`，不要根据单次 duration 下结论。
- 缺 shape、dtype 或硬件分母时，必须把 workload model 标为 incomplete，并列入 `missing_evidence`。
