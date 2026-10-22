# Level1 hardware trace campaign

This page records the September 7 campaign and its frozen execution rules,
including the original concurrency experiments. For new experiment organization
and measurement design, use the [experiment playbook](optimization_experiment_playbook.md)
and [shared-context protocol](shared_context_paired_protocol.md). The commands
below operate on historical protocol implementations; they do not implement the
new native-process A/B runner. Historical manifests and verdicts remain unchanged.

The local collection implementation extends the existing SkillGraph runtime with
typed process events, per-candidate summaries, device-event measurements and a
separate exploration gate. The JSONL contract is described in
[trace_jsonl_contract.md](trace_jsonl_contract.md); the isolated-worker knowledge
entry point is described in [level1_knowledge_manifest.md](level1_knowledge_manifest.md).

The frozen graph still has ten executable optimization classes with one positive
transformation each. Handler choice, parameters and failure recovery are not
graph decision nodes. All 18 predicate extractors remain unimplemented; measured
values, heuristic diagnoses and manual source reviews must therefore retain
separate provenance. Six diagnosis references, six optimization references,
four operator playbooks and 18 packaged skills remain available. Restoring
dependencies and resolving generated links does not broaden graph coverage.

## Frozen experiment

The current campaign is `.aprof/runs/level1-20260907T152600Z`. Its
`run-manifest.json` fixes six train operators (`foreach_norm`, `exp`,
`masked_scale`, `foreach_addcdiv_scalar`, `mish`, `sigmoid`) and the independent
validation operator `gelu`. `swi_glu` is outside the allowed task set.
`scaffolding/collection/configs/level1-dependencies.lock.json` pins the two GitCode dependencies.

The original `benchmarks/cannbench/operators` sources remain unchanged. Each
task has a copied, instrumented baseline and independent candidate source trees.
The source validator rejects oracle, verifier and timing-header modifications
inside an optimization patch. CAS source manifests include file contents and
modes. A frozen candidate roster prevents subsequent source registration/builds
and must exist before full 20-case timing.

The baseline task shapes, dtypes, attributes and local precision contract were
compared to the upstream descriptions. The selected local oracle/verifier is not
claimed to be interchangeable with the complete upstream evaluator. A qualified
CPU reference is separately recorded for `foreach_norm`; the initial reference
failure is retained. Correctness is re-executed for every candidate on all 20
cases. `exp-006` also has an explicit nine-case special-value qualification.

Per task, the budget is at most six candidates, six candidate builds, six timing
groups and three distinct fully profiled candidates. Search exposes only cases
`1,8,14,20`. All candidates derive from the same original baseline. Complete
candidate sources and parameters are frozen before final 20-case timing, and final
feedback cannot authorize more candidates.

## Measurements and admission

`cannbench_device_timing.py` and `benchmarks/cannbench/harness` prepare inputs,
initialize ACL, allocate memory and copy H2D outside the event interval. Two
persistent children provide 30 alternating AB/BA pairs with warmup 10 and
repeat 100. An ACL event interval contains the complete operator, including
TensorList launches and the partial/finalize launches of `foreach_norm`.
It also contains device-visible host submission gaps; it is not a sum of pure
kernel busy times. Independent msprof captures use warmup 10/repeat 5.

The adapter preserves per-case raw samples and computes an equal-case geometric
mean within each round. Every case must have CV at most 5%; the speedup 95% lower
confidence bound must reach 1.03 and the worst case regression must be at most 3%.
Missing, nonfinite, wrong-unit or unstable measurements have no admitted gate
arrays. Their raw evidence remains available.

`calibrate_level1_concurrency.py` records the requested 32/16/8/4/2/1 A/A
concurrency probes. `calibrate_level1_affinity.py` is a separately declared
recovery for an evidenced unpinned failure: both children inherit the same fixed
CPU affinity, each tested width gets fresh idle controls, and same-binary role
bias must additionally stay within 2%. The pooled median and each role's median
shift must independently stay within 2%. All original calibration files remain available. The selected physical
devices and CPU affinity are enforced by `Campaign.measure_case`.

Jobs execute through `run_aprof_job.py` under a host-local physical-device lock.
Logical device 0 is mapped with `ASCEND_RT_VISIBLE_DEVICES`; recorded argv and
host/physical-device identities identify the actual execution. Remote Python is
explicitly `/usr/local/python3.11.15/bin/python3`. Output directories and job
specifications are immutable. An execution failure stops new work for that
candidate while preserving already-running jobs, skipped phases, logs and
partial aggregates. Measurement instability alone does not discard evidence.

