---
name: ascendc-aprof-profiling
description: Plan, execute, and normalize Ascend C profiling evidence for AProf. Use when source/workload diagnosis lacks required metrics, when build and full-case correctness must precede profiling, when a candidate needs paired measurement, or when raw msprof/msprof-op CSV and simulator artifacts must be compressed into versioned symptom drafts. Use the bundled stage runner, symptom compressor, paired timer, and CANNBot collectors; let the runtime gate remain authoritative.
---

# AscendC AProf Profiling 采集与解析

## Machine boundary

- Use this skill to propose collection and parsing work. Let `aprofctl` validate
  candidate-gate artifacts, paired statistics, and measurement status.
- Keep raw artifacts immutable and content-addressed under the task's
  `.aprof/` state. Never synthesize missing counters.
- Mark simulator evidence as feasibility/proxy data; it cannot train production
  performance value.
- `profiling_plan.json`, stage execution reports, paired timing, and symptom
  JSON are versioned drafts. The current runtime does not expose strict
  `profiling_plan`/`profiling_results` contract kinds; do not claim that
  `aprofctl contract validate` validates them.

## 使用场景

当用户还没有完整 profiling 数据，或已有数据不足以支撑 `/ascendc-aprof-diagnosis` 的诊断矩阵时，使用本 Skill：

- 需要从性能问题反推应采集哪些 `msprof` / `aprof` CSV、trace 和平台参数。
- 需要把 Tiling、数据搬运、流水、片上内存、AI Core 利用率、API/算法低效的诊断 metric 汇总成采集任务。
- 需要执行 msprof 并解析 report，得到可交给 `/ascendc-aprof-diagnosis` 验证的 metric 值。

## 工作流

1. 先读取 [references/metric-bundles.md](references/metric-bundles.md)，确认目标问题族和所需 metric 分组。
2. 若用户只给现象，先把现象映射到一个或多个诊断问题族。
3. 读取 [references/metric-to-msprof.md](references/metric-to-msprof.md)，把 metric 映射到 `hw-op`、`hw-msprof` 或 `sim`。
4. 先执行环境、build 和 correctness gate。优先加载 `ascendc-env-check`；对
   CANNBench direct-invoke 工程，build 使用 CMake，correctness 使用
   `bash run.sh --all --skip-build`，并要求 `results.json` 为 20/20。用
   `scripts/run_profile_stages.py` 的 JSON command arrays 固化执行顺序、timeout、
   exit code、日志与 hash；先 `--dry-run`，获得用户授权后再执行。
5. 分开记录两种预算与采样：production gain gate 使用至少 30 个交错配对的
   cheap-timing samples，并要求 `CV<=0.05`、`speedup LCB>=1.03`；完整
   msprof 默认 `warm_up=10`、`repeat=5`，只用于机制 metric 聚合，不能拿 5
   次 full-profile launch 代替 30 对 timing samples。仅当 timing command
   排除 build、数据生成和 verify 时，才使用 `scripts/paired_timing.py`。
6. 使用已安装 `ops-profiling/scripts/msprof_profile_run.sh` 采集 7 组
   aic-metrics + sample-based 产物。不要使用它的 `--compare` 代替正确性
   gate；其 compare path 不是 AProf 的 30-pair production protocol。
7. 读取 [references/report-parsing.md](references/report-parsing.md)，再执行
   `scripts/compress_msprof.py`，把 raw CSV、字段、hash、缺失值和版本化
   heuristic 压成 symptom draft 与 `predicate_states` draft。
8. 保留每个 symptom 的所有 `candidate_problem_ids`。同一现象可以对应多个
   mechanism；source/workload evidence 和 immutable graph routing 才负责消歧。
9. 对缺失数据或不稳定数据明确说明无法直接诊断的原因，并给出下一步采集命令或文件要求。
10. 采集完成后切换到 `/ascendc-aprof-diagnosis` 使用对应诊断矩阵归因。

## Executable tools

Resolve paths from the installed skill roots; do not assume the repository
checkout layout.

- `scripts/run_profile_stages.py`: execute declared preflight/build/correctness/profile stages. Commands are arrays, not shell strings. Stops at the first failed mandatory stage and hashes every log.
- `scripts/paired_timing.py`: collect deterministic alternating AB/BA command-wall-clock pairs. Use only for timing-only commands; fewer than 30 pairs remain exploratory.
- `scripts/compress_msprof.py`: normalize `op_summary_*.csv`, msprof-op CSV, and archived per-core cycles into measured features, heuristic symptoms, ambiguity sets, artifact hashes, and tri-state predicate drafts.
- `ops-profiling/scripts/msprof_profile_run.sh`: CANNBot full hardware collector. Use for selected sentinel/final cases, not every search candidate.
- `ops-simulator/scripts/trace_bubble_analyzer.py --json`: optional structured trace-bubble adapter when a Chrome trace exists. Keep its evidence proxy-labelled.

