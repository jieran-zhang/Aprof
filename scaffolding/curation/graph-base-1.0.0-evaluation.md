# Frozen 1.0.0 validation runner

## Current authorized scope (2026-10-15)

The user approved source/SDK-provable UB allocation bounds and narrowed this release to **exp on 910C/A3 with CANN 9.0.0**. Actual SDK/build identity remains required; this policy approval neither establishes a total compiler UB bound nor changes earlier review rejections.

The **45-run comparison and postseal full test suite are `not_run` by explicit user instruction**. Sigmoid will not be rerun; all other rules remain draft. The matrix, paired comparison criterion and related launch requirements below are retained as the historical evaluation design, not pending work for this exp-only release. No comparison benefit or test pass is claimed.

The authorized continuation is complete: the final machine gate returned **`production_safe_gain` with actual exit 0**. It reused the independently replayed prefix at `/tmp/aprof-teacher-boundary-fixed-20261015-ust71pmc/exp`: accepted source review (45,893 actual tokens), one candidate build, both roles of all 20 correctness cases and 42 additional boundaries, independent six-case screen, all 20×30 formal Task pairs and before/after A/A controls. The formal speedup is **1.1885722798×**, with a **1.1882032839×** 95% lower bound; all 20 cases are faster, with no case regression. These are Exp workload results on the stated hardware/SDK, not a 45-run comparison or generalized benefit.

The original baseline PMU's ten warmups, five captures and oracle were retained. Only the missing candidate role ran ten warmups, five captures and its original oracle, using the same registered `mte2_instructions` metric. That continuation then failed when the LocalEvidence wrapper selected the CAS request-registration path. A separate CPU-only gate completion fixed that adapter path and added no build, capture or formal timing pair. Both earlier failures remain unchanged.

| Actual task | Terminal | Recorded process seconds |
| --- | --- | ---: |
| Original trial; profile stdout/stderr parsing failure | failed / exit 2 | 2821.423869 |
| Candidate PMU continuation; gate request registration failure | failed / exit 2 | 337.899868 |
| Gate-only completion | passed / exit 0 | 286.803726 |

The three recorded executions total **3446.127464 seconds**. Including the continuation launch windows, cumulative online cost is **3446.129387 seconds**, within the registered 5400-second allowance. Each prior deadline and failure is retained. Post-task archive and independent publication audit costs remain separate.

The single canonical optimization skill edit and corresponding Exp Wiki/index/evolution promotion are applied. The persistent [promotion receipt](../../../validation-graph-base-1.0.0/exp-teacher-promotion-20261015/promotion.json) is `sha256:33be3448ee471db6899fa9278dc1524fdf7b073ee6ee44425f93c5752c95095c`; the final dispatcher at `/dev/shm/aprof-exp-gate-completion-20261015-rys12h6p/dispatcher-result.json` is `sha256:bafe7eca85b05b66b2315638557c229f65041767224babc9c3ed4a2be2f30fea`. **Independent scoped publication audit and sealing remain pending; 0.5.1 is still the stable default.** This documentation update starts no model, hardware, replay, archive or publication operation. The historical implementation records below retain their original status statements; this section gives the current limited acceptance status.

## Historical 45-run design and implementation record

The stable default is now 0.5.1. The unsealed 1.0.0 candidate is authorized to use
runtime 0.2.3 / Task v5 with per-case complete kernel sequences and task-local
evidence; hardware requalification remains required. The fixed comparison arm remains
the original 0.5.0 knowledge package. The Task controller integration has CPU
coverage; no new rule qualification or 45-run comparison is claimed. Online
verification remains inside each task's budget; a separate collector owns
optional archival after the actual task exit and reports that cost separately.

`scaffolding/collection/scripts/evaluate_skill_release.py` prepares the fixed
five-operator × three-arm × three-seed matrix. Launch requires a qualified
restricted-tool worker, at least one independently accepted skill promotion,
all five baseline hardware qualifications, and a fully frozen evaluation.
Preparing a matrix does not run a model or use an NPU.

