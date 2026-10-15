# Architecture-aware, self-contained AProf workflow

The base workflow now separates algorithm parallel planning from execution tuning, and chooses an actual operator implementation per workload metadata region. The canonical skills live under `skills/aprof`; `skillgraph/registry.json` generates the portable plugin and installers. No external skill checkout is required.

## Stage and evidence flow

1. Preserve the complete operator semantics, precision contract, baseline source and declared workload matrix. Collect the actual target architecture profile with provenance.
2. Diagnose the source/workload and collect missing profiling evidence. Distinguish insufficient independent work from inefficient execution.
3. Use `ascendc-aprof-parallel-planning` to compare algorithms, task partitions, ownership, reduction/synchronization and workspace per workload group. Algorithm implementation attempts use `optimization_stage=algorithm_parallel`.
4. Bind a dispatch plan to the selected parallel plan: shape/dtype/layout/attributes select a unique uint64 tiling key and real kernel entry. Keep a general fallback, reject ambiguous regions, and verify boundary neighbors.
5. Freeze the plan for `optimization_stage=execution` candidates: tile, buffer, data movement, API and pipeline changes. Decomposition or ownership changes return to planning.
6. Gate every isolated candidate, measure affected regions and run the full correctness/regression matrix. Preserve source/plan/profile/dispatch hashes, selected key/entry, parent-best lineage and all failed/NOOP outcomes using the current trace contract.

The three planning contracts are `architecture_profile`, `parallel_plan` and `dispatch_plan`. They have strict schemas and canonical content hashes. Runtime context evidence contains these objects and their corresponding `_ref` hashes; existing strict v1 candidate episode fields are not silently extended. CAS registration and machine gates remain separate from JSON schema validation.

```bash
aprofctl contract validate --kind architecture_profile --input architecture.json
aprofctl contract validate --kind parallel_plan --input parallel-plan.json
aprofctl contract validate --kind dispatch_plan --input dispatch-plan.json
aprofctl dispatch select --plan dispatch-plan.json --workload metadata.json
aprofctl graph validate --graph skillgraph/versions/v0002
```

For a registered operator, use the target SDK's Host Tiling and key registration mechanism. For direct launch, implement equivalent host launcher dispatch or pass an explicit uint64 key to a matching kernel parameter. Logging a selector result without wiring the actual kernel does not implement dispatch. Benchmark case IDs and expected outputs cannot determine the key.

Consecutive rounds start from the selected previous parent that passed correctness and runtime validation, with its source hash and selection evidence preserved. Performance admission is independent: an exploratory parent with `formal_admission=not_evaluated` is not a production best. A failed round preserves the previous validated parent and still contributes its attempt/feedback trace. An aggregate all-case result is supplementary to per-group evidence; it must not hide a regression in another region or fallback.

## Platform identity and capability evidence

A2/910B and A3/910C share `DAV_2201`; `GetSocVersion` can return the same enum. Preserve the raw `aclrtGetSocName` result and actual device/die view. 950 PR/DT uses `DAV_3510`, with RegBase/SIMT and different data paths, but an architecture label alone does not prove API/dtype/compiler support.

The local `npu-arch` skill records official sources, their development/release status, installed SDK examples and unknowns. Resource sizes and counts come from the selected platform rather than family-name constants. In particular, no unverified bandwidth, SSBuffer capacity or universal dual-issue vector peak is installed as a default. Unknown capability/resource values cannot authorize a specialized candidate.

## Local knowledge and packaging

The thirteen historical support names remain compatible, but their registry sources now point to local `skills/aprof/support` capabilities. Long upstream workflow manuals are replaced by targeted AProf references for platform evidence, RegBase/SIMT, API/memory/event contracts, execution mechanisms, algorithm families and tiling dispatch. The former implicit precision-standard, direct-invoke-template and regbase-skill dependencies are absorbed by those local guides.

