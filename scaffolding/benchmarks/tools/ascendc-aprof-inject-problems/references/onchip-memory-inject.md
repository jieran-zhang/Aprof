# On-Chip Memory Injection Recipes

Use these recipes for UB/L1/L2 reuse problems, temporary tensor pressure, workspace misuse, and GM spill proxies.

## Recipes

| problem_id | label | Injection | Evidence |
| --- | --- | --- | --- |
| `ub_temp_overallocated` | `ub_temp_overallocated` | Allocate an unused UB buffer under `APROF_INJECT_UB_OVERALLOC` | UB occupancy formula |
| `gm_spill_intermediate` | `gm_spill_intermediate` | Extra safe CopyOut as a GM spill proxy | write traffic amplification |
| `low_ub_reuse` | `low_ub_reuse` | Redundant CopyIn as a low-reuse proxy | read traffic amplification, L2 hit |

## Rules

- UB over-allocation must not overlap existing tensors or change output.
- GM spill proxies must write an equivalent value that is later overwritten or identical to final output.
- Prefer hardware memory CSV for active labels; source-only UB occupancy remains derived evidence.
