# Tiling Injection Recipes

Use these recipes for blockDim, tileLength, tileNum, tail, and dynamic-shape tiling problems.

## Recipes

| problem_id | label | Main knob | Evidence |
| --- | --- | --- | --- |
| `blockdim_too_small` | `blockdim_too_small` | `default_blockdim=1` | `Block Dim / coreNum`, task duration |
| `tile_length_too_small` | `tileLength_too_small` | `default_tile_length=16` | MTE instruction density, small copy granularity |
| `tile_length_too_large` | `tileLength_too_large` | `default_tile_length=4096` | totalTiles below core count, UB pressure |
| `tile_num_unreasonable` | `tileNum_unreasonable` | `default_tile_num_mul=4` | extra tile loop count, idle tile branches |
| `tail_inefficient` | `tail_inefficient` | `APROF_INJECT_TAIL=1` plus non-divisible output size | tail branch copy/barrier evidence |
| `fixed_tiling_dynamic_shape` | `fixed_tiling_dynamic_shape` | `APROF_INJECT_DYNSHAPE=1` | multi-shape comparison |

## Rules

- Keep one tiling knob changed per case.
- Prefer `scaffold_project` for host-side blockDim and dynamic-shape tiling.
- Sim-only cases can be generated but remain `unverified` until build/profile evidence exists.
- Dynamic-shape recipes need at least two shapes before becoming `active`.
