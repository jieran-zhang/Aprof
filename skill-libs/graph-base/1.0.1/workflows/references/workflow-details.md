# AProf Wrapper Responsibilities

Read this file only when coordinating stage handoff. Do not duplicate graph
contracts, schema fields, measurement thresholds, or gate rules here.

## Reuse within one session

The coordinator owns one canonical candidate record with references to existing
plans, source/patch, execution receipts and required task-local artifacts. Derive summaries from
it; do not ask each wrapper to restate the complete analysis. This record is
orchestration bookkeeping, not an additional runtime contract or reward source.

| Reuse | Recheck or invalidate when |
| --- | --- |
| Prepared input and oracle files | Workload, generator/oracle dependency bytes, preparation argv/environment or output integrity changes. Preparation reuse never caches candidate correctness. |
| Baseline build and correctness | Baseline source, binary, toolchain or declared correctness/input contract changes. Every changed candidate still receives full correctness. |
| Architecture and parallel plan | Hardware/toolchain capabilities, semantic contract, algorithm, decomposition, ownership, reduction or workspace ownership changes. |
| Dispatch rules and workload groups | Metadata domain, key/group/entry or fallback changes. Rebind the implementation source hash for every candidate even when rules are unchanged. |
| Baseline mechanism profile | Source, workload, device/frequency basis, backend/tool, collector, policy or selector meaning differs. Runtime comparison remains authoritative. A candidate-role capture cannot simply be relabeled as baseline. |

Immutable receipts and raw artifacts are reused by reference, never rewritten.
The profiler still checks the live device and source/binary/tool identity around
execution. Reusing a session preflight does not bypass those checks.

## Exploration and acceptance

The main skill defines the screening and formal measurement policies. A screen
uses representative cases to decide where to spend the remaining budget;
formal timing uses a new run with the full declared case set. Keep both sets of
raw samples and their policy/parent identities separate. A screen may stop an
attempt without full profiling, but it cannot supply a formal gain, a formal
stable-no-gain verdict or policy-training reward.

Record the screening extension's sample count and stopping rule before the
initial run. At most one extension is allowed. Do not select a favorable prefix
or invent a stronger minimum gain than the frozen acceptance gate. If timing
does not justify proceeding, retain the observation and stop with admission not
evaluated; do not synthesize mechanism evidence to obtain a terminal verdict.

Correctness and full-workload regression coverage remain candidate-specific.
Mechanism profiling covers the hypothesis-relevant regions; it need not repeat
all cases solely because correctness has a larger matrix. Reuse valid baseline
evidence, then collect the finalist's missing source-bound evidence. A standalone
diagnosis request may collect profiles without creating a candidate.

## Stage ownership

| Stage | Agent responsibility | Machine authority |
| --- | --- | --- |
| Input/scaffold | Resolve a complete `op_dir`; preserve a read-only baseline | Registry and context schema validation |
| Architecture / parallel plan | Recover algorithm and legal decompositions against observed resources; produce profile/parallel/dispatch artifacts | Strict schemas, content hashes, capability/capacity masks |
| Dispatch | Wire metadata keys into actual host/kernel entries, preserve fallback | Unique keys, matching conditions and bound group/plan identities |
| Evidence | Propose source/workload/profile observations and missing views | Predicate IDs, graph version, strict contract validation |
| Profile collection | Propose/execute authorized commands; retain raw artifacts | Raw CSV/JSONL source replay, collection/kernel identity, parser version, paired statistics and evidence quality |
| Route | Supply validated context and budget | Legal candidate set, masks, policy probabilities, selected edge, behavior propensity |
| Candidate | Apply one selected transformation contract in isolation | Contract/version compatibility and candidate-draft schema |
| Validation | Supply build/correctness/runtime/profile artifacts | State path, verdict, utility, and `selected_as_best` |
| Post-task trace/training | Optionally archive local files, verify provenance and import eligible episodes; record archival cost separately | Full archive integrity, independent gate replay, episode hash and append-only store |

## Wrapper rules

All wrappers are optional delegation adapters. The coordinator may invoke the
underlying skill directly and keeps the authoritative session record.

- Diagnosis wrapper normalizes context and evidence; it does not force one
  anchor or choose a transformation.
- Profiling wrapper selects the supported backend and constructs collection/parse
  artifacts; runtime replay establishes evidence validity. On 910C/A3 it uses
  msprof, while compatible 950 systems prefer npu-compute.
- Parallel-planning wrapper constructs algorithm/task and dispatch drafts; it does not invent platform resources or performance gains.
- Optimization wrapper preserves the frozen parallel plan and selected workload group, and constructs execution candidate drafts; it does not run an
  independent acceptance implementation.
- Reviewer audits traceability and suspicious artifacts; it cannot replace a
  machine verdict.

## Failure handoff

