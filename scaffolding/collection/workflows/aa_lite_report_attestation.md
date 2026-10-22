# Closed lite A/A report audit

`aa-search-lite-031` in the resumed Gather task finished before any later timing
stage cited its report hash. Its two native sessions and saved report are complete,
but the existing ledger timing-calibration admission cannot anchor that report.
Keep their raw, native outputs and verification files loose until the separate
retrospective audit is complete.

After all native and report writers exit, run
`level2_aa_lite_report_attestation.py --repository REPO --run RUN
--engineering RUN/bootstrap/frozen-engineering-NNN.json --writers-closed`.
The audit reanalyses the original two-process, four-case, six-pair lite A/A
report with the reviewed msprof analyzer. It checks the full normal/swapped
observation roster, native/report artifact hashes, historical producer
snapshots, the successful ledger control stage and a frozen engineering roster.
It publishes immutable request, attestation and ledger-prefix files, then
appends one typed event to the task event chain. It runs no native code and
does not assert that the report hash was anchored at capture time.

The verification reader accepts only this exact Gather control namespace, a
reviewed audit writer snapshot, the matching task event and the saved report
hash. The raw reader writes v7 for this retrospective authority; v1–v6 seals
retain their original producer and authority identities. Native v2 and
verification v2 can then archive the two sessions with their ordinary seal,
replay and receipt checks. An absent or invalid audit leaves the loose files
in place. A shadow archive under `/tmp` should be checked before retirement.
