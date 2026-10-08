# Level2 lightweight search

New CLI searches use `msprof_task_time_search_lite_v1`; historical v1/v2 plans
and final evaluation keep their original six-process, thirty-pair design.
The [bundled workflow reference](../skills/aprof/ascendc-aprof-workflow/references/search-measurement.md)
defines the measurement and decision policy.

## Running an authored attempt

```bash
python scripts/level2_iteration.py baseline --run /absolute/campaign --operator gather \
  --search-protocol lite --capture-storage local --epoch search-lite-01
python scripts/level2_iteration.py candidate --run /absolute/campaign --operator gather \
  --candidate gather003 --search-protocol lite --capture-storage local --epoch search-lite-01
```

The operator project and proposal must already exist. Registration, build,
twenty-case standalone/prepared correctness, runtime safety, dispatch guards,
parent-only measurement and feedback are handled by the existing executor.
No per-parent full A/A is required. Baseline self-check uses only the four
search sentinels and does not certify later source-specific effects.

`--search-protocol auto` is the default: new plans use lite; an already frozen
search retains its exact protocol, epoch, capture mode and calibration bindings
unless explicitly overridden. Conflicting overrides fail. Python callers keep
the legacy default and opt in with `measurement={"search_lite": True, ...}`.

The small runner builds once into `tools/timing-search-lite`; it does not replace
`tools/timing`. New observations bind the actual producer and binary hashes.
Do not execute old ad-hoc owners that pin a prior producer while silently using
the new code. Frozen finals still use the full protocol and their own compatible
calibration, independently of search feedback.

Before final evaluation, explicitly prepare a full control with
`baseline --search-protocol full --calibration-group aa-initial` (and the
appropriate frozen epoch/storage options), or provide an existing compatible
full calibration. A lite self-check cannot satisfy final calibration. The
candidate command does not automatically create the initial baseline self-check;
run the baseline command first and repeat that check after an environment change
or observed drift. Low-level cohort CLI paths must be absolute.

Each lite case reports two process ratios and a descriptive range; `ci95` is
null. Feedback includes conservative parent-choice guidance, per-case
regressions, and `automatic_remeasure=false`. Failed native execution remains an
infrastructure/source outcome; it is not converted into an uncertain success.

## Evidence and runtime costs

The executor fully verifies each completed observation once and caches that
result in memory for report generation, with mutation checks. Independent
report replay, portable archive verification and tamper checks still execute
the full verification path. A JSON report on disk is not a trusted cache.
New completed timing stages bind report and completion hashes into the ledger;
feedback checks those hashes before selecting a parent. An older completion
without these bindings requires a full replay before creating new feedback.

Formal samples per comparison are 1/15 of the historical design. Warmup,
correctness, build, output verification and profiler startup remain costs, so
this is not a claim of a 15x wall-clock speedup. New searches compare only the
direct parent; original-baseline comparisons are deferred to frozen final
evaluation. No inferred product of ratios is reported as an actual comparison.

The design was chosen from retrospective prefixes of 35 historical Level2
comparisons across nine operators (402 case/configuration cells). Two processes
and six pairs differed from full point estimates by a median 0.082%, p95 0.934%,
and maximum 3.053%. None of 178 cells with an observed full effect above 5%
reversed direction. This is descriptive retrospective support, not independent
protocol qualification: warmup, repeats, longer-run history and profiler mode
were inherited from the original observations.

An independent two-process run on 2026-10-08 compared the existing Gather001 and
Gather002 binaries on six declared cases. Collection, output verification and
report generation completed in 74.314 seconds. The normal/swapped suite ratios
were 1.614508/1.614848, versus 1.615233/1.615656 in the historical full run;
the largest case/configuration point-estimate difference was 0.205%. These
observations were made at different times and do not establish an all-operator
error bound or a wall-clock speedup. The 74 seconds exclude build, full-case
correctness and two failed isolated-environment preparation observations, which
are preserved alongside the successful result. No new source attempt or formal
admission was recorded. Evidence is indexed under the central trace directory's
`method-validation/search-lite-method-20261008/`.
