# Prepared-input device timing

This page describes the existing executable harness. The future
[shared-context paired protocol](../../../collection/workflows/shared_context_paired_protocol.md)
requires a new native runner and process-level analysis; it is not implemented
by these commands. In particular, `--single-live-context` starts a fresh native
process for each role sample, while the default below uses two persistent
children. Neither is A/B sharing one native process and context. See the
[experiment playbook](../../../collection/workflows/optimization_experiment_playbook.md) for
current experiment organization; historical outputs retain their original rules.

`python3 scaffolding/collection/scripts/cannbench_device_timing.py instrument --source ORIGINAL --dest ISOLATED`
copies one supported operator into an absent, noncanonical destination. Build the
copy with its normal CMake command. The original host, kernels and baseline
correctness scripts remain untouched. Candidates must copy the instrumented
baseline so the common harness is identical. `harness_manifest.json` hashes the
original host, transformed host, injected header, patch, template and producer.

The seven supported operators are foreach_norm, exp, masked_scale,
foreach_addcdiv_scalar, mish, sigmoid and gelu. With no APROF environment variables,
the original single-invocation correctness path runs. For TensorLists, the timing
branch prepares each tensor or original chunk in aligned device buffers before
measurement. Each timed invocation executes the complete list, including every
partial/finalize launch for foreach_norm. Inputs, tiling and allocations stay
outside the event interval. Results from the final invocation are copied back
and checked against the original oracle.

```bash
python3 scaffolding/collection/scripts/cannbench_device_timing.py prepare --opdir ISOLATED --case 1 \
  --device 0 --input-root INPUTS --execute
python3 scaffolding/collection/scripts/cannbench_device_timing.py measure --baseline BASE --candidate CAND \
  --cases 1,8,14,20 --device 0 --input-root INPUTS --output UNIQUE_OUTPUT
```

`prepare` without `--execute` is a command dry run. Its Python API
`prepared_commands(opdir, case_id, device, input_root=None)` returns preparation,
execution and verification argv, cwd and metadata path. Execution argv is null
until metadata exists. `command_from_metadata()` can override the output path to
keep correctness/profile/timing results isolated.

`measure` defaults to 10 warmups, 100 complete invocations per ACL-event sample,
and 30 paired AB/BA rounds. Two persistent children prepare the same input once;
the coordinator requests only one child's sample at a time. Thus preparation and
process startup do not enter device timing. Each event interval includes all
launches and any device-visible gaps caused by host submission. It is a complete
operator latency measurement, not a sum of kernel busy durations.

Verified on this host: `ASCEND_RT_VISIBLE_DEVICES=15` plus `--device 0`
places the process on physical chip 15 (NPU 7, chip 1), as confirmed with
`npu-smi` while the prepared child was live. Preserve the physical mapping in
campaign provenance; timing JSON reports the logical CLI device.

Device jobs use `/tmp/aprof-device-locks/device-N.lock` for the entire paired run.
When an external executor already holds the physical-device lock, specify
`--external-lock`. In that mode the caller is responsible for correct physical
device mapping, exclusive access, and process cleanup. Baseline and candidate
always receive the same device argument; each raw record retains host and device.
Each output directory must be unique. Shared prepared inputs must be fully
generated before parallel jobs start; outputs and verification metadata remain
inside each job's unique directory. OMP/MKL/OpenBLAS threads default to two in
measurement children.

The executable protocol uses `APROF_TIMING_INTERACTIVE=1`, prints
`APROF_TIMING_READY`, accepts `sample` and `quit` on stdin, and emits a JSON line
prefixed `APROF_TIMING_JSON:` for every sample. `APROF_TIMING=1` instead executes
`APROF_SAMPLES` samples (default one) without stdin. Set `APROF_WARMUP=10` and
`APROF_REPEAT=5` for standalone msprof profiling. The JSON sample declares source
`acl_event`, unit `ns`, device, sample index and launches per complete operator.

`raw_measurements.json` retains paired samples, execution commands, input/binary
hashes, logs and interrupted-collection status. `measurement_report.json` is
produced only after collection and prepared-path correctness succeed.
`summarize_multicase(raw, expected_cases, min_pairs=30, max_cv=.05, seed=0)` computes
an equal-case geometric mean **within each round**. It never concatenates latency
samples from different shapes. Per-case arrays are always retained, while the
`gate_projection` timing arrays are empty if any case is missing, mismatched,
invalid, noisy or incomplete. Baseline/candidate CV must be at most 5% for every
case and the suite. The report contains paired bootstrap 95% speedup lower bound
(2000 deterministic resamples), maximum paired geometric-mean case regression, and eligibility
for speedup LCB at least 1.03 with regression at most 3%. The runtime remains the
authority for final verdicts and mechanism attribution. Bind the report's CAS
hash and exact `gate_projection` fields into runtime evidence.

For a multi-device suite, concatenate per-case raw records in the frozen case
order, retaining each record's host/device identity, set `complete` only after
all jobs and correctness checks succeed, and call the adapter with the complete
expected case list. A single case's A/B pair must always share its host/device.