The primary comparison is **1.0.0 skill plus on-demand Wiki versus 0.5.0**.
All 15 `(operator, seed)` pairs enter a paired bootstrap of deployed speedup
ratios: 10,000 resamples, RNG seed 4101, percentile two-sided 95% confidence
interval. Its lower bound must exceed 1, with no paired correctness decrease.
The skill-only arm is an ablation and cannot rescue a failing primary result.
Failed/unaccepted candidates retain their cost and use original-baseline
fallback speedup 1. Missing trials prevent publication. The scoring rule is
`PUBLICATION_CRITERION` in the runner and must appear unchanged in the freeze.

The model writes one candidate through an external file-tool broker; only the
trusted host controller can build or execute it. The worker disables execution
and plugin tools and exposes a read-only work tree. Actual tool schemas,
model/effort, CLI and producer hashes are captured by a mock Responses provider
before a qualification receipt can replace the launch blocker. Configuration
booleans or claimed zero builds are insufficient.

The round2 probe of the installed CLI rejected its `ultra` configuration:
the actual request used `max` and exposed execution/delegation tools. Before
any model experiment or evaluation freeze, the selected configuration is now
explicitly `gpt-6-sol` / `max` for every arm and both roles. The tool-only
catalog records the original installed model metadata and exact interface
overrides; these do not change model weights. A fresh actual-request capture
must still prove the finite tool schemas, literal model/effort and absence of
execution/delegation. An override configuration alone is not qualification.

On 2026-10-15 the user replaced the token caps with `time_only_v1`: generation,
independent review, build, correctness, timing, profiling and online admission
initially shared one hard 60-minute deadline, superseded by the adjustable
wall-time amendment below. Model and effort remain identical across roles
and arms. Proposer, reviewer and total tokens (including cached input) are recorded
as actual cost, with no 56k, 8k or 64k rejection threshold. Unknown usage stays
unknown and cannot be invented for publication. Actual timeouts retain their cost
and cannot be repaired by post-task work. The reviewer receives
only anonymous source, diff, contract, frozen boundary inventory and checklist.
Critical fail/unknown stops the candidate without another edit or build.
The first prompt contains losslessly packed contracts and byte-identical deduplicated
sources. One final structured review is bound to the actual model message, later
usage and completed turn. Archival occurs after task exit and is charged separately.
Historical token-budget failures remain unchanged; the new policy applies uniformly
to newly frozen trials, never retroactively to old receipts.

The user subsequently authorized calibrating the wall-time limit too: 60 minutes
is an initial budget setting, not a fixed scientific acceptance threshold.
The next evaluation freeze must choose one explicit shared limit from measured
complete baseline/controller costs, include headroom for generation and independent
review, and apply it equally to all three arms and seeds. No arm may extend its own
budget after seeing its result. Token cost accounting and all non-budget gates stay
unchanged. Collection should finish an already-started bounded acquisition unit and
preserve its records when stopping at a budget boundary; process-hang protection is
separate. This amendment is implemented in the controllers and independent
replayers. Existing launched 3600-second receipts and their actual elapsed times
are retained as originally recorded.

The frozen plan supplies finite positive `budget_seconds = B` and an optional
`finish_started_unit_v1` policy. The original supervisor start fixes `D = start + B`;
subprocesses inherit its remaining time. A reserve `R` covers a complete Task
cycle or PMU unit plus terminal writes. No new collection unit starts after
`D - R`; an already-started unit has its own registered watchdog within `D`.
This preserves complete records at a controlled stopping boundary. Partial
collection remains ineligible, and archival is performed only after actual exit.

The exp/sigmoid Teacher round registered 5400 seconds, with a 600-second reserve;
both attempts ended at source review, without a budget failure. This is not the
45-trial comparison budget. Separate original-baseline probes observed long
complete calls for GQA and weight_quant_batch_matmul. The proposed change to
duration-aware sampling is pending authorization and independent qualification;
neither a longer budget nor these single-call probes qualify the measurement
method. See [current hardware status](graph-base-1.0.0-hardware-validation.md).

