# AProf Repository Layout

This repository contains the maintained AProf performance diagnosis system plus CANNBot skills integration.

## Python package (`src/aprof/`)

| Module | Role |
| --- | --- |
| `agents/diagnosis/` | Performance problem → hardware metric mapping |
| `agents/profiling/` | Profiling planner, harness, tool router |
| `metrics/` | Architecture model and metric contracts |
| `profiling/` | msprof parsing, case I/O, skill registry |
| `benchmarks/` | Benchmark registry, closed loop, CANNBench adapter |
| `reports/` | Analysis, comparison, diagnosis reports |
| `integrations/` | CANNBot skills path resolution and lookup |
| `cli/` | `python -m aprof` entrypoints |

## Root assets

| Path | Role |
| --- | --- |
| `configs/architectures/` | Hardware metric YAML contracts |
| `benchmarks/aprof_injected_ops/` | Injected benchmark case sources |
| `benchmarks/reference_ops/` | Reference AscendC workloads |
| `benchmarks/cannbench/` | CANNBench adapter manifest |
| `skills/aprof/` | AProf-local diagnosis/profiling/benchmark skills |
| `third_party/cannbot-skills/` | Upstream CANNBot skills git submodule |
| `scripts/` | Environment setup, closed-loop runner, Cursor skill linker |
| `tests/unit/` | Offline unit tests |

## Intentionally excluded

- Profiling dumps (`msprof_sim_output/`, `OPPROF_*`, `dump/`)
- Build artifacts (`build/`, `build_sim/`, `*.o`)
- Generated diagnosis outputs under benchmark cases
