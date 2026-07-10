# API And Algorithm Injection Recipes

Use these recipes for scalar loops, underused vector APIs, redundant cast/vector-copy paths, inefficient reduce/matmul proxies, and missing fusion signals.

## Recipes

| problem_id | label | Injection | Evidence |
| --- | --- | --- | --- |
| `scalar_loop_redundant` | `scalar_loop_redundant` | Insert redundant scalar loop under `APROF_INJECT_SCALAR_LOOP` | Scalar ratio/time |
| `small_vector_api_chunks` | `small_vector_api_chunks` | Shrink tile length to small vector counts | vector utilization, scalar/MTE overhead |
| `redundant_cast_or_vector_copy` | `redundant_cast_or_vector_copy` | Add equivalent `Adds(+0)` vector operation under `APROF_INJECT_REDUNDANT_VECTOR` | vector instruction mix/time |

## Rules

- Prefer behavior-preserving equivalent operations over math changes.
- Do not add real dtype casts unless the source already has safe Cast buffers and dtype context.
- Active validation usually requires `PipeUtilization.csv` and, when available, `ArithmeticUtilization.csv`.
