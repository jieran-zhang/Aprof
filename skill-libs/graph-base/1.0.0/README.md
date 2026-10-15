# AProf graph-base 1.0.0 — exp-only release

This package has a user-authorized **exp-only** release scope on Ascend
910C/A3 with CANN 9.0.0. The exp continuation passed the complete online gate
with `production_safe_gain` and a real process exit code of 0. Package sealing
and independent installation are separate release checks; `release.json` and
its verified payload establish the sealed package identity.

This scope covers only `exp-tile8192`. The original 45-run equal-budget
comparison and post-seal full test evaluation are **not run** under this scope
amendment. There is no claim that 1.0.0 improves agent optimization performance
across the five validation operators. Sigmoid, norm, masked_scale, mish,
addcdiv and the other conditional rules remain draft.

## Package and evidence scope

The package preserves the discoverable `skills/<name>` entries and immutable
SkillGraph v0001/v0002. The authorized runtime 0.2.3 and Task v5 changes bind each
case and role to its complete ordered kernel sequence. Evidence for this exp
proposal does not qualify every operator, multi-kernel workload or hardware
platform supported by that interface.

`experience/diagnosis/` and `experience/optimization/{parallel,execution}/`
provide short reading entries. `wiki/` retains ten conditional experience
pages, their source index and an evolution log. Only the exp page and its
single canonical skill revision are validated in this scoped release; the
broader `tile-amortization` page remains draft.
Wiki observations are not policy rewards, and the runtime does not load the
Wiki automatically.

The same exp source and combined binary retain independently replayed full
correctness for 20 cases, 42 boundary checks, controls and formal Task timing
with 30 pairs per case. The formal geometric-mean speedup is **1.1885722798×**,
with a 95% lower bound of **1.1882032839×** and no regression cases. The missing
candidate mechanism collection is now complete: `aiv_mte2_instructions` is
44 in each of five candidate captures versus 87 in each of five retained
baseline captures; the candidate oracle passed. The final gate replay accepted
the complete evidence. The original attempt failed during oracle-output
parsing, and the PMU continuation failed on an evidence binding; both keep
their failed statuses. The successful gate-only continuation made no new build,
PMU capture or formal timing sample. Its actual execution took 286.804 seconds;
the retained original and PMU-continuation executions took 2821.424 and 337.900
seconds, respectively. The total was about 57.44 minutes, including failed stages.

Optimization uses task-local `LocalEvidence`. Full correctness, Task parsing,
controls, profiling and online machine admission belong to the task budget.
Return code and a small report. If trace or training collection is requested,
handoff the local index after task completion and before cleanup. A separate
collector owns permanent copying, CAS registration and archival audit, and
reports those costs separately. The optimization agent does not copy raw
profiles into a persistent directory. Archival cannot upgrade a failed gate.

## Read and audit

Start with `skills/ascendc-aprof-workflow/SKILL.md`. Load the stage skill, and
read one Wiki page when its conditions, conflicts or counterexamples could
change a decision. SkillGraph governs legal routes; `aprofctl` governs
correctness and performance admission. Unknown predicates stay unknown.

From the repository root, check graph and split integrity:

```bash
python3 scaffolding/tools/compile_graph_v2.py \
  --skill-lib "$PWD/skill-libs/graph-base/1.0.0" --check
python3 scaffolding/benchmarks/cannbench/validate_splits.py
```

The exp-scoped publication verifier runs the Teacher audit with the pinned
continuation promotion, original failed-attempt archive, source inventory and
scope amendment. Sealing requires the explicit `--scoped-publication` report
and `--scope-amendment-sha256` arguments to
`scaffolding/tools/release_skill_lib.py`; a component summary is insufficient.
The scope amendment declares `validation_45: not_run`,
`postseal_full_tests: not_run` and `other_rules: draft`.

The release maintainer supplies the frozen source identity, scoped report and
trusted amendment hash when sealing:

```bash
python3 scaffolding/tools/release_skill_lib.py seal \
  --skill-lib "$PWD/skill-libs/graph-base/1.0.0" \
  --source-commit "$SOURCE_COMMIT" --source-version "$SOURCE_VERSION" \
  --scoped-publication "$SCOPED_PUBLICATION_REPORT" \
  --scope-amendment-sha256 "$SCOPE_AMENDMENT_SHA256"
```

After sealing, verify the package bytes and registry independently:

```bash
python3 scaffolding/tools/release_skill_lib.py check \
  --skill-lib "$PWD/skill-libs/graph-base/1.0.0"
```

The standalone Teacher CLI does not supply the continuation promotion closure
and is not a substitute for this scoped publication check.

The curation inventory binds `optimization-traces/index.json` and the current
CANNBench split by SHA-256. Raw traces stay outside the installed package.
Validation/test traces and historical Level2 attempts are not training sources
for these pages. Historical `benchmark_specialized_gain` results cannot serve
as production-safe promotion receipts.

## Publication and budgets

This limited release requires a source-bound `production_safe_gain` verdict,
complete continuation replay, the actual successful process exit and the
single-skill revision chain. The explicit scope amendment changes which rules
and evaluations are included; it does not lower correctness, control, timing,
mechanism or source-integrity thresholds. Preserve rejected proposals in
`wiki/evolution.jsonl` and preserve all original failure receipts.

Under `time_only_v1`, one frozen finite budget covers generation, independent
review, the single build, correctness, timing, profiling and online admission.
Actual tokens are recorded as cost. The time limit is configurable; a child
cannot renew its parent deadline. A frozen reserve allows an already started
collection unit to finish, while incomplete evidence cannot pass. Post-task
collection is separate. Any future equal-budget comparison must freeze the
same calibrated budget for all arms and seeds before starting it.

The scoped gate and actual exit have succeeded. Seal this directory and verify
its independent installation, registry and links before updating catalog and
host marketplace pointers. Never modify the sealed 0.5.0 or 0.5.1 trees or relabel
historical evidence. The 45-run comparison and full test evaluation remain
unperformed unless separately commissioned; this limited release does not
claim their results.
