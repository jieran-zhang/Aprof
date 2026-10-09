# Execution mechanisms under a fixed parallel plan

Use the actual target profile, workload group, parent source and measured evidence. Low utilization on tiny work is an attainable-workload limit until a concrete bottleneck is shown.

| Evidence | Candidate direction | Disproof and required check |
| --- | --- | --- |
| Many short MTE instructions, low bandwidth | Coalesce contiguous copies, batch small scale/bias tables, reduce address setup | High MTE time alone is not bandwidth saturation; compare actual bytes and copy count |
| Repeated GM reads of unchanged tensors | Keep reusable data resident when capacity/lifetime permit | L2 is shared and not guaranteed resident; include all live buffers and full workload |
| Copy and vector/cube serialize despite double buffers | Separate prologue, steady state and drain; enqueue the next producer before consuming the current slot | A queue depth of two alone proves no overlap; check trace dependencies and all tail paths |
| Vector instruction count high for a fused chain | Fuse equivalent operations, avoid repeated Cast/UB round trips; on verified 3510 evaluate register-resident VF | Preserve intermediate precision and special values; inspect instruction counts and spills |
| Scalar control is dominant | Hoist metadata/address invariants, use constant indexing where legal, remove hot-loop state-machine work | Dynamic shape must remain correct; do not hardcode benchmark dimensions or replace every scalar with more expensive vector work |
| Idle gaps without a saturated pipeline | Examine wait/order, task granularity, buffer reuse and issue timing | More buffers or more cores can increase overhead; use the critical dependency chain |
| Capacity or bank conflict suspected | Calculate live intervals and aligned byte ranges; adjust padding/layout or reuse zones | Bank behavior is architecture-specific; padding increases occupancy and requires evidence |

Capacity is `sum(aligned live allocation bytes × simultaneously live instances) + scratch + reserved memory`. Include queue depth, stage buffers, Cast intermediates, API temporary space and synchronization workspace. A large tile can reduce loop overhead and simultaneously reduce overlap. Explore one bounded variable with the same parallel plan and dispatch group.

MatMul execution under fixed decomposition: choose baseM/baseN/baseK from L0A/B/C capacity, L1 steps from reuse and double buffering, and account for accumulation precision. Full-load is justified only when the reusable side fits throughout its lifetime. Ping/pong and preloading need a legal producer/consumer schedule; classify PONG gaps and tail drain separately. Small quantization scales are independent traffic and may benefit from coalescing. Changing M/N ownership, split-K or StreamK is a parallel-plan revision.

Softmax/attention: retain running max/sum/output state only for its owning task; normalize using the declared precision contract. Index workspace by the true task and split, not a reused block slot. Register or UB residency must fit concurrent buffers; a larger S2 tile is not always beneficial.

Sort/reduce local execution: validate scratch capacity and tail masking for every merge/reduction width. Do not apply a remembered MrgSort proposal width, repeat limit or index packing to a different SDK/architecture. The installed overload is authoritative. Cross-core merge/reduce changes are algorithm-parallel decisions.

Evidence report: expected mechanism movement, refuting signal, changed source anchors, resource equations, exact API provenance and first failed gate. Keep paired timings separate from full profiling counters.