Example stage config for CANNBench:

```json
{
  "schema_version": "1.0.0",
  "op_dir": "benchmarks/cannbench/operators/exp",
  "output_dir": ".aprof/executions/baseline-001",
  "stages": [
    {"name": "build", "commands": [["cmake", "-S", ".", "-B", "build", "-DCMAKE_BUILD_TYPE=Release"], ["cmake", "--build", "build", "-j4"]], "timeout_seconds": 1200, "required": true},
    {"name": "correctness", "commands": [["bash", "run.sh", "--all", "--skip-build", "--device", "0"]], "timeout_seconds": 3600, "required": true}
  ]
}
```

Add a profile stage only after the correctness stage passes. Point it at an
explicit CANNBot collector command and a unique `.aprof/` output directory.

Execute from this skill directory (or resolve the installed skill path):

```bash
python3 scripts/run_profile_stages.py --config <config.json> \
  --report <dry-run-report.json> --dry-run
python3 scripts/run_profile_stages.py --config <config.json> \
  --report <execution-report.json>
python3 scripts/compress_msprof.py --input <report-root> \
  --op-name <exact-kernel-name> --output <symptoms.json>
python3 scripts/paired_timing.py --config <paired-config.json> \
  --output <paired-output.json>
```

The stage report, symptom draft, and paired output are not `aprofctl contract`
kinds. Import their evidence into `context` or `gate_request` before runtime
validation and candidate gating.

## 命令选型

- 优先选择能直接产出目标 metric 的真实硬件采集：
  - `hw-op`：需要 `OpBasicInfo.csv`、`PipeUtilization.csv`、`Memory.csv` 等 msopprof 8 CSV 时优先。
  - `hw-msprof`：需要 7 组 `aic-metrics`、sample、`hw_summary.txt` 或对比摘要时优先。
- 只有在无 NPU、只需 timeline/proxy metric，或明确要求 simulator 时，才选择 `sim`。
- simulator 只能作为 trace / 指令 / 源码热点代理，不能声称产出 `PipeUtilization.csv`、`Memory.csv` 等上板 CSV。
- `hw-op` 默认命令是 `msprof op --warm-up=10 --launch-count=5 ...`，用于
  full-profile metric；另行采集至少 30 个交错配对 cheap timings 才能进入
  production gain gate。
- 普通 `msprof --application` 只能作为 legacy fallback；它必须先显式 warmup，再外层 repeat 多次，每次写入独立 run 目录。
- 单次硬件采集只能标记为 `single_run_exploration`；不得作为 final metric evidence 或优化收益声明。

## 输出契约

输出必须包含：

- `profile_mode`：`sim` / `hw-msprof` / `hw-op`。
- `msprof_command`：首选命令、fallback 命令、simulator 命令。
- `required_artifacts`：诊断必须存在的 CSV、trace 或 summary。
- `parser_plan`：每个 metric 对应的文件、字段、公式和输出 key。
- `execution_plan`：执行 msprof 所需的模式、命令参数、输出目录和 summarize/parse 步骤。
- `measurement_policy`：warmup、repeat、统计值选择、稳定性阈值和最小有效提升。
- 执行后输出 `profiling_results.json`：产物清单、缺失项、metric 值、样本、统计、来源文件、字段和公式。

## 输出要求

- 不编造 `msprof` 字段、采集参数或平台规格。
- 所有派生 metric 必须写清楚分子、分母和数据来源。
- 所有 duration / throughput / bandwidth 证据必须带 `samples` 和 `statistics`；默认使用 median 参与 before/after 比较。
- CV 超过阈值、样本数不足或 baseline/candidate policy 不一致时，输出 `measurement_status=measurement_limited`，不要给确定性结论。
- 对 CSV 无法直接支持的问题，明确标注需要 trace/timeline、代码审查、TilingData 或对比实验。
- Treat compressor thresholds as versioned expert heuristics, not calibrated
  probabilities. Preserve `unknown` when theoretical traffic, available core
  count, trace overlap, or instruction granularity is absent.
- 面向用户的采集任务要可执行：说明需要提供哪些文件、字段、shape、dtype、blockDim、TilingData 和平台参数。
- 若输入来自 `diagnosis_hypotheses.json`，必须保留 `linked_hypotheses`，方便最终诊断追溯证据。
- 未经用户确认或环境缺失时，不执行 msprof；仍要输出可执行计划和缺失输入清单。
