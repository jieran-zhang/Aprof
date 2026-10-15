# 0.5.1 measurement controls: post-hoc statistical audit

Date: 2026-10-14. **Diagnostic design evidence only. No historical rejection is changed, and neither release is admitted.**

## Finding

There are two separate problems. Applying the 5% CV and 2% bias/drift limits to every five-pair cycle adds a substantial rejection burden beyond the inherited 0.5.0 contract. However, an isolated roughly 2x event also violates the inherited CV limit with 30 pairs. Removing the small-cycle check alone does not solve short-event instability. This audit does not support weakening the original gain, correctness, regression, or source/provenance requirements.

The most limited next intervention is the separately preregistered **50 ms baseline-calibrated event window**, with every numerical control retained. It tests acquisition behavior; success is not guaranteed. The four-case method study and the subsequent independent full 40-case qualification remain necessary. See [the continuation plan](measurement-admission-reassessment.md).

## Which requirements were inherited?

The actual 0.5.0 sources require:

- Formal timing has at least **30 paired events** and 10 warmups. The collector checks each case's baseline and candidate CV and the suite projection against **5%**.
- The runtime checks the paired arrays, both CVs, and the original deterministic 2,000-resample bootstrap **one-sided 95% speedup lower bound >= 1.03**.
- Maximum recorded case regression is **3%**; full correctness, semantic/scope/portability and mechanism requirements remain separate gates.

The new shared-buffer protocol additionally checks each of six fresh processes, each phase's five pairs, and the merged 30 pairs. It applies 5% CV, A/A role bias <=2%, and before/after mean drift <=2%; same-source method confirmation also applies A/A role bias to the formal phase. Forty cases entail **7,200 events**, **1,440 local role-CV checks**, **240 pooled role-CV checks**, **840 role-bias checks**, and **560 drift checks**, before the suite CV checks. These are correlated descriptive checks, not independently calibrated 5%-significance tests.

Fail-fast is a separate issue: stopping early censors the remaining planned evidence. If the same requirement that every local check pass remains, merely completing the run instead would not change its final rejection condition.

Sources: [0.5.0 contract](../../skill-libs/graph-base/0.5.0/runtime/src/aprof_runtime/contracts.py) and [gate](../../skill-libs/graph-base/0.5.0/runtime/src/aprof_runtime/gates.py); [0.5.0 collector](../../skill-libs/graph-base/0.5.0/skills/ascendc-aprof-profiling/scripts/device_paired_timing.py); [0.5.1 control replay](../../skill-libs/graph-base/0.5.1/runtime/src/aprof_runtime/measurement_admission.py). Source byte hashes are in the accompanying JSON.

## Data and fixed analysis method

Input is **all 6,000 unprofiled events / 3,000 pairs** from exp case 6, six fresh processes with 500 pairs each. The independent profiling data are excluded from this statistical dataset. Each receipt's messages were checked against its actual hash-bound native stdout. No event was removed, winsorized, replaced, normalized away, or selected because a gate passed.

The analysis contains:

1. Full-corpus and per-process CV and original-runtime paired bootstrap calculation.
2. All **600 disjoint five-pair blocks**, covering every pair exactly once.
3. All **100 corresponding six-process pools**, each taking five pairs from every process, for 30 pairs per pool. This also uses every pair exactly once.
4. Every valid aligned 15-pair window, plus **20,000 empirical window resamples**, fixed NumPy seed **20261014**. Each resample independently takes one contiguous 15-pair window from each original process, then labels its first/middle/last five pairs as before/formal/after. This retains local ordering and allocation-level means. It cannot reconstruct real phase priming or real phase-transition behavior.

The original bootstrap function is called without modification, with a fixed audit candidate ID `offline-control-audit-fixed`. Its hash-derived random seed and 2,000 resamples follow the inherited implementation. This is an arithmetic analysis, not a gate verdict on a candidate.

Machine-readable results, every 30-pair pool, method details and source hashes: [statistical audit JSON](graph-base-0.5.1-statistical-gate-audit.json). Reproducible analysis source: `/mnt/tidalfs-hwwh01/dataset/dots_infra/workspace/jieran/APROF/measurement-gate-statistical-audit-20261014/analyze.py`, itself included in the source-hash inventory. It ran without NPU access or production edits.

## Results

Across all 3,000 pairs, baseline CV is **2.8568%**, candidate CV **1.6329%**, paired geometric speedup **1.0004006**, and the inherited one-sided 95% lower bound **0.9999585**. Thus the full observed population is close to A/A equality; it does not demonstrate a performance gain.

| Exhaustive partition | Joint CV/bias rejection | CV rejection | Bias rejection |
| --- | ---: | ---: | ---: |
| 600 disjoint five-pair blocks | 3 / 600 | 2 / 600 | 3 / 600 |
| 100 six-process, 30-pair pools | 2 / 100 | 2 / 100 | 1 / 100 |

Exactly **one** pool passes pooled controls despite containing a rejected five-pair block. The other two remain rejected by the original 5% CV requirement. None of the 100 pools has a speedup lower bound >=1.03. These partitions are fully reported; no passing subset constitutes confirmation.

### Sensitivity to many checks

The empirical ordered-window calculation gives:

