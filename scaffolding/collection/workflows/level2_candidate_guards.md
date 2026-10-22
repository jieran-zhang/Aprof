# Candidate-bound GroupNorm semantic guards, version 1

A proposal may explicitly name `semantic_guard_draft`, a SHA-256 pointer to
`candidates/<id>/semantic-guards/draft.json`. `materialize_candidate` validates
and binds the resulting `semantic_guard_contract` artifact to the exact source
archive and dispatch plan. Registration revalidates every input, reference,
original oracle, and declared key before appending a source attempt.

This initial implementation supports GroupNorm only. A revision retains all
original cases in order, metadata and input/reference bytes unchanged. It may
update expected keys according to the candidate dispatch and add bounded cases
computed with the original PyTorch oracle. It cannot supply executable Python
or replace tolerances: the runner is a reviewed fixed template. The original
agent guard and prior feedback remain untouched. Existing requests without an
explicit artifact follow the original v1 path.

Collection requires the registered proposal/ledger identity, verifies the
complete contract before any native call, and writes a v2 request bound to the
helper producer. Results retain actual native executions, real dispatch logs,
preparation and verification. New guard numeric failures remain conservatively
blocked under the unchanged classifier; this patch does not reclassify prior
GN001 or RMS001 observations or relax any numeric standard.

Archive collection closes the entire guard bundle, original references and
private execution evidence, so portable export retains their bytes. The helper
and runner are fresh-producer allowlist members; freeze engineering before any
new collection. A changed helper producer can be resolved only through the
existing exact task-attested frozen engineering CAS. Native binaries, candidate
scripts, inputs, outputs and guard contracts never receive producer substitution.

Authoring/materialization is not a source attempt or correctness qualification.
It runs CPU golden checks; full original correctness and the expanded guards
must still pass after an authorized source registration/build. Never infer
full-operator qualification from component probes.

A revision also names `original_observation` (closed ledger observation ID and
feedback pointer). Original case metadata and all retained input/reference bytes
must occur in that immutable closed source-failure evidence. Rehashing a changed
original roster or replacing the earlier inputs cannot redefine retention.

V2 completion binds `evidence-closure.json`, the exact private file set and all
bytes of preparation, native records, verification, health, inputs and outputs.
Replay rejects additions, removals and mutations. Output sizes must exactly match
the bound reference; a fractional trailing element is an error.