Four operational collectors/parsers are retained with copyright headers and license copies. Source links and upstream revision in NOTICE files provide attribution; they are not runtime loading requirements. The simulator trace analyzer retains its distinct Apache-2.0 license. Remote profiling resolves local collectors, and knowledge manifests hash actual local files. Historical frozen manifests and graph snapshots keep their original hashes/provenance.

The portable plugin flattens skill directories. The generator rewrites cross-skill Markdown links to their registry names, and materializes shared legacy contracts. Missing canonical support sources are errors rather than optional-submodule warnings. Claude and Cursor inventories include the same local support capabilities.

```bash
python3 scaffolding/tools/sync_aprof_registry.py write
python3 scaffolding/tools/sync_aprof_registry.py check
python3 -m unittest discover -s tests -p test_skill_self_containment.py
```

Self-containment tests build and install a temporary checkout containing no `third_party` directory, execute all four packaged collectors' help commands, and verify that every local Markdown link resolves inside the portable bundle. Existing Level1 dataset parity is a separate historical data integration test; it is not an external skill requirement.

## Level2 research campaign

`scaffolding/collection/scripts/level2_campaign.py` prepares the independent sixteen-operator campaign from the vendored canonical specifications. It preserves each operator's original split; participating former test operators are explicitly known workloads. Frozen per-case baseline pilots determine repeat counts before candidate testing. The [measurement protocol](level2_msprof_protocol_v2.md) defines full-call task coverage, resets, multi-output correctness, six-process pairing and the distinction between task sums and latency.

After the real architecture probe, preparation and all baseline pilots, `freeze` publishes the campaign manifest and independent train/validation ledgers. `freeze-engineering` snapshots producer and knowledge bytes. `materialize` binds an author's plan, draft and complete dispatch to actual implementation hashes; it does not author an intervention or infer a decision rationale.

`scaffolding/collection/scripts/level2_iteration.py baseline` checks all twenty standalone and prepared outputs, derives native lifecycle safety, and runs a small search-system self-check. New `candidate` searches use the [lightweight protocol](level2_search_lite.md): two processes, six pairs and direct-parent comparison after build, all-case correctness, runtime safety and independent semantic/dispatch guards. Historical frozen searches and final evaluation retain the full protocol. The next source proposal must cite a closed observation and name a validated parent. A compiler or source-correctness failure consumes its attempt; a measurement infrastructure failure remains blocked. Reusing an unchanged source adds observations and never creates a fictitious round.

Search feedback exposes only cases `[1,8,14,20]` and at most two predeclared probes. Full baseline calibration stays coordinator-only. Freeze all three source attempts and complete dispatches before final all-case performance comparison; preserve the tested implementation rather than assembling a new one from revealed case results. Per-case, per-key and full-operator reports retain both buffer configurations and their uncertainty.

`scaffolding/collection/scripts/level2_finalize.py --run RUN --operator OP` audits the three closed attempts, freezes all correctness/runtime/boundary-qualified candidates and their final comparison plans, then executes the complete twenty-case comparisons. `--prepare-only` stops after the immutable freeze. A resumed invocation verifies the original request, producer, source and evidence identities; it does not silently retry failed native work or release final-evaluation reservations. Final source selection is a separate explicit decision bound to an already tested implementation. No candidate is removed from the comparison set merely because its search result was slow.

`scaffolding/collection/scripts/level2_report.py --run RUN` reconstructs progress and effects from real ledger records and verified measurement evidence. Unregistered author drafts, pilots and unfinished infrastructure work do not become completed rounds. `scaffolding/collection/scripts/trace_v2_portable.py` creates a relocatable copy of each published archive with the original signed records and its complete evidence closure; the bundled verifier can validate it after the source archive paths are unavailable.

Research evidence uses the [optimization-memory and conditional-lesson v2 contracts](optimization_trace_collection_v2.md). Algorithm-plan and execution lessons link to real memories. A research runtime-safety assessment does not imply formal runtime admission: without a real compatible gate, reports remain `formal_admission=not_evaluated`, `graph_policy_eligible=false`, with no trainable graph episode.
