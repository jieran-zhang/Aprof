# Raw archive parser dispatch compatibility

The first real raw shadow failed before report publication because the post-capture reader expected four `verified_dispatch` fields. The unchanged timing parser copies `select_dispatch`'s four fields (including boolean `fallback`) and appends `captured_kernel_sequence`, producing five fields. The original GN002 samples have this exact shape. Baseline samples omit `verified_dispatch` entirely.

The reader now accepts only that complete five-field object, checks uint64 key (excluding bool), boolean fallback, nonempty group, C identifier entry and a nonempty list of C identifier symbols. Unknown/missing fields and nested paths remain rejected. No nonexistent four-field legacy format is invented. No input, output, CSV, transport, report, measurement epoch or capture producer is changed.

Validation: 33 new CPU tests use the actual unchanged parser for selected/fallback and baseline samples, and test malformed schemas/values/paths. The 42 existing writer and 21 composed integration tests pass with the changed helper. A metadata-only check preserves all 2880 saved samples from six report-bound GN002 sessions, including 1440 dispatched samples. This check does not independently reread actual CSV/raw bytes or establish a successful full shadow.

Preserve failed `/tmp/aprof-raw-shadow-proof-020-02` and its six immutable shadows. Integration requires a fresh engineering freeze, a distinct qualification request/coordinator/output namespace, new producer-bound shadow seals and the full original report + evidence-only portable offline replay. No retirement is authorized by these CPU tests. Future attestor pins must explicitly bind the new helper hash. Both collection producers remain byte-identical.
