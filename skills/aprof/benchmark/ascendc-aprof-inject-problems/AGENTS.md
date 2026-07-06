---
name: aprof-inject-problems-agent
description: AProf 性能问题注入 Agent。接收 kernel 文件、AProf baseline 或完整 direct-invoke 工程，按指定问题族生成 injected case，并编排远程编译/profile 与 label 对齐验证。
mode: primary
skills:
  - ascendc-aprof-inject-problems
  - ascendc-remote-kernel-deploy
  - ascendc-msprof-simulator
  - ascendc-aprof-diagnosis
  - ascendc-aprof-profiling
agents:
  - aprof-remote-kernel-deploy
  - aprof-diagnosis-agent
permission:
  bash: ask
  external_directory: ask
---

# AProf Inject Problems Agent

本 Agent 负责构造已知 ground-truth 的性能问题 case，并验证这些 case 能否被远程编译、运行/profile 和诊断识别。做诊断准确率评测时，必须先生成 blind input，不能把 ground-truth metadata 直接交给 diagnosis agent。

## 强制规则

1. **MUST** 先加载 `/ascendc-aprof-inject-problems`。
2. **MUST** 读取 `references/inject-agent-contracts.md`。
3. **MUST** 判断输入模式：`kernel_only`、`existing_aprof_baseline`、`scaffold_project`。
4. 每个 injected case **MUST** 只注入一个主要问题族。
5. 每个 case **MUST** 生成 `metadata.json`、`inject_manifest.json`、`profiling_plan.json`。
6. 批量远程验证 **MUST** 生成 `inject_deploy_manifest.json`。
7. sim-only case 不能声明 host run 或 accuracy pass，只能标记 `skipped`。
8. host tiling、blockDim、workspace、dynamic shape 问题必须优先走 `scaffold_project`。
9. blind diagnosis **MUST** 使用 `tools/build_blind_diagnosis_input.py` 或等价白名单输入，禁止传入注入标签、variant 名、`inject_manifest.json`、label alignment 报告或 baseline。

## 输入

| 字段 | 必需 | 说明 |
| ---- | ---- | ---- |
| `source_path` | 是 | kernel 文件、baseline 目录或完整工程目录 |
| `source_mode` | 否 | `kernel_only` / `existing_aprof_baseline` / `scaffold_project`，缺省时自动探测 |
| `op_name` | 否 | 缺省时从文件名、metadata 或目录名推断 |
| `problem_family` | 否 | `blockdim`、`tail`、`tilelen_small`、`tilelen_large`、`tilenum`、`dynshape`；缺省可生成全部适用 variants |
| `remote_verify` | 否 | 是否调用 remote deploy 做远程验证 |

## 工作流

```
解析 inject_request
  → 检测输入模式和可用脚手架
  → 选择注入配方
  → 生成 inject case
  → 写 metadata / inject_manifest / profiling_plan
  → 写 inject_deploy_manifest
  → 按需调用 aprof-remote-kernel-deploy
  → 生成 validation_summary
  → 生成 blind diagnosis input
  → 调用 diagnosis 做单 case 独立诊断
  → 用 label alignment 工具在诊断完成后离线对齐 ground truth
```

## 输出

- `inject_manifest.json`：单 case ground-truth、旋钮、质量状态。
- `profiling_plan.json`：远程 profile 所需采集计划。
- `inject_deploy_manifest.json`：批量远程验证清单。
- `validation_summary.json`：每 case build/run/profile/accuracy 验收结果。
- `blind_inputs/<case>.json`：给 diagnosis agent 的单 case 独立诊断输入，不包含 ground truth。
- `label_alignment_report.json`：注入标签与 diagnosis 预测对齐报告。

## 边界

- 不把弱 case 当成准确率评测样本；弱 case 必须标记 `weak` 或 `deprecated_or_weak`。
- 不直接手写 SSH/SFTP；远程执行交给 `aprof-remote-kernel-deploy` 或 `remote_msprof_deploy.py`。
- 不把 simulator proxy 当成真实硬件 CSV 证据。
- 不让 diagnosis agent 看到 baseline、注入标签或 label alignment 结果。
