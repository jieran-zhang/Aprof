# Single-Case Roofline Diagnosis

本文用于 `aprof-diagnosis-agent` 在没有 baseline 的情况下，对单个 kernel 做硬件利用率判断。目标是用硬件分母、shape/tiling、msprof 字段和源码事实构造 roofline 证据，判断瓶颈更接近计算、搬运、同步/调度还是切分问题。

## 输入边界

允许使用：

- kernel 源码和中性源码事实。
- shape、dtype、format、输入输出个数。
- TilingData：`blockDim`、`tileLength`、`tileNum`、`tailLength`、`elemsPerCore`、bufferNum、workspace。
- msprof 产物：`OpBasicInfo.csv`、`PipeUtilization.csv`、`Memory.csv`、`ArithmeticUtilization.csv`、trace/timeline、`*_instr_exe_*.csv`。
- `/npu-arch`、`PlatformAscendC` 或用户提供的硬件参数。

禁止使用：

- `injected_label`、`injected_problem`、variant 名称。
- `inject_manifest.json`、`inject_audit_report.json`、`label_alignment_report.json`。
- 人工标注的 ground truth。

## 硬件分母

优先从运行时或 `/npu-arch` 获取：

| 参数 | 字段 | 用途 |
| ---- | ---- | ---- |
| AIV 核数 | `GetCoreNumAiv()` | Vector 算子核利用率、任务覆盖率 |
| AIC 核数 | `GetCoreNumAic()` | Cube 算子核利用率 |
| UB/L1/L0/L2 容量 | `GetCoreMemSize(...)` | tile/buffer 是否接近容量上限 |
| 频率 | `Current Freq` / 平台规格 | 理论吞吐上限换算 |
| Vector 峰值 | `vector_peak_flops` 或平台规格 | Vector roofline |
| Cube 峰值 | `cube_peak_flops` 或平台规格 | Cube roofline |
| GM 带宽 | `gm_bandwidth_bytes_per_s` 或实测基准 | Memory roofline |

缺少分母时不要硬编码；把对应判断降级为 `proxy`。

## 工作量估算

### 字节量

优先使用 `Memory.csv`：

- `actual_read_bytes = read_main_memory_datas`
- `actual_write_bytes = write_main_memory_datas`
- 或使用 `GM_to_UB_datas(KB)`、`UB_to_GM_datas(KB)` 估算 GM↔UB 流量。

没有 `Memory.csv` 时，从 shape/dtype 估算理论下限：

```text
read_bytes_min = sum(input_elements * dtype_bytes)
write_bytes_min = sum(output_elements * dtype_bytes)
traffic_lower_bound = read_bytes_min + write_bytes_min
```

若源码有重复 `DataCopy`、workspace 往返或 tail 额外 reload，应在 `diagnoses[].metrics` 中单独列出，不要直接把它混入理论下限。

### 计算量

优先使用 `ArithmeticUtilization.csv`：

- `actual_vector_flops = aiv_vec_fops`
- `actual_cube_flops = aic_cube_fops`

没有 CSV 时，可按算法估算：

```text
estimated_ops = output_elements * ops_per_element
```

对 `Exp`、`Div` 这类复杂函数，估算只能作为相对判断或 proxy，必须标注不确定性。

## Roofline 派生

```text
arithmetic_intensity = work_ops / traffic_bytes
achieved_ops_per_s = work_ops / task_duration_s
achieved_bandwidth = traffic_bytes / task_duration_s
compute_roof = peak_flops
memory_roof = arithmetic_intensity * gm_bandwidth
roofline_bound = min(compute_roof, memory_roof)
utilization = achieved_ops_per_s / roofline_bound
```

若缺 `Task Duration`，sim trace 可用 `timeline_span` 做 proxy，但必须标注单位与工具差异。

## 单 Case 诊断顺序

1. **源码与 Tiling 门禁**：检查 `blockDim`、`tileLength`、`tileNum`、`tailLength`、buffer 公式、循环内 `DataCopy`、`PipeBarrier`。
2. **Roofline 下限**：用 shape/dtype 和硬件参数估算最低流量、最低计算量、理论 bound。
3. **真实 report 校正**：若有 `Memory.csv` / `ArithmeticUtilization.csv`，替换估算值。
4. **Trace proxy**：若只有 `trace.json`，统计搬运类、同步类、Vector/Cube 类指令耗时/计数，并标注 proxy。
5. **每问题输出 metric**：每个问题至少 2 个 metric，推荐源码 + tiling + report 各 1 个。

## 输出要求

对每个诊断项输出：

```json
{
  "problem": "tileLength too small",
  "problem_family": "tiling/data_movement",
  "confidence": "medium",
  "metrics": [
    {"name": "tile_num", "value": 128, "source": "tiling_context"},
    {"name": "estimated_copy_bytes_per_tile", "value": 64, "source": "shape/tiling"},
    {"name": "barrier_event_count", "value": 384, "source": "trace.json"}
  ],
  "roofline_interpretation": "trace proxy shows overhead dominated by copy/sync rather than compute",
  "missing_evidence": ["Memory.csv", "PipeUtilization.csv"]
}
```

## 证据降级规则

- 有 `Memory.csv` + `ArithmeticUtilization.csv` + 硬件分母：可做 `roofline-direct`。
- 有 shape/tiling + 硬件分母，但无真实 CSV：只能做 `roofline-estimated`。
- 只有 trace/timeline：只能做 `trace-proxy`。
- 只有源码：只能做 `source-hypothesis`。
