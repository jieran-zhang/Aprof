# Research search and final measurement

Use a small measurement to select the next intervention. Reserve the full
measurement design for frozen evaluation. Preserve the user's explicit protocol
when one is specified; do not relabel existing observations.

For the repository's Level2 campaign, new searches default to
`msprof_task_time_search_lite_v1`: two independent native processes, six
alternating AB/BA pairs per case and normal/swapped output/workspace addresses.
The processes reverse module-loading, first-pair and configuration order.
Warmup remains ten complete calls. Repeat remains the original baseline's
frozen per-case 1 or 10, identical for control and candidate.

- Keep all twenty cases and all named outputs in correctness validation. Keep
  dispatch boundary guards and initialization/reset/multi-kernel call semantics.
- Measure the four declared search cases and up to two predeclared probes.
  Choose probes from the changed workload group or boundary, never dispatch
  from benchmark case IDs.
- Compare against the actual selected source parent. Measure against the
  original baseline after the candidate roster and complete dispatch freeze.
  Do not multiply historical ratios and label the product as a measurement.
- Run one small baseline measurement-system self-check. Do not repeat full
  twenty-case A/A for every new parent. A self-check is not source-specific
  calibration of later candidates; label their search evidence uncalibrated.
  Changes to device, SDK, measurement mode or observed drift justify a new check.
- Treat changes within about three percent as uncertain. Default to retaining
  the validated parent, then continue the next planned source intervention.
  Changes above five percent must agree across processes and address layouts
  before guiding parent choice. Keep regressions on individual keys visible.
  A noisy or conflicting result does not justify an unbounded measurement loop.
  Any supplemental observation must be explicit, budgeted and separate; the
  runner does not automatically retry. A new source or source repair still
  consumes a source attempt.
- Two-process ranges are descriptive, not 95% confidence intervals. Preserve
  `formal_admission=not_evaluated`, `graph_policy_eligible=false`, and no episode.
- Final evaluation keeps the full six-process, thirty-pair protocol, full-case
  coverage, and appropriately bound A/A. Both parent and original-baseline
  comparisons remain available there. Formal runtime admission is separate.

Use one maintained campaign executor. Do not write a new wrapper or request a
new review package for each ordinary iteration. Validate a captured session
once and reuse the verified in-memory result for its group report. Separate
archive replay still verifies all bound evidence; a saved JSON receipt alone is
not authority to skip hashes. Schedule storage compaction at capacity thresholds
outside device timing, preserving original failures and raw evidence.

For elapsed-time planning, count correctness, compilation, profiler startup,
capture, validation and storage costs as well as formal calls. Reducing sample
counts does not imply a proportional reduction in wall-clock duration.

In a source checkout, `scripts/level2_iteration.py` is the common entry point.
Its CLI uses lite for new searches and preserves an existing frozen protocol
with `--search-protocol auto`. `--search-protocol full` explicitly selects the
historical design. The Python API keeps legacy defaults for existing callers.
The lite runner is built separately under `tools/timing-search-lite`; historical
runner binaries, source snapshots and observations remain immutable.
