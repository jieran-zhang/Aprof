---
name: ascendc-aprof-inject-problems
description: Generate synthetic Ascend C performance benchmark cases with hidden ground truth. Use only for benchmark construction, controlled evaluation, or data-generation experiments; keep it separate from the production AProf optimization workflow and never treat generated recipes as verified SkillGraph priors.
---

# AscendC AProf Inject Problems

Use this skill to create benchmark variants with known performance-problem ground truth while preserving mathematical correctness and buildability.

This is a benchmark-generation system, not part of the production AProf
SkillGraph. Generated cases may enter a training or evaluation pool only through
an explicit dataset adapter after single-factor, correctness, slowdown, lineage,
and leakage checks. Do not install this skill as a dependency of the core AProf
workflow and do not import its labels into online diagnosis traces.

## Workflow

1. Read `references/inject-agent-contracts.md`.
2. Detect `source_mode`:
   - `existing_aprof_baseline`: AProf sim-only baseline, usually under `benchmarks/aprof_injected_ops/<op>/baseline/`.
   - `scaffold_project`: complete direct-invoke project with CMake/host runner.
   - `kernel_only`: single kernel file; first create a direct-invoke scaffold with `/ascendc-kernel-direct-invoke`.
3. Choose `problem_family` and `problem_id`. Use `tools/inject_case.py --list-recipes` to inspect supported recipes.
4. Load the relevant family reference:
   - `references/tiling-inject.md`
   - `references/data-movement-inject.md`
   - `references/pipeline-parallel-inject.md`
   - `references/onchip-memory-inject.md`
   - `references/ai-core-utilization-inject.md`
   - `references/api-algorithm-inject.md`
5. Generate the case with `tools/inject_case.py`.
6. Validate structure with `tools/validate_inject_cases.py`.
7. Build/run/profile locally or through `/ascendc-remote-kernel-deploy`.
8. Mark a case `active` only after build and required run/profile evidence pass. Newly generated cases default to `unverified`.
9. For diagnosis evaluation, build blind inputs with `tools/build_blind_diagnosis_input.py`; never pass ground truth to diagnosis.

## Recipe Command

```bash
python skills/aprof/benchmark/ascendc-aprof-inject-problems/tools/inject_case.py \
  --source-mode existing_aprof_baseline \
  --source-path benchmarks/aprof_injected_ops/fast_gelu/baseline \
  --output-root benchmarks/aprof_injected_ops/fast_gelu \
  --problem-family data_movement \
  --problem-id redundant_copyin
```

Legacy aliases are still accepted when `--problem-id` is omitted:

```bash
--problem-family tilelen_small
--problem-family tail
--problem-family blockdim
```

## Quality Rules

- Every case injects one primary problem only.
- `inject_manifest.json.ground_truth` must include `problem_family`, `problem_id`, and `injected_label`.
- `quality.status=active` is reserved for cases with completed build/run/profile validation.
- `quality.status=unverified` is the default after generation.
- `quality.status=unsupported` means the recipe could not find a safe source-code anchor or the source mode is not applicable.
- `quality.status=weak` / `deprecated_or_weak` samples must not count toward diagnosis accuracy.
- `kernel_only` inputs must not be treated as runnable until `/ascendc-kernel-direct-invoke` produces a complete IO-aware scaffold.

## Validation And Evaluation

```bash
python skills/aprof/benchmark/ascendc-aprof-inject-problems/tools/validate_inject_cases.py \
  --op-root benchmarks/aprof_injected_ops/fast_gelu

python skills/aprof/benchmark/ascendc-aprof-inject-problems/tools/build_inject_deploy_manifest.py \
  --op-root benchmarks/aprof_injected_ops/fast_gelu \
  --write-case-plans

python skills/aprof/benchmark/ascendc-aprof-inject-problems/tools/build_blind_diagnosis_input.py \
  --case-dir benchmarks/aprof_injected_ops/fast_gelu/inject_redundant_copyin \
  --trace <trace.json> \
  --out benchmarks/aprof_injected_ops/fast_gelu/blind_inputs/case.json
```

Label alignment must use blind diagnosis outputs. Do not expose `metadata.json.injected_label`, `problem_id`, `inject_manifest.json`, audit reports, or variant names to the diagnosis agent.

## Related Skills

- Direct-invoke scaffolding: `skills/aprof/benchmark/ascendc-kernel-direct-invoke`
- Remote build/profile: `skills/aprof/remote-kernel-deploy`
- Profiling plan and report parsing: `skills/aprof/profiling`
- Diagnosis matrices: `skills/aprof/diagnosis`
