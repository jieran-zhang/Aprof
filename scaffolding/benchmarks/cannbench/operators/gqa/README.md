# GQA direct Ascend C benchmark

Correctness-only implementation of the level4 `gqa` task for Ascend910_9362
(`dav-2201`).  QK, causal masking, softmax, PV, GQA head mapping, and layout
conversion are all executed by the compiled device kernels.  The host only
loads tensors, derives tiling, launches kernels, and writes the result.

```bash
ASCEND_RT_VISIBLE_DEVICES=1 ./run.sh --all --device 0
```

No ACLNN/fused attention implementation, CPU precomputation, simulator, or
profiling is used.
