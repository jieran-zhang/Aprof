# AProf Repository Layout

This repository contains only the maintained AProf performance diagnosis system.

## Python package (`src/aprof/`)

| Module | Role |
| --- | --- |
| `agents/diagnosis/` | Performance problem → hardware metric mapping |
| `agents/profiling/` | Profiling planner, harness, tool router |
| `metrics/` | Architecture model and metric contracts |
| `profiling/` | msprof parsing, case I/O, skill registry |
| `benchmarks/` | Benchmark registry, closed loop, CANNBench adapter |
| `reports/` | Analysis, comparison, diagnosis reports |
| `cli/` | `python -m aprof` entrypoints |

## Root assets

| Path | Role |
| --- | --- |
| `configs/architectures/` | Hardware metric YAML contracts |
| `benchmarks/aprof_injected_ops/` | Injected benchmark case sources |
| `benchmarks/reference_ops/` | Reference AscendC workloads |
| `benchmarks/cannbench/` | CANNBench adapter manifest |
| `skills/aprof/diagnosis/` | Diagnosis skill + reference matrices |
| `skills/aprof/profiling/` | Profiling design skill |
| `skills/aprof/benchmark/` | Inject-problems and msprof-simulator skills |
| `scripts/` | Environment setup and closed-loop runner |
| `tests/unit/` | Offline unit tests |

## Intentionally excluded

- Profiling dumps (`msprof_sim_output/`, `OPPROF_*`, `dump/`)
- Build artifacts (`build/`, `build_sim/`, `*.o`)
- Generated diagnosis outputs under benchmark cases
- External CANNBot skill library and legacy backup trees
