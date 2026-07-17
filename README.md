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
git clone --recurse-submodules git@github.com:jieran-zhang/Aprof.git
cd Aprof
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

如果已经 clone 过但还没拉 submodule：

```bash
git submodule update --init --recursive
```

安装后可用：

```bash
aprof --help
python -m aprof skills
```

### 2. 初始化 CANNBot Skills（推荐）

本仓库通过 git submodule 引入官方 CANNBot skills：

- 路径：`third_party/cannbot-skills`
- 上游：`https://gitcode.com/cann/cannbot-skills`

查看可用 skills：

```bash
aprof cannbot-skills
aprof cannbot-skills ops-profiling
aprof cannbot-skills ops-profiling --show
```

在 Cursor 中直接调用这些 skills：

```bash
bash scripts/link_cannbot_skills.sh
```

该脚本会把 `third_party/cannbot-skills` 和本仓库 `skills/aprof/` 下的 skills 链接到 `.cursor/skills/`。

Python 里也可以直接读取 skill：

```python
from aprof.integrations.cannbot import get_skill_markdown, resolve_skill

skill = resolve_skill("ops-profiling")
text = get_skill_markdown("ops-profiling")
print(skill.path, len(text))
```

### 3. 跑通单元测试

```bash
python -m unittest discover -s tests/unit -v
```

### 4. 检查 msprof 环境（可选）

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

从单个 kernel 搭建直调工程，或继续采集 simulator 报告时，参考 skill：`skills/aprof/benchmark/ascendc-kernel-direct-invoke/SKILL.md`。

### Injected / 匿名注入 case

两套目录，**布局对齐**（agent 可见面不含答案）：

| 目录 | 说明 |
|------|------|
| `benchmarks/aprof_benchmark/fast_gelu` | 金标准 demo：单 kernel → direct-invoke → 匿名 `operators/op_XXXX` |
| `benchmarks/aprof_injected_ops/` | 多算子扩展集（同样：`direct_invoke_baseline` + `operators/op_XXXX` + `.ground_truth`） |

```text
<op>/
├── direct_invoke_baseline/   # 完整可编译直调工程
├── operators/op_XXXX/        # 匿名注入 case（完整工程）
├── benchmark_manifest.json   # 无 problem 标签
└── .ground_truth/            # 维护者专用；诊断禁止读
```

构造新注入 case：`skills/aprof/benchmark/ascendc-aprof-inject-problems/SKILL.md`。  
盲诊约定：`benchmarks/aprof_injected_ops/README.md`、`benchmarks/aprof_benchmark/README.md`。

### GLM 诊断 demo（plugins）

用 `aprof_benchmark/fast_gelu/operators/op_0001` 走通「盲诊输入 → 智谱 GLM-5.2 → JSON」：

```bash
# 配置 configs/secrets/glm.env（见 configs/secrets/glm.env.example）
python plugins/aprof-performance-workflow/demo/run_glm_diagnosis_demo.py
```

Cursor 内完整编排：`@aprof-performance-workflow`（见 `plugins/aprof-performance-workflow/quickstart.md`）。

### 闭环 label 对齐

```bash
python scripts/run_closed_loop.py
```

维护者用 `.ground_truth/case_problem_map.json` 做离线对齐；**不要**把该文件交给诊断 agent。

## Agent Skills 怎么用

仓库内维护的 AProf skills 位于 `skills/aprof/`：

| Skill | 路径 | 用途 |
| --- | --- | --- |
| `ascendc-aprof-diagnosis` | `skills/aprof/diagnosis/` | 性能问题 → metric 诊断矩阵 |
| `ascendc-aprof-profiling` | `skills/aprof/profiling/` | 诊断前规划采集任务 |
| `ascendc-aprof-inject-problems` | `skills/aprof/benchmark/ascendc-aprof-inject-problems/` | 构造 injected benchmark |
| `ascendc-kernel-direct-invoke` | `skills/aprof/benchmark/ascendc-kernel-direct-invoke/` | kernel → direct-invoke 工程，可选 simulator 采集 |

CANNBot 官方 skills（如 `ops-profiling`、`npu-arch`、`ascendc-direct-invoke-template`）位于 `third_party/cannbot-skills/`，可通过 `aprof cannbot-skills` 查看。

在 Cursor / Agent 中，通常按这个顺序使用：

1. 用 `ascendc-aprof-inject-problems` 或 reference case 准备 benchmark
2. 用 `ascendc-kernel-direct-invoke` 搭直调工程并按需采集 simulator profiling 产物
3. 用 `ascendc-aprof-profiling` 规划缺失 metric
4. 用 `ascendc-aprof-diagnosis` 做归因与下一步建议
5. 需要更完整的 Ascend/CANN 能力时，调用 `third_party/cannbot-skills` 中的技能，例如 `ops-profiling`、`npu-arch`、`ascendc-direct-invoke-template`

## 目录结构

```text
src/aprof/                 # Python 包
third_party/cannbot-skills # CANNBot 官方 skills（git submodule）
configs/architectures/     # 硬件架构与 metric 契约
configs/secrets/           # API Key 模板（真实 key 本地 gitignore）
benchmarks/                # aprof_benchmark / aprof_injected_ops / reference
skills/aprof/              # AProf 本地 Agent skills 与 references
plugins/                   # Cursor/Claude plugin（含 GLM 诊断 demo）
scripts/                   # 环境脚本与闭环 / 远程 runner
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
- [GLM 盲诊 Demo](docs/glm_diagnosis_demo.md)
- [注入 ops agent 可见面](benchmarks/aprof_injected_ops/README.md)
- [aprof_benchmark 金标准布局](benchmarks/aprof_benchmark/README.md)
