# Shared context and buffer Task Duration timing

V5 uses `local_profile_only`; qualification requires a verified stable release manifest.
This protocol requires independent hardware qualification. A published release
manifest binds that qualification; without it, this is a candidate. It adds no validated
optimization rule and does not establish a cache or memory-controller mechanism.

## Integration contract

Use `assets/device_shared_timing.h` and `assets/device_task_profile.h` with two named callbacks in one native
process. Both receive the same ACL stream and `SharedBuffers`: identical input,
output and workspace pointers and lengths. Each callback performs one complete
operator invocation, including every constituent kernel and required dependency.
Source review must bind each callback name to its original implementation and
the combined binary. The collector does not translate arbitrary host code.

Inputs are immutable, outputs must be fully written each call, and scratch
initialization belongs inside the complete callback. In-place or stateful
operators and incompatible buffer layouts require separate qualification.
Checking final input bytes cannot detect an input modified and then restored;
the read-only input contract also requires source review. Role-specific immutable
tiling parameters may differ; all parameters belong in the source/build evidence.

The primary metric is `msprof.op_summary.Task_Duration`. Each sample sums the
registered tasks for exactly the frozen R complete calls and divides by R, in ns/call.
Task Duration includes device scheduling, execution and completion response;
it is not pure Vector/Cube instruction time. Preserve every task, including slow
ones. Never select only the longest task or count individual tasks as independent
paired samples.

Record ACL Event elapsed time, first-to-last task span, inter-task gaps and Host
wall time separately. Event time includes task gaps and submission starvation;
neither it nor Host wall is silently substituted for Task Duration. Report a
kernel gain as a kernel gain, with any auxiliary regressions. Do not substitute
graph replay or per-launch synchronization.

The initial qualification scope is complete single-kernel Vector calls on 910C/A3,
CANN 9.0.0. Serial multi-kernel use must register the full ordered task sequence
and qualify its complete-call scope. Overlapping tasks, mixed-task duplication,
unknown task types and missing tasks are rejected. Task sums are not latency
for a parallel workflow; such workloads require a qualified span measurement.

## One calibration, then fixed collection

The proposed protocol is `shared_buffer_msprof_task_window_v5`. Freeze source, workload,
ordered task sequence and the calibration rule before starting. Each case gets
one separate baseline-only pilot: 20 warmups, four prime blocks of 100 calls,
then three 100-call samples. From the median complete Task total M in ns, select
`R = max(100, 100 * ceil(10_000_000 / M))` exactly once. Reject R above 100000.
The fixed 10 ms value predicts the complete Task sum per sample. It is separate
from acceptance thresholds. The earlier 50 ms v1 attempt exceeded the trial
budget and remains rejected. The 10 ms v2 attempt also exceeded the complete
collection-and-replay budget. V3 moved profiles into complete CAS persistence.
V4 keeps the same timing rules and moves permanent copying/CAS/archive audit to
a separate post-task trace/training stage. It still budgets complete local
correctness, Task parsing, controls and online admission. Earlier pilot values
and controls cannot qualify v4; new qualification must bind the v4 implementation.
V5 retains the same calibration and controls. It binds `launches_per_operator`
and `role_kernel_names` as complete role → case-ID maps, including single-kernel
cases. Every map must cover exactly `expected_case_ids`; ordered sequences retain
repeated kernel names and must match the actual full callback launch counts.
The collector and replay select the same case binding. Prior v4 receipts remain
valid only under their original sealed version and do not qualify v5.
The target is not configurable and must not be adjusted in response to failed
controls.
The pilot and both original output checks remain in evidence but never enter
formal samples. Record each case's calibration in task-local evidence, then
freeze the complete calibration table before any confirmation process. Never use candidate timings
to select R, or change R after seeing a control failure.

For each declared case, create six fresh processes and allocations with that
case's frozen R. In each:

