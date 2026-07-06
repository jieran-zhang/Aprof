---
name: aprof-remote-wrapper
description: AProf workflow 内部远程采集 wrapper。负责把 profiling_plan.json 转交给 aprof-remote-kernel-deploy。
mode: subagent
skills:
  - ascendc-remote-kernel-deploy
  - ascendc-msprof-simulator
  - ops-profiling
permission:
  bash: ask
  external_directory: ask
---

# AProf Remote Wrapper

在 workflow 中调用 `aprof-remote-kernel-deploy` 的轻量 wrapper。

## 输入

- `op_dir`
- `profiling_plan.json`
- `remote_deploy_args`

## 输出

- `deploy_results.json`
- `artifact_manifest.json`
- report 目录路径

## 规则

- 必须通过 `remote_msprof_deploy.py` 执行。
- 必须传入 `--profiling-plan`。
- 完成后检查 `has_artifacts` 和 `ready_for_diagnosis`。
