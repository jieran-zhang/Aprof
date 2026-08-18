# AProf Optimization Strategy Routing

This reference is the human-readable cold-start prior used to build the seed SkillGraph. It is not the runtime routing contract. The six historical families are non-exclusive facets; typed graph edges and transformation contracts are authoritative after `v0001` is published.

## Routing Order

1. **Evidence first**: use diagnosis predicates and provisional mechanisms. Historical `problem_family` values may supply multiple facet priors. Preserve linked hypotheses, metrics, missing evidence, and refuting evidence.
2. **Profiling bound second**: if diagnosis families are absent, map profiling evidence to a family. MTE/Memory -> `data_movement`; overlap/bubble -> `pipeline_parallel`; UB/resource conflict -> `onchip_memory`; core occupancy/load balance -> `ai_core_utilization`; vector/scalar/API -> `api_algorithm`.
3. **Source scan fallback**: inspect `tileLength`, `blockDim`, `DataCopy`, `InitBuffer`, `TBuf/TQue`, `SetFlag/WaitFlag`, `MatMul/MMAD`, `Softmax`, `Sort/TopK`, `Reduce`, `GetValue/SetValue`, `std::`, and vector API usage. If evidence remains insufficient, route to `unknown_unresolved` or `NOOP` rather than forcing a family.

## Context-safe Loading

- Default reads: this file, `optimization-candidate-design.md`, and 1 selected family reference.
- Complex operator candidate reads exactly one additional operator playbook:
  `matmul-optimization-playbook.md`, `softmax-fa-optimization-playbook.md`,
  `reduction-sort-optimization-playbook.md`, or `vector-scalar-pipeline-playbook.md`.
- Do not default-load `ascendc-perf-optimize`, `ascendc-tiling-design`, `ascendc-performance-best-practices`, or `ascendc-api-best-practices`.
- Use `optimization-cannbot-knowledge-index.md` only when API overload, repeat/mask, pipeline event, MatMul/FA/Sort/Softmax mechanism, or platform boundary is unresolved.
- A CANNBot point-read may refine a candidate, but it cannot replace AProf diagnosis/profiling/workload evidence.

## Common Workflow Guards

- **EnvironmentPreflight**: run or require CANN env, device visibility, SoC/NPU arch, and `msprof`/`cannsim` readiness before local gates.
- **Workload/Tiling/Bound Modeling**: estimate multicore split, UB/L1/L0/workspace capacity, per-core work, traffic lower bound, and roofline/bound interpretation before patching.
- **CorrectnessAndGeneralityGate**: default every strategy to `production_safe`. Preserve math semantics, dtype precision, dynamic shape/tiling, tail handling, and boundary safety before considering speedup.
- **API lookup before risky edits**: use the optional knowledge index before changing API overloads, `DataCopyPad`, Cast mode, queue/buffer calls, MatMul/FA strategy, Sort/TopK algorithm, or repeat/mask semantics.
- **StaticReview**: after patching and before build, check API legality, UB/L1/L0/workspace bounds, DataCopy alignment, pipeline ordering, portability, and performance clauses.
- **Failure handoff**: accuracy failure -> `ascendc-precision-debug`; runtime nonzero/error code -> `ascendc-runtime-debug`; timeout/crash/AIC error -> `ascendc-crash-debug`; metric regression -> record memory and try next candidate; profile evidence missing -> `ops-profiling`.
- **Simulator label**: cannsim/msprof simulator data is proxy evidence unless validated against real hardware `msprof`/CSV artifacts.
- **Benchmark specialization label**: hardcoded shape/core/UB/tile constants, removed dynamic tiling, reduced precision, or narrowed supported boundary cases must set `scope_status=benchmark_specialized`.

## Six-Facet Expert-Prior Matrix