1. Warm up both implementations ten times before READY.
2. Collect `aa_before`, `formal`, then `aa_after`, in that order.
3. Before each phase, prime four blocks of 100 calls in ABBA order for even
   cycles and BAAB for odd cycles. These are not samples.
4. Collect five alternating AB/BA pairs per phase. Reverse the starting role in
   odd cycles. A/A maps both roles to the baseline callback; formal maps each
   role to its own implementation.
5. After all timing, invoke each implementation once, save its output separately,
   verify input bytes unchanged, exit, then run both original output oracles.
   These output checks are explicitly untimed callback verification, not a claim
   that every intermediate timed output was checked.

One trusted Python oracle process serves the whole collection, using the frozen
original scripts with fresh script globals and each actual output. It reuses
library imports, never golden results or prior verdicts. Requests are serial,
after native exit and before the next native process; a failure or timeout ends
the attempt without restarting the worker. Its complete lifetime and each
request belong in the evidence and task budget.

Each process uses the native `ACL_PROF_TASK_TIME` facility with
`ACL_AICORE_NONE`. Construct TaskProfile after ACL initialization, start it before
RunShared, and finish it before device/context teardown. The controller requires
an explicit fresh `APROF_TASK_PROFILE_DIR` and a successful native exit, including
profiler flush. The native command file specifies the complete five-command
pilot or 19-command confirmation schedule. Export exactly once using the bound
SDK Python entry `msprof.py export summary -dir <PROF> --format csv`, retaining
all raw data, complete summary CSVs and databases. There is no task-name, model,
iteration or duration filter, and no largest-task shortcut. The collector does not write a growing sample
record between pairs. Preserve the complete profiler output and child logs;
parse and verify outputs after process exit. Exactly one complete task table is
required. Only a predeclared export of an otherwise successful capture is allowed,
never a replacement capture. Incomplete evidence cannot be admitted or resumed
as a completed attempt. PMU mechanism evidence is collected separately.

Capture and export into a fresh, preregistered local `scratch_root`, with storage
mode `local_profile_only`. Keep the complete raw profile, summary CSVs, databases,
logs, source identities and execution receipts in the task-local directory.
Bind complete file inventories and verify source bytes around export. Export may
append only the existing `collection_host.log` and `collection_device_<id>.log`;
retain the necessary local prefix snapshots. Every other captured file must
remain byte-identical. Parse the original complete Task CSV from local files.

Before advancing, finish the required output oracles, source/integrity checks and
cycle/pooled controls. Before returning an admitted result, replay complete local
evidence within the remaining task deadline. Do not omit CSV rows, sample points,
failed controls or correctness checks to meet that deadline. Failed or incomplete
attempts expose no gate samples. There is no remote fallback or replacement capture.

The optimization Agent returns code and a small report with the machine result,
actual elapsed cost and local evidence index. It performs no permanent profile
copy, full-profile CAS registration, archive audit or archive-driven reclamation.
Keep successful, failed and partial local evidence until handoff or an explicit
retention decision; provision local capacity accordingly. After the task, an
optional trace/training collector owns archival copies, complete CAS import,
independent archival replay and episode finalization. Record its cost separately.
An archive cannot retroactively complete or change an online failure or timeout.

Within one collection, frozen source/input/SDK digests may be reused only after
two complete, identical hashes separated by at least one second on the local
monotonic clock. Every use still checks the complete source roster, regular-file
status and device/inode/mode/size/mtime/ctime identity. Earlier uses read all
bytes; elapsed time alone never qualifies a cached digest. This safeguard is
limited to the qualified Linux overlay/JuiceFS environment. It does not establish
integrity under arbitrary concurrent edits or on other filesystems. Local profile
validation retains complete content checks; online admission
replays the complete required local evidence. Post-task archival verification is
an additional, separately costed operation.

The v4 collector interface is being adapted to
`collect_local(config, local_output, *, timeout_seconds=3600)` and CLI
`--config [--output] [--timeout-seconds]`, without `--store`. Omitting `--output`
creates a private temporary work directory. This implemented interface still
requires hardware qualification before release.
Work and profile directories must be private task-local storage. Use only the
matching local runtime admission entry; old CAS-based CLI examples do not
implement this workflow. If that entry is unavailable, keep admission unevaluated.