| Failure class | Suggested capability |
| --- | --- |
| static/API/capacity | `ascendc-code-review` or precise docs lookup |
| accuracy/semantic | `ascendc-precision-debug` |
| runtime nonzero | `ascendc-runtime-debug` |
| timeout/crash/AIC | `ascendc-crash-debug` |
| artifact/measurement | `ops-profiling` |
| stable no-gain/regression | finalize a negative episode only from a compatible gate that ran; exploratory stops remain unadmitted records |

Handoff does not erase or rewrite the original candidate episode.

## Runtime state

Under Task v5 `local_profile_only`, keep complete required measurement data
and receipts in private task-local storage. Optimization ends with code and a
small report referencing the local evidence index, after budgeted online admission.
The optimization Agent does not make permanent profile copies or CAS imports.

The post-task trace/training collector owns optional archival copies, CAS imports,
offline integrity replay and episode finalization. It must preserve the original
online outcome, failures and timeouts, and report its cost separately. Unarchived
reports are not verified training episodes. Once online checks and final
code/report delivery are complete, clean only task-owned scratch. If collection
was requested, wait for the collector to receive the complete local evidence
and index before cleanup. Preserve user-owned sources, final deliverables,
installed package roots and live symlink targets. An installed skill may point
outside the task directory; resolve its source before any cleanup. Do not write
traces into `skills/` or `skillgraph/source/`. Development installation of 1.0.1
checks structure only and does not qualify runtime changes or switch defaults.

Legacy `optimization_memory.jsonl` and historical demo summaries remain
`legacy_unverified`; they are not policy-training inputs.


## Task workspace and budget commands

Use the selected package's `tools/aprofctl` throughout. Create one owned
workspace before generating task data:

```bash
tools/aprofctl task workspace-create --task-id <task-id> --parent /tmp
```

The JSON result contains `root`, `scratch` and `final`. Put transient profiles,
receipts and indexes in `scratch`; put the delivered code and small report in
`final`. Add `--collect` at creation only when a post-task trace/training handoff
was requested. An installed package is not task scratch.

Validate a proposed budget plan without starting a task:

```bash
tools/aprofctl task budget-check --plan <budget-plan.json>
```

That checks structure only. To replay the actual parent launch and original
shared deadline, use all three identity arguments instead:

```bash
tools/aprofctl task budget-check --local-index <local-index.json> \
  --launch-ref <sha256:launch> --task-id <task-id>
```

The trusted controller owns launch/terminal evidence and enforcement of the
original deadline. A plan, child timeout or model-authored `passed` value
cannot renew the budget or prove successful execution.

To supervise one already frozen job with the original remaining allowance:

```bash
tools/aprofctl task run --local-index <local-index.json> \
  --budget-ref <sha256:budget-plan> --job-ref <sha256:job> \
  --destination <new-task-scratch-job-directory>
```

This is a process supervisor, not a full optimization or stage scheduler. The
indexed job defines its argv, cwd, environment and output directory. Use the
returned local index, launch, execution and terminal references. A failed or
timed-out child gives the CLI exit code 2, while the execution receipt retains
the child's actual exit status and elapsed cost.

The trusted controller must call `local_archive.freeze_package_identity(local)`
and put the returned reference in the frozen job's `package_identity_ref`.
Execution and post-task collection verify the complete package identity bound
to that job. Selecting a new default does not change an existing task's identity.

If the child produces stage evidence, the frozen job must also declare
`evidence_indices: ["/absolute/child/local-index.json"]`. Give the child collector
an explicit `--output` directory so those index paths are known before launch.
The parent merges references without copying raw data. A missing declared index
makes the task fail while preserving the actual child exit code; partial evidence
from a failed collection is retained. A plain job with no child evidence may omit
`evidence_indices`.

For an explicitly authorized continuation, repeat `--prior-terminal-ref
<sha256:terminal>` for the complete ordered prior chain. The controller charges
all prior execution cost, including failures; it does not reset the budget.
Use a fresh destination and frozen continuation job. Stage recovery is a
trusted Python callback API: reused stages require independent source, binary,
input, timing and receipt replay. There is no self-declared reuse verdict or
permission to resample a failed control.

After final delivery and actual terminal verification, request owned cleanup:

```bash
tools/aprofctl task cleanup --workspace <root> \
  --local-index <root/scratch/local-index.json> --terminal-ref <sha256:terminal>
```

When the workspace was created with `--collect`, also supply
`--collector-receipt <receipt-outside-scratch.json>`. The separate collector must
finish and the receipt must survive cleanup. This command verifies workspace
ownership and the actual terminal chain, then removes only that workspace's
`scratch`; it preserves `final` and paths outside scratch. Missing terminal or
required handoff evidence rejects cleanup. Do not replace this check with a
recursive deletion of the whole workspace or an installed package.
