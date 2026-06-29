# AProf

AProf 是一个面向 Ascend 算子的 agent-native 性能归因系统。它读取 `msprof op simulator` 产物，结合 NPU 架构模型做 roofline 归因，输出瓶颈分类、缺失证据和下一步 profiling 建议。

本仓库包含四块核心能力：

- **Diagnosis agent**：性能问题 → 硬件 metric 映射（`src/aprof/agents/diagnosis/`）
- **Profiling agent**：profiling 规划与 tool router（`src/aprof/agents/profiling/`）
- **Metric 接口**：架构与 metric 描述契约（`configs/architectures/`、`src/aprof/metrics/`）
- **Benchmark 构建**：injected case 与 reference case（`benchmarks/`）

## 环境要求

- Python >= 3.9
- 离线分析：只需 Python 依赖，可直接分析已有的 msprof 输出目录
- 实机/仿真采集：需要 Linux + CANN + `msprof op simulator`（见 `scripts/env_cann.sh`）

## 快速开始

### 1. 获取代码并安装

```bash
git clone git@github.com:jieran-zhang/Aprof.git
cd Aprof
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

安装后可用：

```bash
aprof --help
python -m aprof skills
```

### 2. 跑通单元测试

```bash
python -m unittest discover -s tests/unit -v
```

### 3. 检查 msprof 环境（可选）

```bash
source scripts/env_cann.sh   # 按本机 CANN 路径调整
aprof probe-env --soc-version Ascend910B1
```

如果当前机器没有 CANN/`msprof`，命令会返回缺失项，不会假装已经采集成功。

## 常用命令

### 分析已有 profiling 产物

当你已经有一个 `msprof op simulator` 输出目录（含 `trace.json` 或 `OPPROF_*`）时：

```bash
aprof analyze \
  --input /path/to/msprof_output \
  --arch configs/architectures/ascend910b1.yaml \
  --out reports/my_case
```

输出目录会生成：

- `summary.json` / `summary.md`：归因结果
- `time_windows.csv`：逐窗口 roofline 输入
- `timeline_utilization.svg` 等可视化文件

### 端到端诊断（可复用已有产物，也可触发采集）

```bash
aprof diagnose \
  --input /path/to/msprof_output \
  --arch configs/architectures/ascend910b1.yaml \
  --out reports/my_case_diagnose
```

如果要在本机直接跑 simulator：

```bash
aprof diagnose \
  --executable ./your_kernel_binary \
  --source-root benchmarks/reference_ops/reduce_sum \
  --arch configs/architectures/ascend910b1.yaml \
  --out reports/my_case_diagnose \
  --soc-version Ascend910B1 \
  --run
```

### 对比优化前后

```bash
aprof compare \
  --before /path/to/before_profile \
  --after /path/to/after_profile \
  --arch configs/architectures/ascend910b1.yaml \
  --out reports/compare
```

### 查看内置 profiling skill 契约

```bash
aprof skills
```

## Benchmark 怎么用

### Reference case：ReduceSum

参考工程在 `benchmarks/reference_ops/reduce_sum/`，包含 AscendC 直调源码、数据生成脚本和 SOP 文档。

```bash
cd benchmarks/reference_ops/reduce_sum
bash run.sh
```

采集 simulator 报告时，参考 skill：`skills/aprof/benchmark/ascendc-msprof-simulator/SKILL.md`。

### Injected case：可控性能问题库

`benchmarks/aprof_injected_ops/` 保存带 ground-truth label 的注入 case，例如：

- `swi_glu/inject_blockdim` → `blockdim_too_small`
- `swi_glu/inject_tail` → `tail_inefficient`
- `swi_glu/inject_tilelen_small` → `tileLength_too_small`

如何构造新的 injected case，见：`skills/aprof/benchmark/ascendc-aprof-inject-problems/SKILL.md`。

### 闭环 label 对齐

```bash
python scripts/run_closed_loop.py
```

该脚本会对 SwiGlu 的 3 个 inject case 做规则诊断，并检查预测标签是否与 `metadata.json.injected_label` 一致。

## Agent Skills 怎么用

仓库内维护的 AProf skills 位于 `skills/aprof/`：

| Skill | 路径 | 用途 |
| --- | --- | --- |
| `ascendc-aprof-diagnosis` | `skills/aprof/diagnosis/` | 性能问题 → metric 诊断矩阵 |
| `ascendc-aprof-profiling` | `skills/aprof/profiling/` | 诊断前规划采集任务 |
| `ascendc-aprof-inject-problems` | `skills/aprof/benchmark/ascendc-aprof-inject-problems/` | 构造 injected benchmark |
| `ascendc-msprof-simulator` | `skills/aprof/benchmark/ascendc-msprof-simulator/` | kernel → msprof simulator 端到端 SOP |

在 Cursor / Agent 中，通常按这个顺序使用：

1. 用 `ascendc-aprof-inject-problems` 或 reference case 准备 benchmark
2. 用 `ascendc-msprof-simulator` 采集 profiling 产物
3. 用 `ascendc-aprof-profiling` 规划缺失 metric
4. 用 `ascendc-aprof-diagnosis` 做归因与下一步建议

## 目录结构

```text
src/aprof/                 # Python 包
configs/architectures/     # 硬件架构与 metric 契约
benchmarks/                # reference / injected / cannbench manifest
skills/aprof/              # Agent skills 与 references
scripts/                   # 环境脚本与闭环 runner
tests/unit/                # 离线单元测试
docs/                      # 架构与 benchmark 文档
```

## 开发说明

- 包入口：`python -m aprof` 或 `aprof`
- 架构配置默认文件：`configs/architectures/ascend910b1.yaml`
- 不建议把 profiling dump（`msprof_sim_output/`、`OPPROF_*`）提交进仓库；`.gitignore` 已忽略这类产物
- 更细的模块说明见 [docs/aprof_architecture_and_msprof_flow.md](docs/aprof_architecture_and_msprof_flow.md)

## 文档

- [架构与 msprof 数据流](docs/aprof_architecture_and_msprof_flow.md)
- [仓库布局说明](docs/inventory.md)
- [添加 msprof benchmark](docs/adding_msprof_benchmark.md)
- [msprof simulator 环境说明](docs/msprof_simulator_setup.md)