The config declares `schema_version`, `operator`, `run_id`, `session_id`,
`candidate_id`, logical `device`, mapped `physical_device`, `expected_case_ids`,
`roles`, `build`, `cases` and `task_profile`:

- Each role declares its original `source_dir`, host callback `symbol`, and
  `launches_per_operator`.
- `build` declares the combined `source_dir`, executable `binary` and immutable
  `receipt_files` for its compilation and adapter/source review.
- Each case declares `case_id`, complete `workload`, immutable `prepared_files`,
  direct executable `command`, and role-specific `verify_commands` and
  `output_files`. All commands are argv arrays, without a shell.
- `task_profile` declares the absolute `profiler` executable, a fresh absolute
  local `scratch_root`, and
  `role_kernel_names`, the exact ordered kernel-name sequence for each complete
  callback. Its length must match `launches_per_operator`; both roles are bound
  before collection. The native profiling header, SDK/Python dependencies, fixed export command, actual scratch filesystem
  and complete local file inventories are recorded. The collector exclusively
  creates the scratch root; do not pre-create or share it with another trial.
- The only path placeholder is `{cycle_dir}`. Outputs must be fresh, disjoint
  role paths beneath it. The child reads `APROF_SHARED_CYCLE`,
  `APROF_SHARED_MODE` and `APROF_SHARED_REPEAT`, and calls
  `RunShared`; callbacks and output serialization remain part of reviewed host
  integration. Metadata and oracle inputs are frozen files outside that path.

Configuration and evidence JSON use strict JSON numbers. If input metadata describes
NaN or infinity, preserve the original input/metadata bytes and encode only the
copied descriptive value as, for example, `{"__aprof_nonfinite_float__":"NaN"}`
(also `"Infinity"` or `"-Infinity"`). This does not relax numeric timing checks.

## Admission

A single-kernel pilot has exactly 722 tasks; each confirmation process has
exactly `1222 + 30*R`. Each process supplies 30 macro samples (15 pairs), giving
30 formal pairs over six separately created process and buffer lifetimes. Individual tasks inside a
sample are not extra independent observations. The v4 online entry must reject
old Event, fixed-R Task and earlier Task-window receipts; their explicit historical replay remains
available. A valid measurement proof alone does not authorize a skill release.

The local completion result must bind its report and underlying measurement proof;
a small report alone is not admission. The compatible runtime replays source, binary,
producer, input, oracle, stdout and execution identities and every sample.
It reconstructs all task groups from the original CSV and native stdout, checks
that registration precedes collection, and replays the single oracle worker's
ordered requests and original results. At R=100, a single-kernel cycle contains
4222 tasks: 20 warmups, 1200 prime calls, 3000 measured calls and two final output snapshots.
Summary `passed` or `stable` values alone are insufficient.

For every case, both the aggregate and each fresh cycle must satisfy A/A role
bias `abs(gmean(B/A)-1) <= 0.02`, sample CV `<= 0.05`, and per-role before/after
mean drift `<= 0.02`. Failed or incomplete controls expose no gate samples.
The thirty new formal pairs use the existing equal-case geometric aggregation.
A/A qualification has no required speedup. An actual candidate must additionally
pass the unchanged correctness, per-case regression, gain and mechanism gates.

Representative-case screening remains exploratory; full-workload acceptance
requires a separate registered collection. Keep failures and diagnostic samples
in their original records. V5 admission requires
`shared_buffer_msprof_task_window_v5` and independent qualification bound by the
stable release manifest. Without that manifest the package remains a candidate.
The native header still emits its original `shared_buffer_acl_event_v2` wire
payload for identity and auxiliary Event data; that name is not a Task sample
label. Older Event collections and two-process helpers retain their historical
meaning and cannot supply new Task admission.
