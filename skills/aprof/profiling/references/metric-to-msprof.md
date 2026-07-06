# Metric To msprof

本文将硬件 metric 转换为可执行的 msprof 采集模式和命令模板。具体远程执行交给 `aprof-remote-kernel-deploy`。

## 模式选择

| 需要的 metric / report | 优先模式 | 原因 |
| ---------------------- | -------- | ---- |
| `OpBasicInfo.csv`、`PipeUtilization.csv`、`Memory.csv`、`ArithmeticUtilization.csv`、`ResourceConflictRatio.csv`、`L2Cache.csv`、`MemoryUB.csv`、`MemoryL0.csv` | `hw-op` | msopprof 标准 CSV 最适合 diagnosis 矩阵 |
| 7 组 `aic-metrics`、sample、`remote_hw_summary.txt`、主 bound 摘要 | `hw-msprof` | `ops-profiling` 脚本可封装多组硬件指标 |
| `trace.json`、`*_instr_exe_*.csv`、`*_code_exe_*.csv`、timeline/proxy 指标 | `sim` | `msprof op simulator --config` 可在无 NPU 环境产生 timeline 和指令热点 |

## 命令模板

### hw-op

```bash
msprof op --warm-up=<warm_up> --output=../msprof_hw_output ./<binary> <args>
```

远程工具参数：

```bash
python skills/aprof/remote-kernel-deploy/tools/remote_msprof_deploy.py \
  --local-dir <op_dir> \
  --profile-mode hw-op \
  --run-cmd "./<binary> <args>" \
  --gen-data-cmd "<optional_data_cmd>" \
  --warm-up <warm_up> \
  --summarize
```

### hw-msprof

```bash
bash ../ops_profiling/scripts/msprof_profile_run.sh \
  --warm-up=<warm_up> \
  --output=../msprof_hw_output \
  -- ./<binary> <args>
```

远程工具参数：

```bash
python skills/aprof/remote-kernel-deploy/tools/remote_msprof_deploy.py \
  --local-dir <op_dir> \
  --profile-mode hw-msprof \
  --run-cmd "./<binary> <args>" \
  --gen-data-cmd "<optional_data_cmd>" \
  --warm-up <warm_up> \
  --summarize
```

### sim

```bash
msprof op simulator \
  --config=./op_config.json \
  --output=../msprof_sim_output \
  --timeout="${MSPROF_TIMEOUT:-8}"
```

远程工具参数：

```bash
python skills/aprof/remote-kernel-deploy/tools/remote_msprof_deploy.py \
  --local-dir <op_dir> \
  --profile-mode sim \
  --msprof-timeout 8
```

Simulator 约束：

- 必须使用 `--config`，不要使用 `--application`。
- 不要为 simulator 添加 `--aic-metrics=PipeUtilization`。
- 不要声称 sim 会产出 `PipeUtilization.csv` 或 `Memory.csv`。

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
- 若用户尚未提供 `run_cmd`，在 `remote_deploy_args.run_cmd` 中保留 `./<binary> <args>`，并在 `notes` 中要求补充。
