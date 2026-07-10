# AProf Inject Agent Contracts

All fields must be traceable. Unknown values use `null`, empty arrays, or `"unknown"`; do not invent validation evidence.

## inject_request.json

```json
{
  "op_name": "fast_gelu",
  "source_mode": "existing_aprof_baseline",
  "source_path": "benchmarks/aprof_injected_ops/fast_gelu/baseline",
  "output_root": "benchmarks/aprof_injected_ops/fast_gelu",
  "problem_family": "data_movement",
  "problem_id": "redundant_copyin",
  "variant": "inject_redundant_copyin",
  "profile_mode": "hw-op",
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

Constraints:

- `source_mode`: `kernel_only`, `existing_aprof_baseline`, or `scaffold_project`.
- `problem_family`: `tiling`, `data_movement`, `pipeline_parallel`, `onchip_memory`, `ai_core_utilization`, or `api_algorithm`.
- `problem_id`: concrete recipe id from `inject-problems-meta.md`.
- Legacy family aliases `blockdim`, `tail`, `tilelen_small`, `tilelen_large`, `tilenum`, and `dynshape` may be used only as shorthand for tiling recipes.
- `profile_mode`: `sim`, `hw-msprof`, or `hw-op`.

## inject_manifest.json

Each generated case writes `inject_manifest.json` in its root.

```json
{
  "schema_version": 2,
  "op_name": "fast_gelu",
  "variant": "inject_redundant_copyin",
  "source_mode": "existing_aprof_baseline",
  "source_path": "benchmarks/aprof_injected_ops/fast_gelu/baseline",
  "case_dir": "benchmarks/aprof_injected_ops/fast_gelu/inject_redundant_copyin",
  "profile_mode": "sim",
  "ground_truth": {
    "injected_label": "redundant_copyin",
    "problem_family": "data_movement",
    "problem_id": "redundant_copyin",
    "expected_diagnosis_family": "data_movement"
  },
  "applicability": {
    "status": "applied",
    "source_modes": ["existing_aprof_baseline", "scaffold_project"],
    "patch_results": [
      {"patch_id": "redundant_copyin", "applied": true, "reason": "applied"}
    ]
  },
  "knobs_changed": [
    {
      "field": "APROF_INJECT_REDUNDANT_COPYIN",
      "injected": 1,
      "reason": "requires Memory.csv or trace proxy to confirm redundant MTE2"
    }
  ],
  "kernel_flags": {
    "APROF_INJECT_REDUNDANT_COPYIN": 1
  },
  "allowed_files_changed": [
    "op_kernel/fast_gelu_kernel.asc",
    "op_kernel/aprof_variant_config.h",
    "metadata.json"
  ],
  "quality": {
    "single_factor": true,
    "preserve_math": true,
    "confidence": "pending_validation",
    "status": "unverified",
    "notes": ["requires build/run/profile validation before active use"]
  },
  "artifacts": {
    "metadata": "metadata.json",
    "profiling_plan": "profiling_plan.json"
  }
}
```

`applicability.status`:

- `applied`: recipe changed the requested source safely.
- `unsupported`: source mode or kernel shape did not support the recipe.
- `unverified`: reserved for imported/manual cases where applicability cannot be audited.

`quality.status`:

- `active`: build/run/profile evidence passed; may count toward diagnosis accuracy.
- `unverified`: generated but not fully validated yet.
- `unsupported`: should not be built/profiled unless debugging the recipe.
- `weak` / `deprecated_or_weak`: retained but excluded from accuracy.

## profiling_plan.json

Per-case profiling plans follow `skills/aprof/references/contracts.md#profiling_planjson` and add inject-specific remote deploy args:

```json
{
  "plan_id": "inject_hw-op_fast_gelu_inject_redundant_copyin",
  "profile_mode": "hw-op",
  "mode_reason": "data_movement/redundant_copyin requires validation before active label use",
  "required_artifacts": [
    {"path_pattern": "msprof_hw_output/OPPROF_*/Memory.csv", "reason": "real memory traffic and MTE counts"},
    {"path_pattern": "msprof_hw_output/OPPROF_*/PipeUtilization.csv", "reason": "pipe utilization and per-core timing"}
  ],
  "remote_deploy_args": {
    "profile_mode": "hw-op",
    "steps": "upload,build,profile,download",
    "msprof_timeout": 8,
    "remote_env_exports": [
      "APROF_INJECT_COMMON={remote_root}/common",
      "APROF_INJECT_RUN={remote_root}/common/inject_run.sh"
    ]
  }
}
```

Sim-only cases may request trace and `*_instr_exe_*.csv`, but those artifacts are proxy evidence only.

## inject_deploy_manifest.json

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
      "variant": "inject_redundant_copyin",
      "local_dir": "benchmarks/aprof_injected_ops/fast_gelu/inject_redundant_copyin",
      "local_out": "benchmarks/aprof_injected_ops/fast_gelu/remote_inject_out/inject_redundant_copyin",
      "profiling_plan": "benchmarks/aprof_injected_ops/fast_gelu/inject_redundant_copyin/profiling_plan.json",
      "inject_manifest": "benchmarks/aprof_injected_ops/fast_gelu/inject_redundant_copyin/inject_manifest.json",
      "ground_truth_label": "redundant_copyin",
      "problem_family": "data_movement",
      "problem_id": "redundant_copyin",
      "applicability_status": "applied",
      "quality_status": "unverified"
    }
  ]
}
```

## validation_summary.json

```json
{
  "schema_version": 1,
  "variant": "inject_redundant_copyin",
  "ground_truth_label": "redundant_copyin",
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

For full direct-invoke projects, `run_pass` and `accuracy_check` must be real booleans. For sim-only cases they remain `"skipped"`.

## label_alignment_report.json

Label alignment is an offline step after blind diagnosis:

```json
{
  "schema_version": 1,
  "op_name": "fast_gelu",
  "cases": [
    {
      "variant": "inject_redundant_copyin",
      "ground_truth_label": "redundant_copyin",
      "problem_family": "data_movement",
      "problem_id": "redundant_copyin",
      "predicted_label": "redundant_copyin",
      "status": "pass",
      "quality_status": "active"
    }
  ],
  "summary": {
    "total": 1,
    "passed": 1,
    "failed": 0,
    "pending": 0,
    "skipped": 0
  }
}
```

Do not pass this file, `inject_manifest.json`, `metadata.json.injected_label`, `problem_id`, or variant names to diagnosis.
