# AI Core Utilization Injection Recipes

Use these recipes for low Vector/Cube utilization, underused cores, empty cores, load imbalance, and tail drag.

## Recipes

| problem_id | label | Injection | Evidence |
| --- | --- | --- | --- |
| `underused_blockdim` | `underused_blockdim` | Large enough work with `default_blockdim=1` | core utilization below hardware core count |
| `overlaunched_empty_cores` | `overlaunched_empty_cores` | Small output with high blockDim | idle/near-empty cores, head overhead |
| `tail_core_imbalance` | `tail_core_imbalance` | Non-divisible output plus multi-core/tail path | per-core duration imbalance |

## Rules

- Active validation requires hardware core denominator from `/npu-arch`, `PlatformAscendC`, or profile context.
- Sim-only output is proxy evidence unless per-core trace clearly shows imbalance.
- Do not treat low blockDim as an error for inherently tiny workloads.