| Rule applied to an empirical pseudo-case | Rejection fraction | Hypothetical probability of >=1 rejection among 40 IID copies |
| --- | ---: | ---: |
| Current local + pooled, three-phase controls | 12.155% | 99.439% |
| Pooled three-phase controls only | 6.235% | 92.386% |
| Original formal 30-pair CV only | 2.115% | 57.475% |

The last column is only the sensitivity formula `1 - (1-p)^40`. **It is neither a measured family-wise error rate nor a confidence bound for the actual 40 heterogeneous cases.** These pseudo-cases reuse one workload and correlated data. Increasing the number of resamples reduces Monte Carlo noise; it supplies no new hardware evidence. The table shows how an all-checks-must-pass policy can amplify occasional rejection even for identical implementations.

Only two of the 6,000 events exceed 1.5x their process median. Treating that rate as IID solely for sensitivity gives a 90.93% chance of at least one such event in 7,200 events. An exact binomial 95% interval maps to an extremely broad **25.2%–99.98%** range. The rarity and process clustering prevent a precise tail-frequency claim, and not every tail definition is itself a gate failure.

### Why one event causes a rejection

For `n-1` observations equal to one and one observation equal to two, sample CV is `sqrt(n)/(n+1)`:

| Paired events in the affected role | Sample CV | Candidate-side geometric role bias | Mean drift when only one phase has the tail |
| --- | ---: | ---: | ---: |
| 5 | 37.27% | 14.87% | 20.00% |
| 30 | 17.67% | 2.34% | 3.33% |

The actual rejected exp cycle had after-control baseline CV **43.08%**, role bias **14.57%**, and baseline drift **23.99%**. The rejected sigmoid cycle had before-control baseline CV **32.10%**, role bias **11.55%**, and baseline drift **14.39%**. Formal-phase CVs in those cycles were below 0.31%. These were real control failures under the preregistered policy, not fabricated gain failures. Only five of six required cycles exist for either terminal case, so this audit cannot reconstruct complete-case or full-suite acceptance.

The 95% performance confidence bound addresses the mean paired log speedup after stability checks. It does not certify that every five-pair subgroup is stable, replace the raw CV checks, or remove rare events. Shared process/cycle dependence also means all repeat calls inside an event must not be counted as additional independent pairs.

## Minimal next protocol: fixed 50 ms target

The selected study fixes **50 ms**, with exactly **three baseline-only pilot events at repeat=100** per case. Let their median event duration be `m` milliseconds:

`R = 100 * max(1, ceil(50 / m))`

The pilot is independent of confirmation. Freeze the resulting `R` once for both roles; reject calibration as unsupported if `R > 100000`. Keep the existing six-process / three-phase / five-pair design, warmup and priming, all controls, and all observations. Do not sweep targets, alter R after seeing candidate/control results, retry until passing, or use pilot samples in the gate.

As an analytic illustration only, a fixed additional **0.56 ms** delay in one of five events gives:

| Ordinary event duration | Five-event role CV | Role bias | Mean drift |
| --- | ---: | ---: | ---: |
| 0.625 ms | 33.98% | 13.65% | 17.92% |
| 50 ms | 0.50% | 0.22% | 0.22% |

This dilution is plausible for a fixed additive delay. It is not evidence that delays remain fixed when R changes; submission pressure, queue behavior, cache residency, thermal state and stalls that scale with launch count may all differ. A successful four-case study is followed by a fresh independent full 40-case confirmation, not promotion of these calculations to hardware evidence.

### Estimand and cost

Longer events measure **sustained, amortized complete-operator duration**: the event interval enclosing R complete direct-enqueue callbacks divided by R. They do not measure isolated-call latency, and they are not automatically identical to the previous 100-call burst estimand. Complete host/device work and scratch reinitialization required by each call must remain inside every callback; replacing callback submission with graph replay or kernel-duration sums would change the measurement further.

For an approximately 0.625 ms pilot event, the formula gives R=8000. One cycle then contains `20 + 3*400 + 30*R + 2 = 241222` kernel calls for a one-kernel operator. At exactly 50 ms per event, 40 cases contain about **360 seconds of timed intervals**, plus fixed priming, process initialization, correctness oracles, profiling and I/O. That is not an end-to-end runtime estimate. Full-protocol timeline captures grow with R and need a preregistered storage/task-count plan.

For later A/B use, a common repeat calibrated only on baseline cannot guarantee a fast candidate's event reaches 50 ms. For example, a 10x faster candidate can have a 5 ms event. Such a candidate must still pass the unchanged controls; silently recalibrating from candidate performance would violate the frozen design.

### Evidence changes required before production use

New confirmation must bind the calibration plan, every pilot sample, baseline source/binary/input identity, target/formula/cap, frozen per-case R, new header/collector/checker producer hashes and independent confirmation identity. Native output and runtime replay must verify the actual R and division by R, pair counts, callback/stream/buffer identity, and derived timeline task counts. Historical repeat=100 receipts and all failed attempts remain immutable and distinguishable. These are acquisition-protocol changes; the inherited correctness, CV, 3% gain-LCB and 3% regression floors remain unchanged.

## Limits

This is a post-hoc analysis of one exp workload, not a prospective statistical validation or a proof of the underlying runtime/firmware cause. It supports a new preregistration only. No new hardware sampling, production edit, threshold relaxation or release publication was performed for this audit.
