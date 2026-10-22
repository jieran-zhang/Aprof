# AProf graph-base 0.5.1

This directory is the complete, canonical skill library. Copy it anywhere to use
it independently. It contains the optimization workflow, core/support skills,
an optional remote adapter, runtime 0.2.2, contracts and immutable v0001/v0002
graphs. This version starts from the preserved 0.5.0 release for a
measurement-method repair. Runtime thresholds and graph snapshots are unchanged.
Earlier Event confirmations remain rejected. A Task-only diagnostic reproduced
150/250 ms Event intervals while kernel Task Duration stayed stable; the extra
time occurred between tasks in that capture. The Task Duration protocol requires
complete independent qualification, bound by the stable `release.json` manifest.
The proposed `shared_buffer_msprof_task_window_v4` uses `local_profile_only`:
optimization keeps task-local profiler files and returns code plus a small report.
Complete correctness, Task CSV parsing, controls and online admission still count
against the task budget. Optional permanent copying, CAS registration and archival
audit belong to the post-task trace/training collector, with separate costs.
Only a verified stable `release.json` establishes V4 qualification and release;
without it, 0.5.1 is unsealed and the default remains 0.5.0. Earlier failed
campaigns retain their original protocols and outcomes.
Without a release manifest, treat this directory as an unsealed candidate. The
installation commands below apply after successful qualification and sealing.

## Install and verify

From this directory, use Python 3.11 or later:

```bash
python3 tools/install.py --runtime
python3 tools/release.py
./tools/aprofctl graph validate --graph skillgraph/versions/v0002
```

The installer creates a version-local `.runtime-env` and installs the declared
Python dependencies. The launcher always selects this directory's runtime, even
if another version is on PATH. Hardware execution additionally needs the target
CANN SDK, compiler, profiling tools and NPU access. Plan-only use does not execute
hardware. Remote execution is optional; add `--with-remote` to install its Python
dependency and explicitly select the adapter when needed.

For a filesystem skill host, expose the core/support skills with
`python3 tools/install.py --skills-dir <host-skills-directory>`. This creates
links to this complete release, so retain the directory. Add `--with-remote`
only to expose the optional adapter. Switching versions requires removing the
previous managed links; the installer refuses to overwrite other skills.

The release root is also the plugin root: `.codex-plugin/plugin.json` and
`.claude-plugin/plugin.json` discover `skills/`. A host must retain the whole
package, including runtime, graphs and tools. After a plugin host copies the
package into its cache, run the runtime installer in that installed copy. Do not
edit a stable manifest or add a cachebuster; a changed package gets a new version.

## Supported workloads and profiling

The current optimization focus is **Vector operators on Ascend 910C (A3)**.
The [workflow input template](skills/ascendc-aprof-workflow/SKILL.md) describes
operator cases, build/correctness/run commands, device, budget and constraints.
Raw kernel input can be scaffolded; execution optimization needs a complete
operator project.

Profiling selects the supported backend: **msprof on 910C/A3**, and preferential
npu-compute on compatible **950/dav-3510** systems. The documented npu-compute
support does not include A3. Its 950 parser/fixture coverage is distinct from
this library's verified operator optimization scope. Keep the system CANN and
driver unchanged; do not install a mismatched tool to satisfy a preference.
See [tool support and provenance](skills/tool-npu-compute/NOTICE.md).

Both backends feed capture manifests and normalized profiles into runtime source
replay. Mechanism profiling remains separate from the declared production timing
protocol. See [collector commands](skills/ascendc-aprof-profiling/references/collector-interface.md).

## Default optimization loop

Use one coordinator, one hypothesis and one candidate. Reuse verified session
preparation and frozen plans; rebind candidate source identity and run full
correctness after every change. Screen representative cases using the shared
context and buffer Task Duration protocol: one baseline Task pilot freezes the
repeat count, followed by six fresh processes with five formal pairs each and
pre/post A/A controls. Failed controls or clear regressions stop the attempt.
These are exploratory observations without reward.

An advancing candidate receives a new full-workload thirty-pair timing run with
independent A/A controls,
then the missing five-capture mechanism evidence and the unchanged formal gate.
PMU is disabled for timing and collected separately for mechanisms. Keep Event
intervals and Host wall as auxiliary metrics. Only runtime acceptance selects a production best. Preserve every failed or
inconclusive attempt, and derive the human summary from one canonical record.
See the [shared timing protocol](skills/ascendc-aprof-profiling/references/shared-timing.md)
and [input preparation helpers](skills/ascendc-aprof-profiling/references/prepared-timing.md).

The helpers need a project-specific generator/oracle and complete-call timing
integration. They do not provide an automatic adapter for every operator.
Record actual session duration; no fixed 20–30 minute completion is claimed.
Retain the local evidence needed for handoff; a small report alone is not verified
training data. Post-task archiving cannot change an online failure or timeout.

## Invoke

Use `ascendc-aprof-workflow` with a complete operator directory, its workload and
correctness contract, execution commands and budget. For example:

```text
Use $ascendc-aprof-workflow.
Prepare a validated optimization plan; do not build or execute hardware.
op_dir: <complete operator project>
budget: {candidate_limit: 1, build_limit: 0, timing_limit: 0, full_profile_limit: 0}
```

The [main skill](skills/ascendc-aprof-workflow/SKILL.md) owns the optimization
procedure. [Stage interfaces](workflows/aprof-performance-workflow.md) describe
handoff. Use `tools/aprofctl` in examples that name `aprofctl`; pass the graph
inside this package explicitly. New stage-aware sessions use v0002.

## Version and evidence boundary

`release.json` seals package bytes and binds independent skill/runtime/graph
versions. Historical 0.4.1/0.4.2 bytes and frozen campaign producers remain unchanged.
After publication, new sessions explicitly select 0.5.1; changing the default catalog does not migrate
an old run. Installation state is excluded from the seal. Online measurement state
belongs in private task-local temporary storage, never in this library. A separate
trace/training collector owns any requested permanent archive. Campaign policy, lesson
curation and training are external callers; they cannot change this release.

Runtime 0.2.2 reads legacy profiles and verifies stored 0.2.0/0.2.1 graph
episodes without rewriting them. New measured admission requires 1.1 profile
provenance and independent measurement-method evidence. Historical exploration
outcomes must be replayed with their original frozen producer; they cannot be
rebound to this release as new measurement proof.

Graph snapshots and their logical provenance paths are preserved byte for byte.
`skillgraph/provenance-paths.json` locates the retained source evidence. v0001
validates as a historical snapshot, but its original compilation digest differs
from the documents at the 0.4.0 source commit. Do not overwrite it to make a
recompilation match. v0002 is a reproducible overlay on the frozen v0001 graph.
