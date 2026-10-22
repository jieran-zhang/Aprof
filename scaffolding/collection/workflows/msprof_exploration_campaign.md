# msprof exploration campaign adapter

This adapter implements `optimization_experiment_playbook.md` without changing the original AProf workflow, runtime gates, event-only replay, or the raw `msprof_kernel_time_study_v1` producer. Its campaign protocol is `msprof_task_time_exploration_v1`.

## Interfaces

- `msprof_exploration_campaign.py`: checkpoint-derived, hash-chained split ledger; source identity, multiple observations, launch-time charging, final-evaluation reservations and frozen rosters.
- `msprof_exploration_report.py`: pure plan validation, observation verification and process-level cohort analysis. Missing complete case/config blocks are invalid evidence. A/A precision limits are feedback, not collection failures.
- `msprof_exploration_execute.py` and `run_msprof_exploration_stage.py`: explicitly selected serial stages and external public-work recording; no automatic queue advancement.
- `msprof_exploration_archive.py`: split-specific v2 publication and pure read-only verification; each real parent/baseline comparison has its own evaluation. Full source archive and native source hashes retain their distinct domains.
- `msprof_exploration_safety.py` and `release_aprof_devices.py`: topology-derived health evidence and identity-checked release of explicitly authorized sglang process trees.

Stages are selected explicitly, for example:

```bash
python scaffolding/collection/scripts/run_msprof_exploration_stage.py --run /absolute/run --operator exp --candidate baseline --kind build --group build
python scaffolding/collection/scripts/run_msprof_exploration_stage.py --run /absolute/run --operator exp --candidate baseline --kind correctness --group correctness
python scaffolding/collection/scripts/run_msprof_exploration_stage.py --run /absolute/run --operator exp --candidate baseline --kind runtime --group runtime
python scaffolding/collection/scripts/run_msprof_exploration_stage.py --run /absolute/run --operator exp --candidate baseline --kind control --group aa-initial
```

Candidate timing requires an immutable plan from `prepare_timing`; final timing additionally requires the ledger's frozen roster. Each stage commits its charge before executing and retains failure evidence. A failed stage is not silently retried. Tool builds and baseline/calibration controls are recorded as fixed campaign costs, separately from inherited candidate budgets.

The primary metric is the sum of task durations for complete operator calls, divided by repeat. It excludes gaps between tasks. Native profiling explicitly uses task-time L1 with AI-core profiling disabled. Mechanism profiles use separate executions and accounting.

Native lifecycle observations are recorded separately from formal admission. New research records have `formal_admission=not_evaluated`, `graph_policy_eligible=false` and `episode_ref=null`; they do not synthesize a legacy episode or runtime gate verdict.
