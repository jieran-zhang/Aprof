# Retrospective final report consistency attestation

The standalone tool replays a closed Level2 finalization and appends one typed task event. It does not execute native work, create source attempts, observe feedback, select a winner, or change measurement/calibration status. The claim is retained consistency at this audit, never historical measurement authority.

After freezing the installed engineering, use `python scripts/level2_final_report_attestation.py inspect --run /ABS/RUN --operator maximum --request-sha256 sha256:EXACT_FINAL_REQUEST --engineering /ABS/RUN/bootstrap/frozen-engineering-NNN.json`. The corresponding `attest` command additionally requires `--writers-closed`; it streams actual evidence and publishes the new audit. A real successful audit and offline closure qualification are required before final evidence retirement.

This v4 source package preserves the approved v3 implementation and protocol `level2_final_report_consistency_attestation_v2`. Its only implementation changes are the exact reviewed storage profile and the explicit `level2_final_report_authority` Runtime dependency. The storage profile pins integration patch `11208eed8ad7ed1171a7290b44a869df11338c95a7f6bbe820838d5b7df5ca13`, raw68742f, verifier78ff7d, facade47fa96, nativea08bb1, reporte18685, unchanged capture4d4f8d and parserc3d60d. Complete hashes are literal in the source. The authority reader is discovered and bound by actual engineering/CAS closure, rather than statically pinned here: its reviewed-writer table contains this writer hash, so including it in the static profile would create a cycle.

The full audit includes every final comparison and each unique A/A calibration, all20 cases, normal/swapped and all six processes. Full saved-report comparison uses only the established analysis-producer provenance exception. Every other field and logical reference remains exact. Invalidated calibration remains invalidated. Historical producer snapshots are inert bytes, never executed. Original raw-v1 proofs retain verification452c/nativea08 identity under the trusted new reader.

Every actually loaded repository dependency, the current tool and retained source snapshots must match the supplied canonical engineering manifest/CAS. The tool retains all original source, stage, report, event-prefix and logical evidence bindings. Its compact storage catalog contains exact origins plus one full archive binding per seal and content-deduplicated complete nested proof objects. No nested proof is pruned.

The existing full audit reader context exits before durable audit publication. The final pre-event pointer audit uses a separate reader context and must exit successfully before event append, under the existing host, ledger and recorder locks. Reentry after publication repeats complete replay and preserves prior committed bytes. A failed pre-event check may leave an uncommitted audit directory but cannot emit a success event. No automatic retry executes native work.

Separate versioned data-only authority admission and complete tar/catalog export are supplied by the reviewed final-authority and storage-integration packages. Applying these packages is not real-data qualification. Fresh raw-v2 AA/search shadow plus old-v1 compatibility replay and a subsequent actual final audit/closure qualification remain required before production final retirement.

CPU tests cover real append-only ledgers with an explicit fake report analyzer,
compact catalog integrity, import/profile checks and tiny retired-raw fixtures.
They provide no actual campaign or NPU qualification. Run them with
`python3 -m pytest tests/test_final_report_attestation.py tests/test_attestor_facade.py tests/test_attestor_real_raw_reader.py`.
