# Architecture and metric routing

Select the backend from the actual SoC and installed tool capabilities before
choosing metrics. The AProf optimization scope remains primarily Vector on
910C/A3. Support for a profiler on 950 is a separate capability.

| Environment | Mechanism profiler | Boundary |
| --- | --- | --- |
| Ascend 950 / dav-3510, matching CANN/tool version | npu-compute | Ascend C, a supported single operator invocation; confirm installed Sections. |
| Ascend 910C / A3 | msprof op | Current supported hardware route; do not install an incompatible npu-compute. |
| Other/unknown | Explicit preflight | No inference from shared DAV_2201 ISA or tool presence alone. |
| No hardware / requested simulator | msprof op simulator | Proxy evidence only. |

On npu-compute use the following views; on msprof use matching available CSVs
without assuming their aggregation or counter definitions are identical.

| Diagnostic question | npu-compute Section/file |
| --- | --- |
| Kernel task time, block count and identity | summary.jsonl / OpInfoSummary |
| Scalar/Vector/MTE activity and Core balance | PipeUtilization |
| Traffic amplification and transfer granularity | Memory plus workload byte lower bound |
| Arithmetic utilization | ArithmeticUtilization plus actual architecture denominators |
| Wait/conflict | ResourceConflictRatio |
| UB/L0 traffic | MemoryUB / MemoryL0 |
| Cache hits/misses | L2Cache |
| Sampled pipeline overlap | Pipeline / PipeTrace.json |

Read [tool semantics](../../tool-npu-compute/references/evidence.md) before
interpreting npu-compute output. `PipeUtilization` plus `Memory` supplies active
bandwidth dependencies missing from a Pipe-only capture. Prefer a small Section
selection tied to the current hypothesis. Trace sampling does not establish Core
coverage or all-kernel timing.

For msprof commands and simulator compatibility, read
[metric-to-msprof.md](metric-to-msprof.md). For repeated collection and source
replay, use [collector-interface.md](collector-interface.md).
