---
name: ascendc-aprof-profiling
description: Measure complete kernel tasks and collect Ascend C mechanism evidence with source replay. Use msprof Task Duration for qualified 910C/A3 paired timing, separate PMU captures for mechanisms, and npu-compute on supported 950 systems.
---

# AProf profiling and source replay

For historical A/A drift and metric-scope counterexamples, consult the grouped
[diagnosis experience index](../../experience/diagnosis/README.md) only after
establishing the current collector, workload and measurement protocol. Draft
Wiki observations do not replace this skill's formal capture requirements.

Use this skill to turn diagnostic metric requirements into an executable capture
and an auditable normalized profile. The runtime owns source replay, stability,
mechanism alignment and candidate acceptance.

## Task-local execution and post-task handoff

`shared_buffer_msprof_task_window_v5` uses `local_profile_only`.
Keep required profiler files, execution receipts and source identities in a private
task-local directory. The optimization Agent returns code and a small report with
the actual machine result. The local index serves online tools or a requested
collection handoff; the optimization Agent does not copy profiles to
permanent storage or register their contents in CAS. Complete correctness, full
Task CSV parsing, A/A controls and online admission remain inside the task budget.
A trace/training collector may archive and independently audit the files after
the task; report that cost separately. Keep local failures and partial files for
the requested handoff; otherwise clean up task-created temporary data when the
task ends. Archiving cannot rescue a failed or timed-out optimization.

Use the matching v5 local admission entry; if unavailable, return `not_evaluated`.
The 1.0.1 development package is unsealed. Its installation does not qualify
runtime changes, extend the inherited exp scope, or rebind old v4 evidence.
Do not substitute an old CAS collector or treat a small report as formal evidence.

## Select the backend

Read [metric-to-profiler.md](references/metric-to-profiler.md) after the bundled
environment preflight and `npu-arch` identify the actual device/toolchain.

- **Ascend 950 / dav-3510:** prefer `tool-npu-compute` when the installed version
  and single-operator target are supported. Load its tool-specific references
  only when using or interpreting that backend.
- **910C/A3:** use `msprof`; npu-compute's verified upstream scope does not
  include this architecture. Keep msprof available for compatibility and missing
  views on other supported environments.
- **Unknown/incompatible environment:** produce a plan and explain the exact
  missing capability. Keep the system CANN/driver unchanged.
- **Simulator:** use it for feasibility and trace proxies when requested or
  hardware is unavailable; it cannot establish production hardware gain.

## Capture and normalize

In an optimization session, reuse valid baseline evidence and defer full
mechanism capture until the candidate survives the exploratory screen and fresh
full-workload timing by default. A route-required predicate is a decision-changing
gap: collect the minimum valid diagnostic evidence before the edit, using the
formal capture counts when its provenance contract requires them. An unavailable
extractor or unsupported predicate stays explicit; neither a source hypothesis
nor quick timing can substitute for that evidence. Standalone profiling requests
do not require a candidate.

1. Preserve the complete operator/case contract and source identity. Require
   successful build and complete correctness evidence for this exact source;
   reuse its receipts instead of rerunning those stages for each profiling view. Use
   `scripts/run_profile_stages.py` with JSON argv arrays to record stage order,
   timeouts, exit codes and log hashes. A dry-run is useful for inspection;
   already-authorized execution does not require a second confirmation.
2. Select only missing metrics from [metric-bundles.md](references/metric-bundles.md).
   Use the [collector interface](references/collector-interface.md) to select the
   backend and record independent captures in a new task-local directory.
3. Keep capture identity, kernel/collection, source/binary, workload, hardware,
   backend version, raw artifacts and policy bound together in task-local files;
   do not modify reports or manufacture an `OpBasicInfo.csv` for JSONL.
4. Parse with [report-parsing.md](references/report-parsing.md). The bundled
   normalizer emits a versioned profile whose selected values can be replayed
   from raw CSV/JSONL. Distinguish within-capture Core aggregation from repeated
   captures. Keep missing fields, unsupported values and unavailable identity
   explicit.
5. Submit the local evidence and mechanism report through the compatible
   runtime online-admission path within the same task deadline. A schema-valid object alone proves neither collection
   success nor mechanism alignment. The runtime recomputes source values and
   verifies comparison identity; an Agent-authored boolean is not a substitute.
6. Return to `ascendc-aprof-diagnosis` with measured values, uncertainty,
   alternative mechanisms and the next missing view. Preserve
   `linked_hypotheses` when supplied.

