# Portable CPU paper examples

These examples exercise the frozen D7/P4/O7, routing6, policy2 runtime contracts. They do not run a target compiler, correctness oracle, profiler, or device. `C3.result=implemented` and the saved validation status mean the paper declarations satisfy the handoff contract; they are not execution or performance receipts.

- `single-transfer/`: one contiguous-transfer Action.
- `transfer-derived-reuse/`: contiguous transfer plus the new derived-result-reuse Action.
- `transfer-buffer-management/`: contiguous transfer plus the new buffer/event-management Action.

Each task has a complete canonical workload before its first decision file, an explicit nonempty scheme ID and hash, a shared plan, member-specific routes and actual leaf selections, source/parameter/compatibility bindings, C1/C2/C3 JSON, and a validation report. Evidence is synthetic and labeled paper-only. Performance predictions remain unknown. The two new-intent examples reference an initial `routing-structure.json` declaration from their source context: derived values with multiple consumers, or buffer/event completion structure. These are explicit CPU contract declarations that justify the context tags; they do not verify actual source understanding or practical automatic-routing usefulness.

Replay a chain with the package runtime (replace `PACKAGE` and `TASK` with their local paths):

```sh
aprofctl knowledge validate-chain --root PACKAGE --task-root TASK --c1 TASK/C1.json --c2 TASK/C2.json --c3 TASK/C3.json
```

The task files contain relative references. They can be copied to another task directory and replayed with the same frozen package. No timing result is included. Check `example-metadata.json` and the root `index.json` before interpreting any status.
