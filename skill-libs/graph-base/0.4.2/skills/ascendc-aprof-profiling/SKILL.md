---
name: ascendc-aprof-profiling
description: Select a supported profiler, collect repeated Ascend C mechanism evidence, and normalize original reports for AProf runtime replay. Use for missing diagnosis metrics or candidate mechanism comparison; prefer npu-compute on supported 950 systems and msprof on 910C/A3. Keep correctness and paired production timing separate.
---

# AProf profiling and source replay

Use this skill to turn diagnostic metric requirements into an executable capture
and an auditable normalized profile. The runtime owns source replay, stability,
mechanism alignment and candidate acceptance.

## Select the backend

Read [metric-to-profiler.md](references/metric-to-profiler.md) after the bundled
environment preflight and `npu-arch` identify the actual device/toolchain.

- **Ascend 950 / dav-3510:** prefer `tool-npu-compute` when the installed version
  and single-operator target are supported. Load its tool-specific references
  only when using or interpreting that backend.
- **910C/A3:** use `msprof op`; npu-compute's verified upstream scope does not
  include this architecture. Keep msprof available for compatibility and missing
  views on other supported environments.
- **Unknown/incompatible environment:** produce a plan and explain the exact
  missing capability. Keep the system CANN/driver unchanged.
- **Simulator:** use it for feasibility and trace proxies when requested or
  hardware is unavailable; it cannot establish production hardware gain.

## Capture and normalize

1. Preserve the complete operator/case contract and source identity. Run the
   declared build and complete correctness commands before profiling. Use
   `scripts/run_profile_stages.py` with JSON argv arrays to record stage order,
   timeouts, exit codes and log hashes. A dry-run is useful for inspection;
   already-authorized execution does not require a second confirmation.
2. Select only missing metrics from [metric-bundles.md](references/metric-bundles.md).
   Use the [collector interface](references/collector-interface.md) to select the
   backend and record independent captures in a new task-local directory.
3. Keep capture identity, kernel/collection, source/binary, workload, hardware,
   backend version, raw artifacts and policy bound together. Preserve files in
   the CAS; do not modify reports or manufacture an `OpBasicInfo.csv` for JSONL.
4. Parse with [report-parsing.md](references/report-parsing.md). The bundled
   normalizer emits a versioned profile whose selected values can be replayed
   from raw CSV/JSONL. Distinguish within-capture Core aggregation from repeated
   captures. Keep missing fields, unsupported values and unavailable identity
   explicit.
5. Submit the normalized evidence and mechanism report through the runtime's
   CAS-aware gate path. A schema-valid object alone proves neither collection
   success nor mechanism alignment. The runtime recomputes source values and
   verifies comparison identity; an Agent-authored boolean is not a substitute.
6. Return to `ascendc-aprof-diagnosis` with measured values, uncertainty,
   alternative mechanisms and the next missing view. Preserve
   `linked_hypotheses` when supplied.

## Measurement boundary

Formal mechanism evidence requires at least ten recorded warmups and five
independent captures, with CV <= 0.05; record what actually executed. Core rows, Section rows, internal replay and
Pipeline sampling groups are not repeated measurements. Single captures remain
exploratory; missing captures or excess variation limit the conclusion.

The production gain gate separately requires at least thirty alternating AB/BA
timing pairs, CV <= 0.05 and speedup LCB >= 1.03. Use the caller's declared timing
protocol and full workload coverage. A profile duration does not automatically
become a production timing sample. `scripts/paired_timing.py` is appropriate only
for timing-only commands that exclude build, generation and verification; its
command wall time must not be reported as kernel execution time.

## Installed tools

Resolve paths from this release, even when installed outside the checkout:

- `scripts/profile_capture.py`: architecture routing and repeated collection.
- `scripts/normalize_profile.py`: capture-manifest and raw-source normalization.
- `scripts/run_profile_stages.py`: declared preflight/build/correctness/profile stages.
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