## Measurement boundary

Screen predeclared representative cases using their separate registered screen
plan; screening cannot establish reward. The finalist starts a fresh full-coverage
[shared-buffer protocol](references/shared-timing.md) run before mechanism
capture. That formal protocol uses six fresh processes and five pairs per phase
in each process, including A/A controls. A control failure invalidates the
comparison; preserve it and stop that attempt. Prepared input reuse never
substitutes for full correctness or independent verification of both callbacks.

Formal mechanism evidence requires at least ten recorded warmups and five
independent captures, with CV <= 0.05; record what actually executed. Core rows, Section rows, internal replay and
Pipeline sampling groups are not repeated measurements. Single captures remain
exploratory; missing captures or excess variation limit the conclusion.

The production gain gate separately requires at least thirty alternating AB/BA
timing pairs, CV <= 0.05 and speedup LCB >= 1.03. The accompanying runtime replays
the registered raw A/A controls, complete task table and source identities.
Use `device_task_window_timing.py`: one baseline Task pilot freezes the calls per
sample for each case, followed by six independent processes. Task Duration is
the primary kernel metric. Event intervals and
Host wall are auxiliary; report their scope and regressions separately. An
independent local scratch directory holds profiling work. Full local integrity,
correctness and control checks precede the next cycle; permanent transfer and CAS
registration are post-task work. An
arbitrary profile row does not become a formal sample. `scripts/paired_timing.py` is appropriate only
for timing-only commands that exclude build, generation and verification; its
command wall time must not be reported as kernel execution time.

Collect PMU counters only for regions that test the mechanism. Task timing covers
every declared case, with PMU disabled; full PMU coverage is unnecessary. The A3 mechanism collector
currently uses `--aic-metrics=Default`; selecting fewer normalized metrics does
not reduce that acquisition cost. Do not claim per-Section msprof collection is
implemented. Baseline reuse must pass the runtime's exact source, workload,
hardware/frequency, tool, collector and measurement-policy comparison.

## Installed tools

Resolve paths from this release, even when installed outside the checkout:

- `scripts/profile_capture.py`: architecture routing and repeated collection into
  task-local files; returns the manifest identity and local evidence index. No `--store`.
- `scripts/normalize_profile.py`: complete source replay with `--local-index`;
  returns a normalized profile, its hash and an updated local index.
- `scripts/run_profile_stages.py`: declared preflight/build/correctness/profile stages.
- `scripts/prepare_workload.py`: verified input/oracle preparation reuse.
- `scripts/device_task_window_timing.py`: implemented Task v5 local collector;
  see [shared timing](references/shared-timing.md) for its interface, original
  deadline binding and unchanged measurement requirements.
- `assets/device_task_profile.h`: native Task-only profiling around the complete callback schedule.
- `scripts/device_task_timing.py`: historical fixed-repeat Task v2 evidence; no current formal admission.
- `scripts/device_shared_timing.py`: historical Event measurement and diagnostic support;
  its samples cannot enter new Task admission.
- `scripts/device_paired_timing.py`: legacy two-process diagnostic drafts;
  these cannot supply new Task v5 measured admission.
- `scripts/paired_timing.py`: alternating command-wall-clock pairs when applicable.
- `scripts/compress_msprof.py`: legacy msprof symptom drafts and expert heuristics.
- `ops-profiling/scripts/msprof_profile_run.sh`: auxiliary multi-group msprof
  capture; its `--compare` is not the production paired protocol.

The collection/normalization command examples and their configuration live in
[collector-interface.md](references/collector-interface.md).

## Output and authority

A profiling plan/result, stage report, paired-timing output or symptom JSON is a
**draft**. Include backend/profile mode, exact argv, required artifacts, field
selectors/formulas/units, measurement policy, observed samples, statistics,
missing evidence and source hashes. Keep legacy `msprof_command` only for a
legacy msprof plan; never label an npu-compute command as msprof.

Formal capture manifests, normalized profiles and mechanism reports have their
own machine contracts. Follow [contract mapping](../../references/contracts.md)
for current kinds and formal gate handoff. Keep old 1.0 profiles and historical
campaign evidence read-only; do not silently reinterpret their samples with the
new source protocol or replace frozen campaign producers.

Report unknown when theoretical traffic, available Core count, trace overlap
or instruction granularity is absent. Versioned heuristic thresholds are not
calibrated probabilities. Preserve each symptom's candidate mechanism set until
source/workload evidence and immutable graph routing resolve it.
