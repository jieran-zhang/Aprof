# Measurement admission reassessment and release continuation

Status: active research and implementation. Neither 0.5.1 nor 1.0.0 is sealed.

The current objective is to repair and independently qualify the acquisition
method, publish stable 0.5.1, then migrate and qualify 1.0.0 and complete its
frozen comparison and publication. The preceding work produced executable
changes and new hardware evidence; it was progress, not successful publication.
Historical failed attempts remain failed.

## What rejected 0.5.1

The shared process/context/buffer method passed the original target-case bias
checks. Independent production confirmation then stopped at exp case 6 cycle 4
and sigmoid case 7 cycle 4, because isolated long events violated the control
rules. Correctness passed on the cases actually executed. Unexecuted cases and
profiles remain unexecuted; partial coverage cannot qualify the full release.

The inherited 0.5.0 performance contract requires at least 30 paired samples,
candidate CV at most 5%, a speedup lower confidence bound of at least 1.03,
and per-case regression at most 3%. The measurement repair additionally applied
CV, role-bias and drift rejection separately to every five-pair resource cycle.
Those small-cycle checks are stricter than the inherited performance contract.
Their statistical justification must be assessed separately from correctness,
source identity and complete-operator coverage, which remain mandatory.

The [independent statistical audit](graph-base-0.5.1-statistical-gate-audit.md)
reports all 600 disjoint five-pair blocks and 100 six-process pools from the
6000-event dataset, with no passing-subset selection. Three small blocks and two
30-pair pools fail. Its simulations quantify sensitivity under stated sampling
assumptions; they do not estimate the actual 40 heterogeneous cases' error rate.

A single 2x observation among otherwise equal observations gives sample CV
about 37.3% at n=5 and 17.7% at n=30. Removing the five-pair rejection alone
therefore does not fix the original 30-pair contract. The event window of the
short failing exp case was only about 0.6 ms; a roughly 0.5--0.7 ms dispatch
delay dominates such a window.

The independent unprofiled diagnostic retained all 6000 events. Two large tails
occurred without corresponding main-thread enqueue/RecordEvent delays, context
switches or faults. Separate profiling substantially increased submission CPU
time and event duration, so its task gaps do not establish the cause of those
unprofiled tails. Exact firmware/runtime causality remains unknown.

## Next bounded method study

Study a longer event window without deleting observations or changing any
numerical acceptance threshold:

- Fix the target duration at 50 ms before new hardware sampling.
- For each case, collect exactly three baseline-only pilot events at repeat=100.
- Let `m` be their median event duration in milliseconds. Freeze
  `repeat = 100 * max(1, ceil(50 / m))` once for both roles of that case.
- If the required repeat exceeds 100000, reject calibration as unsupported;
  do not silently cap it or choose a different target after seeing results.
- Pilot observations never enter confirmation statistics. Confirmation starts
  fresh processes with the frozen repeat and uses all its observations.
- Keep one context/stream/shared buffer set per process, the complete callback,
  direct enqueue, end-event synchronization, and division by actual repeat.
- Keep six fresh resource lifetimes, three phases of five pairs, original
  warmup/priming, original oracle, and the current overall/per-cycle controls.
- Fix the case order to exp [6, 9], sigmoid [7, 4]. Stop the affected operator
  at its first required failure and record later cases as not run; independently
  judge the other operator. No target sweep or resampling until passing.

This studies sustained complete-operator mean duration, not isolated invocation
latency. Longer batches may change queue and thermal behavior; event duration
is not kernel-duration sum. Stalls that scale with launch count may remain.
The four-case study is not the full 40-case production qualification and cannot
seal 0.5.1. A successful study supports a protocol implementation followed by a
new, independently registered full qualification and installation audit.

Before prospective production changes, the complete unsealed repeat=100
candidate and all 14 repository producers bound by the latest failed production
plan/freeze were copied and checked against their original hashes. The immutable
archive index is at
`/mnt/tidalfs-hwwh01/dataset/dots_infra/workspace/jieran/APROF/measurement-method-v1-source-archive-20261014/index.json`
with SHA256 `048db70c6b6bbca6d5cd176d8033defc4c5df46c95817593c93b15fc3b7d4254`.
This preserves historical replay source bytes; it does not turn the old candidate
into a sealed release or change any failed verdict.

## Remaining path to 1.0.0

After sealing 0.5.1, migrate its runtime and measurement admission through the
Teacher verifier, validation adapter/controller, evidence replay and publication
verifier. Preserve the v0002 topology, split, correctness rules and performance
floors. The current 1.0.0 verifier still requires the entire 0.5.0 runtime;
changing that obsolete base-version restriction is necessary for this migration.

Restricted worker tools, blind review, graph routing and the 45-run evaluator
are implemented, but code and mock probes do not replace real hardware and model
receipts. Finish the five baseline qualifications and the train-controller
positive path; independently promote at least one eligible rule. Freeze the
candidate, run all 45 equal-budget validation trials, and replay the primary
comparison before stable publication. Validation outcomes must not tune skills;
test remains a single evaluation after sealing. No objective is complete until
both requested releases have passed their applicable gates.