The broker supplies controlled list/read/search/replace/submit tools and a
read-only graph_route(context_id). Graph contexts, planning artifacts and
predicate evidence are frozen from qualified baselines. A source claim or Wiki
observation cannot replace a missing calibrated predicate. Wiki bodies are
accessible only through read_wiki in the Wiki arm; its logs record page hashes,
bytes and estimated tokens, separately from actual total model usage.

The three seed labels identify repetitions and run order; they do not seed
model sampling or replace the original workload RNG seeds. All arms use the
same isolated tool environment. The 45-run comparison has not yet been executed.

The root-owned freeze JSON has these fields:

```text
schema_version: 1
state: frozen_for_validation
plan: {path, sha256}
teacher_audit: {path, sha256}
libraries: {baseline: {path, sha256}, candidate: {path, sha256}}
model: {name, reasoning_effort, cli_version}
budget_policy: time_only_v1
model_budgets: {proposer: null, reviewer: null}
worker_qualification: {path, sha256}
toolchain: {identity, files: [{path, sha256}]}
tasks: {operator: {baseline: {path, sha256}, context: {path, sha256}, evaluation_plan: {path, sha256}, baseline_qualification: {path, sha256}, route_registry: {path, sha256}, review_contract: {path, sha256}, review_checklist: {path, sha256}, review_boundaries: {path, sha256}, profiles?: {path, sha256}}}
evaluator: {argv: [...], files: [{path, sha256}], physical_device: 0, logical_device: 0, lock_owner: evaluator, environment: {OMP_NUM_THREADS: '32', MKL_NUM_THREADS: '32', OPENBLAS_NUM_THREADS: '32'}}
target_speedup: <predeclared number greater than 1>
publication_criterion: <PUBLICATION_CRITERION constant>
```

All paths are absolute. Directory hashes use `tree_sha()` (path, content and
mode; Python caches excluded). Library references use `library_sha()`, which
also excludes only the top-level `release.json` seal metadata, so the frozen
payload hash remains replayable after sealing. Source/input payloads receive no
such exclusion. The evaluator command expands `{workspace}`,
`{result}`, `{operator}`, `{seed}`, `{run_id}` and `{seconds}` as individual argv strings, never through
a shell. Its result must contain `counts`, `full_declared_correctness`, all
per-case `cases` (`case_id`, `correct`, `baseline_us`, `candidate_us`), raw
`evidence` path/hash references, `candidate_tree_sha256`, and replayable formal
`trace` and `store` path/hash references. It runs outside the model's root, so
the model cannot write its own measurement receipt. The publication verifier
replays the machine outcome using the candidate's frozen runtime. The formal
evidence must include an `evaluation_case_report` CAS artifact equal to `cases`,
and the gate-bound accuracy report must contain `case_ids` and
`passed_case_ids`. Original/candidate CAS source bundles use the frozen
profiler's JSON `schema_version/files` format; all file objects are verified
and the bundle must match its `source_inventory()` over the worker's clean
source tree. The controller receives a separate copy for building, so its
artifacts cannot change the worker's frozen tree. It owns stage device locks;
the outer job wrapper takes no device lock, avoiding a nested lock with
`device_paired_timing.py`. Physical device visibility and logical device 0 are
passed explicitly. Primary speedup is recomputed from the formal machine outcome.

```bash
python3 scaffolding/collection/scripts/isolated_eval_worker.py --probe
python3 scaffolding/collection/scripts/evaluate_skill_release.py prepare FREEZE.json RUN_DIR
python3 scaffolding/collection/scripts/evaluate_skill_release.py run RUN_DIR RUN_ID
python3 scaffolding/collection/scripts/evaluate_skill_release.py summarize RUN_DIR
```

The standalone `validation_host_evaluator.py` supplies baseline qualification
and one-candidate control. Qualification builds and checks all twenty cases,
then runs A/A-before, a full20 baseline/baseline stand-in, and A/A-after before
source-bound named-kernel profiling. A candidate receives an independent source
review, one build, full correctness, A/A-before, thirty fresh formal pairs per
case, A/A-after, and five captures per role of its predeclared mechanism.
Controller stage events are recorded as they happen against a frozen protocol.
The shared timing_admission verifier replays controls, stdout, source/input/oracle
hashes and the complete stage chain. A stable formal report alone cannot admit
timing; unadmitted observations remain intact with empty gate timing arrays.
Actual hardware receipts, not these entry points, establish qualification.

