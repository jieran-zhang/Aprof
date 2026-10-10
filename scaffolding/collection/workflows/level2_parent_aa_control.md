# Candidate parent A/A control

The fixed ledger control stage accepts only the baseline candidate ID. A final
comparison against a validated candidate parent needs a separate A/A report
for that parent's exact source, build, epoch, capture storage and 20-case suite.

`maintenance/level2_parent_aa_control.py` prepares an immutable request under
`task/parent-controls/NAME`, then calls the maintained `cohort_plan`,
`preflight_cohort`, and `collect_cohort` producers. Its completion records the
six-process report, group completion, actual costs and failure, if any. A
started collection is never implicitly retried. The control adds no source
attempt. `level2_finalize.py --calibration-for-control CANDIDATE=REPORT`
can bind its passed report to final direct-parent comparisons. The original
baseline A/A must be passed separately for original-baseline comparisons.

Capture remains `local` msprof with actual raw output under `/tmp`; seal and
replay raw, verification and native outputs after the entire cohort exits and
the final report authority is established. Retain failed or partial data.
