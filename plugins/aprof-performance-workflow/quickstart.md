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

若只想生成计划，不执行远程采集：

```text
@aprof-performance-workflow
只生成 diagnosis_hypotheses.json 和 profiling_plan.json，不执行远程 msprof。
```

若允许远程采集，需要先配置：

```text
scripts/server_config.json
```

然后给出上板所需命令：

```text
run_cmd: ./<binary> <args>
gen_data_cmd: python3 scripts/gen_data.py ...
```

## 产物

典型产物包括：

- `diagnosis_hypotheses.json`：源码阶段的问题假设和最多 3 个 metric。
- `profiling_plan.json`：msprof 命令、远程执行参数和 report 解析方案。
- `remote_out/deploy_results.json`：远程执行结果。
- `remote_out/artifact_manifest.json`：产物是否满足采集计划。
- `final_diagnosis.md`：带硬件数据支撑的最终诊断。

## 边界

- 源码诊断阶段只产生假设，不直接确认瓶颈。
- `sim` 只提供 trace / 指令 / 热点 proxy，不产出 msopprof 8 CSV。
- 真实硬件 metric 优先通过 `hw-op` 或 `hw-msprof` 获取。
