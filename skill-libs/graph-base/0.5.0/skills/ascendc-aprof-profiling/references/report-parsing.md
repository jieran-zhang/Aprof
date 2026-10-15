# Raw report parsing and evidence handoff

For new sessions, collect through [collector-interface.md](collector-interface.md)
and normalize selected metrics into the 1.1 source protocol. Both msprof and
npu-compute preserve their actual raw format and backend identity. Legacy
`compress_msprof.py` remains available for symptom drafts and old reports; its
output is not a substitute for formal source replay.

## Identity before values

Keep one workload, source role, device and selected kernel/collection explicit
in each capture manifest. Match npu-compute kernel identity against that
collection's `OpInfoSummary`; match msprof against its recorded OpBasicInfo and
kernel-directory evidence. Do not synthesize a CSV representation of JSONL and
claim that derivative as the original source.

The runtime checks the bound raw files, selectors, independent capture roster,
aggregation and comparison identity. Preserve exact filenames, raw hashes,
field names, units, excluded NA cells and missing evidence. Schema validation
checks the document shape; source replay checks the evidence it references.

## Backend-specific views

| Backend | Raw views | Interpretation |
| --- | --- | --- |
| npu-compute | Section CSV, summary.jsonl, HardwareInfo.jsonl, PipeTrace.json | Read [npu evidence semantics](../../tool-npu-compute/references/evidence.md); task summary and Core rows have different aggregation scopes. |
| msprof op | OpBasicInfo, PipeUtilization, Memory, ArithmeticUtilization, ResourceConflictRatio, L2Cache, MemoryUB, MemoryL0 CSVs | Read actual fields and kernel/Core identity; filenames may carry timestamps. |
| auxiliary msprof | PROF_GROUP/PROF CSV and optional human summaries | Summaries help navigation; selected raw CSV values remain the source. |
| simulator | trace.json, instruction/code execution CSV | Feasibility and trace proxies; no production hardware gain evidence. |

For transfer-size or traffic-amplification hypotheses, record the workload's
byte lower bound, Core/task aggregation and formula. For hardware utilization,
record the observed architecture denominator. No denominator means unknown,
not a made-up utilization percentage.

## Samples and comparison

First aggregate selected rows within each capture using the declared reducer;
then form the repeated `samples` in capture order and apply the outer reducer.
The count of Core rows, Section records or internal replays is not the repeat
count. Preserve per-Core rows for imbalance diagnosis even when one aggregate
is used for a mechanism comparison.

A JSONL Section summary mean and a CSV Core median are different metrics.
Compare the same backend, selector meaning, units, aggregation, workload and
compatible hardware/measurement policy. Baseline/candidate profile duration
must not be copied into paired production timing arrays.

The normalizer reports missing/unstable metrics. The runtime, not the agent,
determines whether enough valid independent evidence exists for mechanism
alignment. One capture is exploratory. Extra Core rows cannot make it stable.
If the actual capture policy does not satisfy a final evidence requirement,
record `measurement_limited` and retain the raw observation.

## Symptom drafts

For an old msprof report, use:

```bash
python3 scripts/compress_msprof.py --input <report-root> \
  --op-name <exact-kernel-name> --output <symptoms.json>
```

Supply `--available-cores` or `--theoretical-gm-bytes` only when supported by the
workload/hardware evidence. Preserve extractor version, threshold profile,
unknown predicates and candidate-mechanism ambiguity sets. Do not feed
npu-compute reports to this legacy compressor: same-named CSVs do not supply the
OpBasicInfo identity or identical field semantics it expects.

For a simulator Chrome trace, the bundled `ops-simulator` bubble analyzer can
provide structured proxy observations. For npu-compute Pipeline, use its
bundled inspector and sampled-group rules. Neither path authorizes interpreting
summed overlapping busy intervals as whole-kernel duration.

## Draft outputs

`profiling_results.json` may summarize artifact inventory, unavailable views,
metrics, samples/statistics and links to hypotheses. Mark source-only,
single-capture, proxy and unstable conclusions explicitly. Its status is a
human/agent handoff, not a machine contract or accepted verdict. Formal evidence
uses [the runtime contracts](../../../references/contracts.md) and raw-source
hashes, with separate correctness and timing artifacts for candidate admission.
