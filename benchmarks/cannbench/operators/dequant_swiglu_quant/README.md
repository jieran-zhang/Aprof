# dequant_swiglu_quant

Ascend C direct-invocation implementation for the authoritative CANN Bench level-3 task. The fused dequantization, SwiGLU, optional smooth scaling, per-token maximum, scale calculation, round-to-even, clamp, and int8 conversion all execute in the device kernel.

```bash
ASCEND_RT_VISIBLE_DEVICES=1 ./run.sh --all --device 0
```

This benchmark is correctness-only. Performance profiling was intentionally not collected.