`validation_operator_adapter.py` stages source and dispatches all five operators,
including GQA's reorder → QK → softmax → PV → scatter sequence and
weight-quantized matmul's dequant → matmul → post sequence. It wraps the complete
operator in the existing event timer and preserves required stage synchronization.
For the two external case specifications, only the exact YAML lookup location
changes; generator and verifier bytes remain unchanged. Preparation produces
source hashes and commands, and explicitly reports that no build, input
generation, model inference or hardware execution has occurred. The timing
configuration requires an independently calibrated repeat count. Full baseline
correctness, timing controls and actual source-bound profiling remain required
before these preparations can enter a freeze.

Task preparation has three explicit stages:

1. Use `validation_operator_adapter.py` to copy the operator and instrument its
   complete timing interval. Generate the declared inputs with its unchanged
   `commands.generate_inputs` list, once for use by every arm/repetition.
2. Use `validation_host_evaluator.py prepare-task` to hash those existing inputs
   and record the fixed repeat count, 910C mapping, sentinel case, named kernel
   choices and exact PMU metric cells. This command does no hardware work.
3. Run `qualify-baseline` for that exact task plan before candidate freeze. Bind
   its qualification receipt, task plan, input/source inventories and every
   evaluator script into the root freeze. Point the model context at the
   generated task `context.json`, which includes the permitted profile choices.

The profile plan is a JSON object with `case_id`, a `kernels` list, and `metrics`
mapping each allowed metric name to `unit`, `file`, `format: csv`, `field`,
`row_aggregation: median` and `aggregation: median`. These choices must be
established from baseline tool capabilities before the model run. The model
must record `actual_parent: "original baseline"`, concrete `source_anchors`
(`path`, one-based `line`, `why`), and one `mechanism` (`case_id`, `kernel`,
`metric`, `expected_direction`) in `candidate_plan.json`. The controller binds
that plan in its TraceWriter proposal before build or performance collection.
Missing/unavailable PMU evidence stays unaccepted; the controller does not
choose a substitute metric after measurement. Named-kernel PMU support is
separate from complete-operator latency and does not prove exclusive causality.
All arm prompts show the exact candidate-plan JSON structure. The controller
conservatively requires host text outside the timed body and CMake controls to
match the original, preserves host launch-site counts/loop headers, and refuses
new host runtime/launch helpers in includes. Candidates that need a wider host
rewrite receive a static rejection under this frozen scope; the controller
does not silently measure a narrower interval.

Production source scope now requires one independent blind review bound to the
source inventories, proposal, model events and token receipts. Its obligations
cover precision/semantics, dynamic tails, task ownership, UB capacity, buffer
lifetimes/synchronization, workspace, complete timing scope and absence of
case-specific answer substitution. The former integer-parameter checker remains
a conservative helper, not a substitute for review. Kernel pipeline/parallel
rewrites can be reviewed; wider host launch/loop/timer rewrites remain outside
this experiment's admitted scope. Every candidate must also replay its selected
legal graph edge and transformation parameters.

An evaluator argv can use:

```text
python3 .../validation_host_evaluator.py evaluate
  --plan /frozen-tasks/{operator}/task-plan.json
  --baseline-receipt /qualified-baselines/{operator}/qualification.json
  --workspace {workspace} --result {result} --run-id {run_id} --seconds {seconds}
```

No evaluation or qualification command runs automatically. Baseline hardware
qualification, an independently accepted skill rule and the root freeze are
still required; protocol probes and unit checks do not replace these receipts.

Every started trial records a terminal result even if staging or worker startup
fails. Such a result reports measured elapsed time, retains available logs and
leaves unavailable model usage unknown. A missing authoritative worker usage
receipt prevents publication; no tokens or hardware gate evidence are invented.

## Second-round status

