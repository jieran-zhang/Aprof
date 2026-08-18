# AProf runtime schemas

These JSON Schemas document serialization version `1.0.0`. The Python runtime
is the authoritative validator and additionally enforces cross-field
invariants (probability sums, candidate/evidence identity, hashes, paired
measurements, gate replay, route replay, and state-machine ordering). All object
schemas reject unknown fields. `tests/test_schema_parity.py` keeps a shared
valid/invalid corpus aligned across JSON Schema and the Python models.

`handler-attempt.schema.json` is a shape-validated exploration sidecar for the
handler, parameter, context, and retry decisions that the immutable v1
candidate episode does not model. It does not attest graph/edge/candidate
references, is not linked into EpisodeStore/CAS, grants no reward authority,
and is not embedded into the v1 episode.
