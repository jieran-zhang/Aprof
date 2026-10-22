# Pipeline Parallel Injection Recipes

Use these recipes for CopyIn/Compute/CopyOut serialization, double-buffer failure, queue depth issues, and excessive synchronization.

## Recipes

| problem_id | label | Injection | Evidence |
| --- | --- | --- | --- |
| `serial_copy_compute_copyout` | `serial_copy_compute_copyout` | Insert extra `PipeBarrier<PIPE_ALL>` around each tile | trace overlap drops |
| `excessive_pipe_barrier` | `excessive_pipe_barrier` | Insert repeated barriers under `APROF_INJECT_EXCESSIVE_BARRIER` | sync/wait events or trace drains |
| `double_buffer_disabled` | `double_buffer_disabled` | Only supported when source exposes an explicit DB knob | queue depth and trace |

## Rules

- Do not invent DB changes in kernels without queue/depth knobs.
- Extra barriers preserve math but must remain `unverified` until trace or profile evidence confirms the signal.
- If no safe tile-loop anchor exists, emit `unsupported`.