Implementation and finite hardware qualification are recorded in
[the round2 protocol](graph-base-1.0.0-round2.md). Restricted-tool mock probes and
CPU checks do not qualify a real model run or a hardware gain. The final probe
must bind the actual requested model/effort and the final producer bytes.

New source preparations use the v2 timing header. Input generation, baseline
qualification, promotion and the 45-run comparison are distinct stages with
separate receipts. No 45-run comparison or sealed test evaluation has run.
The stable default remains 0.5.1 until the unchanged 1.0.0 publication gate passes.

## Whole-task deadline supervision (2026-10-15)

`evaluate_skill_release.py run` now dispatches one supervised child for the
entire trial, including source staging, generation, review, candidate execution
and online replay. An immutable attempt/plan/job chain binds the original
monotonic deadline (3600 seconds in the initial implementation; the frozen
parent's configurable B after the amendment above). The actual `run_aprof_job` job carries that
absolute deadline, checks it before spawning, and caps its wait after spawning;
filesystem preparation cannot grant a fresh relative budget. Expired work uses
the existing descendant cleanup. Publication verifies the original launch,
actual execution and logs, child result, elapsed cost and final handoff.

Setup failures retain a failed terminal and available authoritative model usage.
If no process was launched, no successful exit is invented; a missing execution
receipt cannot pass the publication check. Tokens remain recorded costs without
a hard limit. Counts, one-candidate/build constraints and baseline fallback are
unchanged; post-task archival remains separate.

Focused CPU validation: **54 passed in 23.51 seconds**, covering the evaluator,
real process-tree cleanup, delayed prelaunch expiry, absolute timeout, setup
failures and altered deadline/exit bindings. No provider or hardware ran.

- Evaluator source SHA256: `86e36d83337f92fe44dc0212e85424bbb718c2424d619f478a307ba4825045bb`.
- Job runner source SHA256: `0d0bc22f5fbf42cccb0314da61736a02c09eb4feeaf81c6baf8226082bf041ca`.
- Log: `/tmp/aprof-skill-release-supervisor-absolute-v2.log`, SHA256
  `d0a942ee18ab3b9ebd5397e2fa2e2780d681e7a9e972735f09ca93ee56a0ea3a`.

## Task evaluator integration (2026-10-15)

The explicit `measurement_protocol` branch now joins the trusted evaluator to
`task_validation_trial.execute_evaluation`, including the original supervisor
launch and deadline. Its freeze binds each actual baseline plan, qualification,
local evidence index, Context derivation and route registry. Before any model
call, the baseline qualification and all 20 Contexts are independently replayed.
Their budgets and collection policies must match the common comparison plan.

Task input fields are `evaluation_plan`, `baseline_qualification`,
`baseline_local_index`, `context_derivation_ref`, `route_registry`, the original
baseline tree and the unchanged review contracts. `evaluator.task_local_root`
must name an existing canonical directory on a supported local filesystem;
this machine's executable `/dev/shm` is available for the future freeze. The
candidate cannot select this root. Raw/profile files remain at their original
local paths; staging rejects persistent profile-tree copies.

The trusted entry verifies the original reviewed submission and route, constructs
its actual source patch and CandidateDraft, then uses the existing single-build,
full correctness, Task, full-call PMU and runtime finalization path. Scoring and
publication replay the actual episode, both roles of all 20 correctness cases,
the 20-case Task report, and the controller's actual exit under the original
deadline. A completed summary alone does not grant a gain. The original 45-run
matrix and paired publication criterion are unchanged.

Focused CPU checks: **80 passed in 10.54 seconds**. Log:
`/tmp/aprof-task-evaluator-final-cpu-v3-20261015.log`, SHA256
`9c65eb391f269db1af05c0080c1f0ba08ea770ba5dde74848b961978b493dc1f`.
No model, candidate build or NPU was used. Real baseline qualification, at least
one Teacher promotion and the common calibrated budget still block launch.
The proposed duration-aware sampling protocol remains separate and pending.

This replay currently requires the retained task-local paths, source workspaces
and build evidence. It does not yet support deleting those paths and publishing
from an archive alone. A post-task collector may receive the local index; any
later archival and its cost remain outside the optimization task.
