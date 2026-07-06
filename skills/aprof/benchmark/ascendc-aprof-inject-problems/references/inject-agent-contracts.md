# AProf Inject Agent Contracts

本文定义 `aprof-inject-problems-agent` 的结构化输入输出。所有字段必须可追溯；未知值使用 `null`、空数组或 `unknown`，不要编造。

## inject_request.json

用户或 workflow 提供的注入请求。

```json
{
  "op_name": "fast_gelu",
  "source_mode": "existing_aprof_baseline",
  "source_path": "benchmarks/aprof_injected_ops/fast_gelu/baseline",
  "output_root": "benchmarks/aprof_injected_ops/fast_gelu",
  "problem_family": "tilelen_small",
  "variant": "inject_tilelen_small",
  "profile_mode": "sim",
  "remote_verify": true,
  "operator_context": {
    "shape": [2048],
    "dtype": "float32",
    "soc": "dav-3510"
  },
  "constraints": {
    "single_factor_only": true,
    "preserve_math": true,
    "allow_kernel_edit": true,
    "allow_host_edit": false
  }
}
```

字段约束：

- `source_mode` 只能是 `kernel_only`、`scaffold_project`、`existing_aprof_baseline`。
- `problem_family` 使用 `blockdim`、`tail`、`tilelen_small`、`tilelen_large`、`tilenum`、`dynshape`。
- `profile_mode` 使用 `sim`、`hw-msprof`、`hw-op`。`kernel_only` 和 `existing_aprof_baseline` 默认 `sim`。

## inject_manifest.json

每个 injected case 的产物说明，放在 case 根目录。

```json
{
  "schema_version": 1,
  "op_name": "fast_gelu",
  "variant": "inject_tilelen_small",
  "source_mode": "existing_aprof_baseline",
  "source_path": "benchmarks/aprof_injected_ops/fast_gelu/baseline",
  "case_dir": "benchmarks/aprof_injected_ops/fast_gelu/inject_tilelen_small",
  "profile_mode": "sim",
  "ground_truth": {
    "injected_label": "tileLength_too_small",
    "problem_family": "tilelen_small",
    "expected_diagnosis_family": "tiling"
  },
  "knobs_changed": [
    {
      "file": "scripts/gen_data.py",
      "field": "default_tile_length",
      "baseline": 256,
      "injected": 16,
      "reason": "增加 tile 数和循环/同步开销"
    }
  ],
  "kernel_flags": {
    "APROF_INJECT_TAIL": 0,
    "APROF_INJECT_DYNSHAPE": 0
  },
  "allowed_files_changed": [
    "scripts/gen_data.py",
    "op_kernel/aprof_variant_config.h",
    "metadata.json"
  ],
  "quality": {
    "single_factor": true,
    "preserve_math": true,
    "confidence": "high",
    "status": "active",
    "notes": []
  },
  "artifacts": {
    "metadata": "metadata.json",
    "profiling_plan": "profiling_plan.json"
  }
}
```

`quality.status` 使用：

- `active`：可用于 benchmark 与诊断评估。
- `weak`：信号弱或只能作为辅助样例。
- `deprecated_or_weak`：历史 case 保留但不应用于判断准确率。

## profiling_plan.json for inject

每个 case 的远程验证计划，复用 [../../../references/contracts.md](../../../references/contracts.md) 的 `profiling_plan.json`，并允许在 `remote_deploy_args` 中增加 inject 字段：

```json
{
  "plan_id": "inject_sim_fast_gelu_tilelen_small",
  "profile_mode": "sim",
  "mode_reason": "AProf injected sim-only case uses run.sh build/sim and msprof op simulator",
  "required_artifacts": [
    {
      "path_pattern": "msprof_sim_output/**/trace.json",
      "reason": "sim timeline"
    },
    {
      "path_pattern": "*_instr_exe_*.csv",
      "reason": "instruction-level evidence"
    }
  ],
  "remote_deploy_args": {
    "profile_mode": "sim",
    "steps": "upload,build,profile,download",
    "msprof_timeout": 8,
    "remote_env_exports": [
      "APROF_INJECT_COMMON={remote_root}/common",
      "APROF_INJECT_RUN={remote_root}/common/inject_run.sh"
    ]
  }
}
```

## inject_deploy_manifest.json

一个 op 的批量远程验证清单，放在 `benchmarks/aprof_injected_ops/<op>/inject_deploy_manifest.json`。

```json
{
  "schema_version": 1,
  "op_name": "fast_gelu",
  "source_root": "benchmarks/aprof_injected_ops/fast_gelu",
  "inject_common_dir": "benchmarks/aprof_injected_ops/common",
  "profile_mode": "sim",
  "batch_local_out": "benchmarks/aprof_injected_ops/fast_gelu/remote_inject_out",
  "cases": [
    {
      "variant": "inject_tilelen_small",
      "local_dir": "benchmarks/aprof_injected_ops/fast_gelu/inject_tilelen_small",
      "local_out": "benchmarks/aprof_injected_ops/fast_gelu/remote_inject_out/inject_tilelen_small",
      "profiling_plan": "benchmarks/aprof_injected_ops/fast_gelu/inject_tilelen_small/profiling_plan.json",
      "inject_manifest": "benchmarks/aprof_injected_ops/fast_gelu/inject_tilelen_small/inject_manifest.json",
      "ground_truth_label": "tileLength_too_small",
      "quality_status": "active"
    }
  ]
}
```

## validation_summary.json

每个 case 远程验证完成后的汇总，放在 `local_out` 下。

```json
{
  "schema_version": 1,
  "variant": "inject_tilelen_small",
  "ground_truth_label": "tileLength_too_small",
  "profile_mode": "sim",
  "build_pass": true,
  "run_pass": "skipped",
  "profile_pass": true,
  "accuracy_check": "skipped",
  "accuracy_reason": "sim-only inject path has no host execution",
  "has_trace": true,
  "has_instr_exe": true,
  "ready_for_label_alignment": true,
  "deploy_results": "deploy_results.json",
  "artifact_manifest": "artifact_manifest.json",
  "notes": []
}
```

`run_pass` 和 `accuracy_check` 使用 `true`、`false` 或 `skipped`。sim-only case 默认 `skipped`，full-scaffold case 必须给真实结果。

## label_alignment_report.json

由 label alignment 工具或 diagnosis workflow 输出。

```json
{
  "schema_version": 1,
  "op_name": "fast_gelu",
  "cases": [
    {
      "variant": "inject_tilelen_small",
      "ground_truth_label": "tileLength_too_small",
      "predicted_label": "tileLength_too_small",
      "pass": true,
      "confidence": "medium",
      "evidence": [
        "metadata.tile_length=16",
        "trace.json present"
      ]
    }
  ],
  "summary": {
    "total": 1,
    "passed": 1,
    "failed": 0,
    "skipped": 0
  }
}
```