## Workflow commands

These commands operate on the already prepared campaign; inspect each script's
`--help` before reusing the workflow for another run. Operator workers receive
only their task manifest and their own baseline evidence. The worker launcher
uses a fresh ephemeral process and captures actual knowledge reads and tool
events. It does not run device commands itself.

```bash
python3 scaffolding/collection/scripts/run_isolated_level1_worker.py --help
python3 scaffolding/collection/scripts/collect_level1_traces.py --help
python3 scaffolding/collection/scripts/import_level1_worker_evidence.py foreach_norm
python3 scaffolding/collection/scripts/bind_level1_mechanisms.py prepare --operator foreach_norm
python3 scaffolding/collection/scripts/run_level1_hardware_queue.py foreach_norm
python3 scaffolding/collection/scripts/bind_level1_mechanisms.py bind --operator foreach_norm
python3 scaffolding/collection/scripts/finalize_level1_campaign.py --run .aprof/runs/level1-20260907T152600Z --operator foreach_norm
```

The hardware queue runs correctness, sentinel timing, profile selection, roster
freeze, the selected profiles and final 20-case timing. Mechanism predictions must be
committed before candidate profiling. Binding replays original CSV cells and
reports missing, refuted or noisy predictions explicitly. A latency improvement
alone does not prove its proposed mechanism.

If both complete calibration ladders reject admission, the guarded fallback
continues correctness and counters on two fixed diagnostic devices. It declares
up to three profiler candidates without timing feedback, freezes every source,
and records per-attempt calibration evidence. It collects no candidate timing
and cannot claim a gain. Empty adapters, explicit timing `not_run` reasons and
the final report's `measurement_status=blocked` preserve this distinction.

```bash
python3 scaffolding/collection/scripts/run_level1_blocked_diagnostics.py run --operator foreach_norm --run .aprof/runs/level1-20260907T152600Z
```

## Local outputs and limitations

Each split owns `episodes.sqlite`, CAS, `trace_events.jsonl`,
`optimization_traces.jsonl` and `episodes.jsonl`. Each task contains its knowledge
manifest/read log, baseline/candidate snapshots, source patches, execution logs,
raw msprof tables, normalized counters, raw paired samples, frozen roster,
exploration requests/outcomes and finalization report. The campaign exports also
provide a combined report and a separately selected `best_source` per task.

Exploration has no fabricated graph edge, route or propensity, and never writes
a v1 episode. Consequently an exploration-only campaign has an empty verified
`episodes.jsonl`; this is an explicit graph-coverage finding. The policy-training
path still reads verified SQLite episodes. This campaign does not train or
modify the graph, policy or core knowledge semantics.

Interrupted collector/transport executions and reference/environment
qualifications remain evidence. The FD-ownership repair in EpisodeStore has a
separate event-stream recovery audit with original stream bytes retained.
Final summaries distinguish these infrastructure issues from kernel failures.

The `foreach_norm` diagnostic controller initially failed on a nullable event
reason before launching any candidate profiler job. The narrowly scoped
`recover_level1_profile_preflight.py` verifies the exact failure signature,
absence of profiler jobs and outputs, frozen source/plan/correctness hashes, and
the original trace boundary. It archives the old queue and records a CAS-bound
recovery attestation before resuming those same candidates. It cannot reopen a
failed kernel, correctness check, or actual profiler execution. A reconstructed
old controller source is labeled as reconstruction, not a contemporaneous hash.

After all task closures, export and verify the complete local delivery:

```bash
python3 scaffolding/collection/scripts/finalize_level1_campaign.py --run .aprof/runs/level1-20260907T152600Z
python3 scaffolding/collection/scripts/verify_level1_campaign.py --run .aprof/runs/level1-20260907T152600Z --output .aprof/runs/level1-20260907T152600Z/localverification_report.json
python3 scaffolding/collection/scripts/summarize_level1_lessons.py --run .aprof/runs/level1-20260907T152600Z
python3 -m pytest -q
python3 scaffolding/tools/sync_aprof_registry.py check
git diff --check
```

Raw observations, supported lessons and qualified winners are separate concepts.
An operator can close with a measured non-gain or an evidenced blocker. Neither
JSONL row count nor the number of successful proposals substitutes for the
correctness, measurement and evidence checks.
