# AProf 1.0.1 Wiki — inherited exp-only knowledge

This is a conditional reading layer for AscendC 910C/A3 work. Start at
`index.json`, read one relevant page, and return to SkillGraph for legal
routing. A page does not itself establish a machine verdict or permit
skipping correctness.

The inherited 1.0.0 release scope is only `exp-tile8192` on 910C/A3 with CANN
9.0.0. Its retained 20-case correctness, 42 boundary checks and full formal
Task timing have been replayed, and its missing five candidate PMU captures
and oracle are complete. The final gate replay returned
`production_safe_gain`, and the gate-only process exited successfully with
code 0. It added no build, PMU capture or formal timing sample.

Only `exp-tile8192` and its single canonical skill revision carry that validation.
This 1.0.1 package is unsealed; the inherited receipt does not qualify its runtime
changes or supply a verdict for a new optimization attempt. `tile-amortization` remains draft because its
mish/addcdiv observations are outside the exp receipt. `sigmoid-pipeline` and
all other pages also remain draft and need their own independent evidence.
The 45-run validation comparison and post-seal full test evaluation are not
run under this limited scope.

Source IDs and byte hashes are frozen in
`scaffolding/curation/graph-base-1.0.0.json` in the development repository.
Raw traces are not copied into the installed skill lib. `evolution.jsonl`
keeps accepted, deferred and rejected proposals. The original attempt's
oracle-parsing failure and the PMU continuation's evidence-binding failure
retain their failed statuses; the later successful gate-only continuation is
a separate record.
Validation and test traces are excluded from these pages.

No Wiki page supplies a missing SkillGraph predicate, unlocks a route or
bypasses the registered stopping rule. Only a replayable, source-bound
promotion receipt can change a rule's publication status.
