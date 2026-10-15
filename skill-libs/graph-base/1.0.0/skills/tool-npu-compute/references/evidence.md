# Evidence semantics for operator diagnosis

Read only the views needed for the current hypothesis. Preserve observed
differences, formulas, missing fields and alternative explanations; the tool's
output alone does not identify a unique bottleneck.

| Question | Primary view | Interpretation boundary |
| --- | --- | --- |
| Scalar, Vector or transfer activity | `PipeUtilization.csv` | Active ratios can overlap; they are not exclusive percentages of one timeline. |
| Transfer size and GM traffic | `Memory.csv` | Compare workload-derived required bytes with the matching Core/task aggregation; do not multiply a summary by guessed core counts. |
| Vector arithmetic | `ArithmeticUtilization.csv` | Instruction/active ratios are not a complete roofline without operation counts and hardware denominators. |
| Wait and resource conflict | `ResourceConflictRatio.csv` | Wait is not automatically a bank conflict; use each field's actual definition. |
| UB/L0 access | `MemoryUB.csv`, `MemoryL0.csv` | Respect AIV/AIC applicability and missing counters. |
| Cache behavior | `L2Cache.csv` | Preserve read/write and local/far distinctions when those fields exist. |
| Pipeline overlap and gaps | `PipeTrace.json` | Sampled complete intervals only; see below. |
| Kernel identity and task duration | `summary.jsonl` / `OpInfoSummary` | One result's identity, block count and task duration, not Core-row timing samples. |
| Device and frequencies | `HardwareInfo.jsonl` | Bind actual chip/arch and frequency observations; do not infer 910C from DAV_2201 alone. |

## Units, missing values and grouping

- CSV rows identify `block_id` and `sub_block_id` (`cubeN` or `vectorN`). Compare
  matching keys/Core semantics, not row numbers. Do not merge separate results,
  workloads, kernels or repeats just because their filenames match.
- A field containing `ratio` is an unscaled ratio. A field containing `(%)` is
  a percentage. Never divide a ratio by 100 merely because it exceeds 1.
- `NA` in CSV and `null` in JSONL mean unavailable or inapplicable, not zero.
  Record excluded cells and distinguish wrong Core, missing counts, invalid
  denominator/frequency and known unsupported output. Zero is a real value when
  the counters and denominator exist.
- Upstream currently leaves `aiv_mte3_active_bw(GB/s)`,
  `aiv_ub_to_gm_bw(GB/s)`, `UB_to_GM_datas(KB)`,
  `UB_to_GM_bw_usage_rate(%)` and `aiv_ub_read_bw_gm(GB/s)` unavailable.
  This does not prove that the kernel performed no writes.
- `PipeUtilization` alone can lack counters for active bandwidth; collect
  `Memory` alongside it when those bandwidth fields are needed.
- Data quantities use binary KB (`bytes / 1024`) and the documented bandwidth
  fields use binary GB (`bytes * 1e6 / 1024^3 / duration_us`). Keep that convention
  when comparing workload bounds.
- `aic_time(us)` / `aiv_time(us)` are row cycles divided by the relevant MHz
  frequency. They are not the kernel's `Task Duration(us)`. Mixed-kernel memory
  calculations may use a task-log duration; preserve backend/version semantics.
- A tool-reported theoretical maximum is part of that tool/configuration's
  evidence. The upstream 950 sample's 1600 GB/s value is not a verified 910C/A3
  peak and must not become this library's architecture constant.

## Summary and repeated evidence

Each Section in `summary.jsonl` averages its valid task-level values, with a
potentially different valid count per field. It cannot reconstruct individual
Block rows. The final `OpInfoSummary` identifies the kernel, device, block count,
frequencies and task duration; unavailable fields remain null.

Keep Section summary mean and per-Core CSV aggregation as different metrics.
Reduce the selected Core rows within one capture, then form repeated samples
from independent captures. Thousands of Core rows or replays do not satisfy five
independent captures. Runtime checks the selected sources, units, aggregation
and stability before mechanism alignment. Neither these samples nor task-log
duration automatically satisfy the separate 30-pair production timing gate.

## Pipeline sampling limits

`PipeTrace.json` uses complete (`ph="X"`) busy intervals. `ts` and `dur` are
**microseconds**, even when `displayTimeUnit` is `ns`. Events can overlap across
tracks, so summed busy time is not kernel elapsed time.

Tracks carry group/Core and sometimes process/result/device/replay prefixes.
Different replay prefixes do not establish one continuous global timeline.
The sampled group IDs are 0 through 5: at most **six sampled groups**, each with
observed `cubecore`, `veccore0` or `veccore1` tracks. These counts do not describe
all active cores, blockDim or total core coverage; `pid` does not expose Block ID.
Only intervals with both endpoints are emitted. Empty or missing tracks do not
prove idle hardware, unsupported pipelines or the absence of a bottleneck.

Use the bundled inspector for structure and the observed track roster; infer
overlap only within compatible source/track/time domains. Correlate with source,
workload and PMU evidence before assigning a mechanism.
