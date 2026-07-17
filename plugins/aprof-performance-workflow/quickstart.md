# AProf Performance Workflow Quickstart

## 安装

从仓库根目录执行：

```bash
bash plugins/aprof-performance-workflow/init.sh
```

如果提示缺少 `ops-profiling` 或 `npu-arch`：

```bash
git submodule update --init third_party/cannbot-skills
```

## 使用方式

在 Cursor 中调用：

```text
@aprof-performance-workflow
请分析这个 Ascend C kernel 的潜在性能问题，并给出需要采集的硬件 metric。
kernel_path: <path/to/kernel.asc>
op_dir: <path/to/direct-invoke-op>
```

推荐 demo 路径（完整可编译工程，无答案泄漏）：

```text
op_dir: benchmarks/aprof_benchmark/fast_gelu/operators/op_0001
```

若只想生成计划，不执行 msprof：

```text
@aprof-performance-workflow
只生成 diagnosis_hypotheses.json 和 profiling_plan.json，不执行 msprof。
```

若允许采集，给出执行所需命令：

```text
run_cmd: ./<binary> <args>
gen_data_cmd: python3 scripts/gen_data.py ...
profiling_output_dir: profiling_out
```

## GLM-5.2 API 盲诊 Demo（不依赖 Cursor）

配置 `configs/secrets/glm.env` 后：

```bash
python plugins/aprof-performance-workflow/demo/run_glm_diagnosis_demo.py
```

说明见 [demo/README.md](demo/README.md)。默认用 `aprof_benchmark/fast_gelu/operators/op_0001`，输出 `demo/out/single_case_diagnosis.json`。

910B 真机采集为可选项：参考 `demo/upload_case_for_hw.example.sh`，或先本机 `bash run.sh hw` 再把 CSV 摘要并入盲诊输入。

## 产物

典型产物包括：

- `diagnosis_hypotheses.json`：源码阶段的问题假设和最多 3 个 metric。
- `profiling_plan.json`：msprof 命令、执行计划和 report 解析方案。
- `profiling_results.json`：采集产物、缺失项和 metric 解析值。
- `profiling_out/`：`msprof` 生成的 CSV、trace 或 summary。
- `final_diagnosis.md`：带硬件数据支撑的最终诊断。

## 边界

- 源码诊断阶段只产生假设，不直接确认瓶颈。
- `sim` 只提供 trace / 指令 / 热点 proxy，不产出 msopprof 8 CSV。
- 真实硬件 metric 优先通过 `hw-op` 或 `hw-msprof` 获取。
- 注入评测场景禁止读取 `.ground_truth/`、`injected_label`、`inject_manifest.json` 等答案文件。
