# engram_gate_fusion direct invoke

Correctness-first Ascend C direct-invoke implementation of the 20 original
`third_party/cann-bench/tasks/level3/engram_gate_fusion` cases.

```bash
ASCEND_RT_VISIBLE_DEVICES=1 ./run.sh --case 1 --device 0
ASCEND_RT_VISIBLE_DEVICES=1 ./run.sh --all --skip-build --device 0
```

The host performs validation, allocation, transfers, and kernel launch only.
All RMSNorm, gating, convolution, activation, residual, and state-update math
runs in the two compiled Ascend C stages on the NPU.
