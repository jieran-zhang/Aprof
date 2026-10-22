# Collector and normalizer commands

Run these commands from the installed `ascendc-aprof-profiling` skill directory,
or resolve their absolute paths from the selected release. Use the Python
interpreter with that release's runtime dependencies.

## Declared route and capture

```bash
python3 scripts/profile_capture.py select --backend auto --architecture Ascend910C
python3 scripts/profile_capture.py capture --config <capture.json> \
  --output <new-capture-directory> --store <task-episodes.sqlite>
```

`select` is a read-only decision from the declared architecture; it reports
`hardware_verified=false`. `capture` also probes actual board identity with
`npu-smi`, checks the tool, and binds the resulting evidence. A3 routes to
msprof; 950/dav-3510 routes to npu-compute. Explicit npu-compute on A3 fails
before launching the target. Keep the system CANN and driver unchanged.

Example configuration (replace every path and case field with the actual
operator contract):

```json
{
  "backend": "auto",
  "architecture": "Ascend910C",
  "device": 0,
  "case_id": 1,
  "kernel": "exp_kernel",
  "role": "baseline",
  "source_dir": "/absolute/operator-project",
  "binary": "/absolute/operator-project/build/exp",
  "workload": {"shape": [1024, 1024], "dtype": "float16", "base": -1, "scale": 1, "shift": 0},
  "command": ["/absolute/operator-project/build/exp", "--numel", "1048576", "--dtype", "float16", "--input", "/absolute/input.bin", "--output", "/absolute/output.bin", "--base", "-1", "--scale", "1", "--shift", "0", "--device", "0"],
  "cwd": "/absolute/operator-project",
  "warmups": 10,
  "repeats": 5,
  "timeout_seconds": 120
}
```

The command must directly invoke the declared binary. Build, input generation
and full correctness are preceding stages; they do not belong in `command`.
Keep large generated inputs outside the clean source snapshot. Optional `soc`
must reflect the observed chip. If a visibility mapping is used, record
`physical_device` and `chip` for the board probe as well as logical `device`.
`tool_path` can select an existing compatible executable without installing it.

For npu-compute only, supply `sections` (for example
`["PipeUtilization", "Memory"]`) or `set` (`basic` / `full`). The JSON interface
expands the Set first, then adds Sections with first-occurrence deduplication;
use the native CLI when a different option order is specifically required.
Set/Section options are rejected for msprof.

The collector executes the declared warmup target commands separately, then
runs each capture in its own process and output directory. Its msprof command
uses `--warm-up=0 --launch-count=1` after those recorded host warmups. These
capture/host-warmup counts must not be described as same-context iterations or
profiler replay warmups. Native replay remains separate from independent
captures. If multiple result collections exist, use explicit `collection`
selection after inspecting the preserved output; do not merge them.

Outputs include execution logs/receipts, raw files,
`capture-manifest.json`, its CAS hash, and the adjacent SQLite/CAS store. Keep the
store's `.objects` directory with the database. Existing output directories are
refused; failed captures retain their logs. Success does not imply gain.

## Normalize selected raw metrics

```bash
python3 scripts/normalize_profile.py --manifest <capture-manifest.json> \
  --metrics <metrics.json> --store <task-episodes.sqlite> \
  --output <new-normalized-profile.json>
```

`--manifest` also accepts an already registered `sha256:...` object. Use the same
store as capture. A selector is expanded once for every independent capture;
its filename must exactly match a file in the selected collection. A timestamped
msprof filename cannot be replaced with a guessed canonical name.

Example npu-compute `metrics.json`:

```json
{
  "task_duration_us": {
    "unit": "us",
    "file": "summary.jsonl",
    "format": "jsonl",
    "field": "Task Duration(us)",
    "where": {"category": "OpInfoSummary"},
    "row_aggregation": "mean",
    "aggregation": "median"
  },
  "vector_ratio": {
    "unit": "ratio",
    "file": "PipeUtilization.csv",
    "format": "csv",
    "field": "aiv_vec_ratio",
    "where": {},
    "row_aggregation": "median",
    "aggregation": "median"
  }
}
```

For msprof, use the selected raw CSV filename/field and `format="csv"`.
Exact runtime selectors with `sources` can select different recorded filenames
per capture; obtain that shape from the bundled normalized-profile schema and
`normalize_profile.py --help`, rather than inventing new selector fields.

Formal available metrics require at least ten recorded warmups, five independent
captures and CV <= 0.05; lower-count collection is exploratory. The normalizer
calls runtime source replay. It writes a 1.1 normalized profile,
registers it in CAS, and reports per-metric statuses. For npu-compute CSV rows
with `sub_block_id`, the runtime applies a fixed core rule: `aiv_*` metrics use
all `vector*` rows, and `aic_*` metrics use all `cube*` rows. Other fields keep
all matching rows. NA/null in any applicable row makes that capture unavailable
for the metric; the runtime does not silently drop it. CSV `where` supports only
exact `Op Name` / `OP Name` identity; JSONL `where` supports only `category`.
Selecting a favorable subset of Core rows is not allowed. Unknown/unavailable values remain
limited evidence. This command is not a candidate gate; create a
mechanism report referencing the baseline and candidate profiles and follow
[formal handoff](../../../references/contracts.md).
