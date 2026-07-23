# Metric To msprof

本文将硬件 metric 转换为可执行的 msprof 采集模式和命令模板。执行与产物检查由 `aprof-profiling-agent` 完成。

## 模式选择

| 需要的 metric / report | 优先模式 | 原因 |
| ---------------------- | -------- | ---- |
| `OpBasicInfo.csv`、`PipeUtilization.csv`、`Memory.csv`、`ArithmeticUtilization.csv`、`ResourceConflictRatio.csv`、`L2Cache.csv`、`MemoryUB.csv`、`MemoryL0.csv` | `hw-op` | msopprof 标准 CSV 最适合 diagnosis 矩阵 |
| 7 组 `aic-metrics`、sample、`hw_summary.txt`、主 bound 摘要 | `hw-msprof` | `ops-profiling` 脚本可封装多组硬件指标 |
| `trace.json`、`*_instr_exe_*.csv`、`*_code_exe_*.csv`、timeline/proxy 指标 | `sim` | `msprof op simulator --config` 可在无 NPU 环境产生 timeline 和指令热点 |

## 命令模板

### hw-op

```bash
msprof op --warm-up=<warm_up> --launch-count=<repeat> --output=profiling_out/msprof_hw_output ./<binary> <args>
```

默认 `<warm_up>=10`、`<repeat>=5`。执行前确认 `run_cmd` 可在当前 profiling 环境运行，输出目录建议使用 `profiling_out/msprof_hw_output`。`--launch-count` 产生同一 workload 的重复样本，解析时必须汇总 median/mean/std/CV。

### hw-msprof

```bash
bash ../ops_profiling/scripts/msprof_profile_run.sh \
  --warm-up=<warm_up> \
  --output=profiling_out/msprof_hw_output \
  -- ./<binary> <args>
```

执行前确认 `ops_profiling/scripts/msprof_profile_run.sh` 可用，输出目录建议使用 `profiling_out/msprof_hw_output`。若脚本本身不能提供 `<repeat>` 个同质样本，外层必须循环执行到 `repeat=5`，并保存为 `run_1`...`run_5`。

### legacy-msprof-application

```bash
for i in 1 2 3 4 5; do
  mkdir -p "profiling_out/msprof_hw_output/legacy_run_$i"
  msprof --application="./<binary> <args>" \
    --output="profiling_out/msprof_hw_output/legacy_run_$i" \
    --aic-metrics="${APROF_AIC_METRICS:-PipeUtilization}" \
    --task-time=on --runtime-api=on
done
```

普通 `msprof --application` 是 legacy fallback。它没有 `--launch-count` 时，必须在 profiling 前显式 warmup 目标程序，并外层 repeat 多次。不要覆盖旧 report；每次采集写入独立目录。

### sim

```bash
msprof op simulator \
  --config=./op_config.json \
  --output=profiling_out/msprof_sim_output \
  --timeout="${MSPROF_TIMEOUT:-8}"
```

执行前确认 `op_config.json`、kernel `.o` 和 simulator 运行环境可用，输出目录建议使用 `profiling_out/msprof_sim_output`。

Simulator 约束：

- 必须使用 `--config`，不要使用 `--application`。
- 不要为 simulator 添加 `--aic-metrics=PipeUtilization`。
- 不要声称 sim 会产出 `PipeUtilization.csv` 或 `Memory.csv`。
- sim 结果只能作为 trace/proxy；不参与 final hardware speedup evidence，除非用户明确接受 proxy 结论。

## Metric 到模式映射

| Metric | 首选模式 | 必需产物 | Fallback |
| ------ | -------- | -------- | -------- |
| 核利用率 | `hw-op` | `OpBasicInfo.csv` | `hw-msprof` summary + report 字段 |
| 核间耗时不均衡 | `hw-op` | `PipeUtilization.csv` | sim trace proxy |
| MTE2/MTE3 Bound | `hw-op` | `PipeUtilization.csv` | `hw-msprof` 多组 metrics |
| 单次搬入/搬出粒度 | `hw-op` | `Memory.csv` | 无直接 sim fallback |
| 读/写流量放大 | `hw-op` | `Memory.csv` + shape/dtype | 无直接 sim fallback |
| 重叠率 / 流水串行度 | `sim` | `trace.json` | hw sample timeline（如可用） |
| SCALAR Bound | `hw-op` | `PipeUtilization.csv` | sim instr proxy |
| Vector/Cube 理论利用率 | `hw-op` | `ArithmeticUtilization.csv` + `/npu-arch` | `hw-msprof` summary |
| UB 冲突 / wait | `hw-op` | `ResourceConflictRatio.csv` | hw sample |
| L2 命中率 | `hw-op` | `L2Cache.csv` | 无直接 sim fallback |

## 计划拆分规则

- 同一批 metric 若都能由 `hw-op` 产出，合并为一个 `hw-op` 计划。
- 若同时需要 `trace.json` 和 8 CSV，输出两个 plan 或把 trace 标为 `optional_artifacts`。
- 若用户尚未提供 `run_cmd`，在 `execution_plan.run_cmd` 中保留 `./<binary> <args>`，并在 `notes` 中要求补充。
- 对最终性能证据，`execution_plan` 必须包含 `warm_up`、`repeat`、`statistic`、`stability_cv_threshold` 和 `min_effect_pct`。
- baseline 与 candidate 必须使用相同 mode、warmup、repeat、shape、dtype 和统计策略；否则只能输出探索性比较。