| Problem family | Trigger signals | Candidate strategy | Local reference | Expected metric movement | Contraindications |
| --- | --- | --- | --- | --- | --- |
| `tiling` | tile too small/large, tail slow path, bad task shape, MatMul/FA split mismatch | task/tile/shape decomposition, tail unification, Vec/UB vs Cube/L1+L0 two-level split, MatMul/FA/Sort/Reduction tiling choice | `tiling-optimization-strategies.md` | larger useful copy bytes, lower tail/core imbalance, better CUBE/MTE/Fixpipe balance | UB/L1/L0 budget unknown, dynamic shape missing, padding may enter compute |
| `data_movement` | small DataCopy, non-aligned copy, redundant GM round trips, low bandwidth with high MTE | true/false memory-bound split, coalesce copy, DataCopyPad with valid count, L2/reuse, resident small params | `data-movement-optimization-strategies.md` | lower MTE instruction count, lower GM bytes, better useful bytes/instruction | padded values consumed, true bandwidth bound, copy lifetime unclear |
| `pipeline_parallel` | low overlap, no-bound bubble, DB configured but serial, PING/PONG gap, AIC/AIV wait | prolog/steady/drain rewrite, event decoupling, UnitFlag/preload/early issue, StreamK sync repair | `pipeline-parallel-optimization-strategies.md` | higher stage overlap, lower wait/gap, shorter duration without extra GM traffic | loop trip too small, UB cannot fit queue depth, sync is algorithmically required |
| `onchip_memory` | UB footprint too high, repeated small param loads, bank conflict, workspace slot issues | lifetime reuse, UB/L1/L0 resident, zone reuse, layout/padding, workspace slot split | `onchip-memory-optimization-strategies.md` | lower UB footprint, fewer GM reloads, lower conflict/wait | lifetime alias unclear, conflict evidence absent, resident squeezes main tile |
| `ai_core_utilization` | active cores low, tail/core imbalance, MN underparallel long K, FA decode task shortage | task decomposition, StreamK/DP+SK, split-KV, group/reduction/sort stage parallelism | `ai-core-utilization-optimization-strategies.md` | more useful active cores, lower per-core variance, lower stage tail | tiny workload, hardcoded core count, workspace reduce or numerical proof missing |
| `api_algorithm` | Scalar/API overhead, repeat limit risk, Cast/reduce/softmax/sort inefficient, GM round trips in API chain | Scalar rewrite, vector repeat/Counter mode, Cast fusion, online softmax, MrgSort/Reduce/MatMul API-local replacement | `api-algorithm-optimization-strategies.md` | lower Scalar/misc, higher vector efficiency, fewer GM round trips | API/platform support unknown, precision mode changes, fusion exceeds UB |

## Required `optimization_plan.json` Linkage

Each strategy entry must include:

- `problem_family`
- `linked_hypotheses`
- `linked_metrics`
- `bound_type`
- `optimization_scope`
- `semantic_requirements`
- `structural_edits`
- `capacity_model`
- `abort_conditions`
- `required_evidence`
- `expected_metric_delta`
- `pre_patch_checks`
- `post_patch_checks`
- `failure_handoff`

If a field cannot be populated from diagnosis/profiling, keep an empty list or `"unknown"` and state which evidence is missing in `notes`; do not invent metrics.

For executable candidates, map the strategy fields to:

- `decision_gate`: `required_evidence` plus source/profiling trigger and contraindications.
- `capacity_formula`: `capacity_model`.
- `structural_patch_shape`: `structural_edits`.
- `metric_delta`: `expected_metric_delta`.
- `abort_conditions`: `abort_conditions`.

## Candidate Acceptance

Before selecting a candidate as `best_op`, require:

- `build_status=passed`, `accuracy_status=passed`, `profile_status=passed`.
- profiling evidence uses warmup/repeat and `measurement_status=stable`.
- `semantic_status=preserved`.
- `scope_status=production_safe`.
- `portability_risk` is not `high`.
- `accepted_for` contains `production`.

If a faster candidate fails these checks, keep it in `final_optimization_report.md` under rejected or benchmark-only candidates with its speedup and rejection reason.
