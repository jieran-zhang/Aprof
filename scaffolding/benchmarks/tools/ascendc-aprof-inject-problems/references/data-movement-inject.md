# Data Movement Injection Recipes

Use these recipes for GM access frequency, DataCopy granularity, repeated copies, and CopyIn/CopyOut dominance.

## Recipes

| problem_id | label | Injection | Required evidence |
| --- | --- | --- | --- |
| `redundant_copyin` | `redundant_copyin` | Duplicate GM->UB `DataCopy` under `APROF_INJECT_REDUNDANT_COPYIN` | `Memory.csv` MTE2 counts or trace proxy |
| `extra_copyout` | `extra_copyout` | Duplicate UB->GM `DataCopy` under `APROF_INJECT_EXTRA_COPYOUT` | `Memory.csv` MTE3 counts or trace proxy |
| `small_datacopy_granularity` | `small_datacopy_granularity` | Reduce tile length to 8 elements | single-copy bytes and MTE instruction density |

## Safe Patch Pattern

- Only duplicate an already-correct copy of the same address range.
- Do not change the tensor feeding final math.
- If the expected `DataCopy(aLocal, inputGlobal[outOffset], copyParams)` or `DataCopy(outputGlobal[outOffset], outLocal, copyParams)` anchor is absent, mark the case `unsupported`.

## Validation

- Prefer `hw-op` when real `Memory.csv` is available.
- Simulator trace can only be labeled as proxy evidence.
