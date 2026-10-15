# Adding AProf msprof Simulator Benchmarks

This guide describes how to add benchmark cases to the AProf benchmark tree and
make them runnable through the manifest runner.

Current benchmark locations:

- `benchmarks/aprof_injected_ops/` — injected vector-kernel cases
- `benchmarks/reference_ops/` — reference AscendC workloads
- `benchmarks/cannbench/manifest.yaml` — CANNBench adapter manifest skeleton

The legacy path `benchmarks/msprof_simulator_real/` is not yet populated in this
repository; use the layouts above for new cases.

## Benchmark Contract

Each runnable case has this layout:

```text
benchmarks/msprof_simulator_real/cases/<case_id>/
  workload/        # AscendC source tree
  raw/             # real msprof op simulator output
  diagnose/        # AProf report generated from raw/
```

The raw artifact contract is:

- `raw/aprof_metadata.json`
- `raw/OPPROF_*/simulator/trace.json`
- `raw/OPPROF_*/simulator/**/*_code_exe.csv`

The diagnose artifact contract is:

- `diagnose/summary.json`
- `diagnose/summary.md`
- `diagnose/time_windows.csv`
- `diagnose/harness.json`
- `diagnose/problems.json`

## Manifest Fields

Add a case object with these required fields:

- `id`: stable snake-case case id. This becomes the case directory name.
- `enabled`: set to `true` for the default suite.
- `capture_status`: use `pending_workload`, `attempted_missing_driver_runtime`,
  `captured_fallback`, or `captured_real_msprof`.
- `operator_name`, `kernel_version`, `shape`, `data_type`, `soc_version`: copied
  into `aprof_metadata.json` and reports.
- `source_root`, `executable`, `profile_output`, `diagnose_output`: paths
  relative to the repository root.
- `workload_source`: describes how `--prepare-sources` materializes the workload.
- `expected_diagnosis`: used by `--verify` once trace and hotspot artifacts exist.

## Workload Source Modes

Use `official_gitee_sparse_checkout` for a source tree pulled directly from
Huawei Ascend samples:

```json
{
  "kind": "official_gitee_sparse_checkout",
  "repo": "https://gitee.com/ascend/samples.git",
  "ref": "master",
  "subdir": "operator/ascendc/0_introduction/21_vectoradd_kernellaunch/VectorAddSingleCore"
}
```

Use `derived_from_official_sample` for local variants based on another case:

```json
{
  "kind": "derived_from_official_sample",
  "base_case": "official_vector_add_baseline",
  "notes": "Describe the intended bottleneck or code change."
}
```

Derived cases inherit the base build command. During `--prepare-sources`, the
runner copies the base source tree, preserves the case README as `APROF_CASE.md`,
and adjusts the workload tensor length from the manifest `shape`.

## Running The Suite

Materialize, build, run, and verify all enabled cases:

```bash
python3 scripts/collect_msprof_benchmarks.py --prepare-sources --build --run --verify
```

Run one case:

```bash
python3 scripts/collect_msprof_benchmarks.py \
  --case <case_id> \
  --prepare-sources \
  --build \
  --run \
  --verify
```

Offline verification without rerunning msprof:

```bash
python3 scripts/collect_msprof_benchmarks.py --verify --allow-incomplete
```

## Real Evidence vs Fallback Evidence

The default runner requires real `msprof op simulator` output. On machines where
CANN toolkit is present but driver/runtime libraries such as
`libascend_hal.so` or `libdcmi.so` are unavailable, `msprof` may start and still
fail before producing timeline artifacts. Default `--run --verify` should fail
in that state.

For CI or method-loop testing only, pass `--allow-fallback-capture`. The runner
then writes a clearly marked fallback capture under:

```text
raw/OPPROF_FALLBACK_<case_id>/
raw/fallback_capture.json
```

Fallback captures are msprof-compatible fixtures for exercising AProf's closed
loop, reports, and expected diagnosis checks. They are not real profiling
evidence, and default verification ignores them. Only set `capture_status` to
`captured_real_msprof` after the raw directory contains a real `trace.json` and
at least one real `*_code_exe.csv` from `msprof op simulator`.

## Checklist For A New Case

1. Add the manifest entry and a short `workload/README.md` describing the
   intended bottleneck.
2. Choose `official_gitee_sparse_checkout` or `derived_from_official_sample`.
3. Set `expected_diagnosis.bottleneck_class`,
   `responsible_components_any`, and `recommendation_prefix_any`.
4. Run `python3 scripts/collect_msprof_benchmarks.py --case <case_id> --prepare-sources --build --run --verify`.
5. Inspect `diagnose/summary.md`, `diagnose/problems.md`, and
   `benchmarks/msprof_simulator_real/collection_summary.json`.
6. If you intentionally used `--allow-fallback-capture`, keep `capture_status`
   as `captured_fallback` or `attempted_missing_driver_runtime`; do not claim it
   as real msprof evidence.
