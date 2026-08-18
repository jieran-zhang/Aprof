# Report Parsing Plan

本文描述 msprof report 生成后如何整理并获取 metric 的具体值。以 raw CSV/trace 为证据，使用 `scripts/compress_msprof.py` 生成 AProf symptom draft；`ops-profiling` summary 只作人读交叉检查。

## 通用步骤

1. 根据 `profiling_plan.json.execution_plan.output_dir` 或用户提供的 report 目录定位产物。
2. 生成或读取 `profiling_results.json`，确认 `required_artifacts` 均已满足。
3. 按 `profiling_plan.json.parser_plan` 逐项读取 CSV、trace 或 summary。
4. 对真实硬件 metric 汇总重复样本：记录 `samples`、`count`、`mean`、`median`、`min`、`max`、`std`、`cv` 和 `selected`。
5. 输出 metric 值时保留来源路径、字段名、公式和单位。
6. 缺字段时不要猜值，记录到 `missing_required_artifacts` 或 `notes`。
7. 运行 `compress_msprof.py --input <report-or-archive> --output <symptoms.json>`；如有平台核数和算法流量下界，显式传入 `--available-cores`、`--theoretical-gm-bytes`。
8. 保留 compressor 输出的 artifact hash、extractor version、threshold profile、unknown predicate 和 candidate problem ambiguity set。

## hw-op CSV

典型路径：

```text
profiling_out/msprof_hw_output/OPPROF_*/OpBasicInfo.csv
profiling_out/msprof_hw_output/OPPROF_*/PipeUtilization.csv
profiling_out/msprof_hw_output/OPPROF_*/Memory.csv
profiling_out/msprof_hw_output/OPPROF_*/ArithmeticUtilization.csv
profiling_out/msprof_hw_output/OPPROF_*/ResourceConflictRatio.csv
profiling_out/msprof_hw_output/OPPROF_*/L2Cache.csv
profiling_out/msprof_hw_output/OPPROF_*/MemoryUB.csv
profiling_out/msprof_hw_output/OPPROF_*/MemoryL0.csv
```

解析建议：

- 使用 Python `csv.DictReader` 或 `pandas.read_csv`，字段名保持原样。
- 保留目标 op 行和逐 `block_id` 行，不要只取均值。
- 派生 metric 要同时输出公式和参与计算的原始字段值。
- 若目录包含 `legacy_run_*`、`run_*` 或 `hw_op` 的多次 report，逐 run 解析同一 metric 后再做统计。

常见派生：

| Metric | 文件 | 解析方式 |
| ------ | ---- | -------- |
| 核利用率 | `OpBasicInfo.csv` | `Block Dim / coreNum` |
| 核间耗时不均衡 | `PipeUtilization.csv` | 对逐核 `aiv_time(us)` 或 `aic_time(us)` 取 max/min |
| MTE2/MTE3 Bound | `PipeUtilization.csv` | 比较 `ai*_mte2_ratio`、`ai*_mte3_ratio` 与 VEC/CUBE/SCALAR 占比 |
| 单次搬入粒度 | `Memory.csv` | `GM_to_UB_datas(KB) * 1024 / ai*_mte2_instructions` |
| 读流量放大 | `Memory.csv` | `read_main_memory_datas / 理论必需读数据量` |
| L2 命中率 | `L2Cache.csv` | 读取 `ai*_total_hit_rate(%)` |

## hw-msprof

典型路径：

```text
profiling_out/msprof_hw_output/PROF_GROUP_*/PROF_*/*.csv
profiling_out/msprof_hw_output/PROF_GROUP_*/PROF_Sample/**/aicore.db
profiling_out/hw_summary.txt
```

解析建议：

- 优先读取 `hw_summary.txt` 获取主 bound、逐核摘要和 ops-profiling 归纳。
- 如需结构化数值，再读取 `PROF_GROUP_*` 下对应 CSV。
- `hw_summary.txt` 只能作为摘要证据，不能替代缺失的原始 CSV 字段。
- 对外层 repeat 的多组 `PROF_GROUP_*`，每组先提取同名 metric，再按同一公式计算统计值。

## sim

典型路径：

```text
profiling_out/msprof_sim_output/OPPROF_*/simulator/trace.json
profiling_out/msprof_sim_output/OPPROF_*/simulator/core0.veccore0/*_instr_exe_*.csv
profiling_out/msprof_sim_output/OPPROF_*/simulator/core0.veccore0/*_code_exe_*.csv
```

解析建议：

- `trace.json`：按事件时间计算 MTE/Compute 重叠率、串行阶段和 idle。
- `*_instr_exe_*.csv`：按 cycles / running_time 汇总指令热点。
- `*_code_exe_*.csv`：定位源码热点。
- sim metric 是 proxy；最终报告必须标注 `Trace/对比` 或 `sim-proxy`。

## profiling_results.json 生成规则

根据 `profiling_plan.json.required_artifacts` 检查本地 report 目录：

- 找到匹配文件则加入 `artifacts[]`。
- 没找到则加入 `missing_required_artifacts[]`。
- 只有缺失列表为空时，`ready_for_diagnosis = true`。
- 按 `parser_plan[]` 解析得到的值加入 `metric_values[]`，并记录来源文件、字段、公式、单位。
- `samples` 为空或样本数小于 `execution_plan.repeat` 时，设置 `measurement_status=single_run_exploration` 或 `measurement_limited`。
- `cv > stability_cv_threshold` 时，设置 `measurement_status=unstable`，并在 `notes` 说明需要增加 repeat、隔离系统噪声或重新采集。
- baseline/candidate 比较必须使用相同的 `selected` 统计值。默认使用 median；不要用单次最优值替代 median。

## Structured symptom boundary

`compress_msprof.py` currently implements conservative hardware-CSV drafts for:

- core coverage and per-core imbalance;
- scalar share;
- MTE setup dominance when ratio, bandwidth usage, and bytes/instruction all exist;
- UB/resource conflict;
- GM traffic amplification when the task supplies a theoretical byte lower bound;
- dominant pipe and a non-authoritative set of plausible mechanisms.

Timeline overlap and vector granularity remain `unknown` unless a dedicated
trace/instruction adapter is supplied. When `trace.json` exists, the installed
`ops-simulator/scripts/trace_bubble_analyzer.py --json` may provide structured
bubble evidence, but it must remain simulator/proxy-labelled until hardware
evidence exists.

## 统计规则

```text
mean = sum(samples) / count
median = sorted(samples)[count // 2] 或偶数中位均值
std = sample standard deviation when count > 1 else 0
cv = std / abs(mean) when mean != 0 else null
selected_value = statistics[statistic]
```

`measurement_status`：

- `stable`：样本数满足 repeat，CV 不超过阈值，可作为 final metric evidence。
- `unstable`：样本数满足 repeat，但 CV 超阈值。
- `single_run_exploration`：只有单次样本，只能用于探索。
- `measurement_limited`：缺失样本、缺失字段、baseline/candidate policy 不一致或提升小于噪声阈值。

示例输出见 [../../references/contracts.md](../../references/contracts.md)。
