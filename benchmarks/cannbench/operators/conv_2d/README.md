# conv_2d direct Ascend C benchmark

Correctness-first implementation for the level-3 `conv_2d` task. The binary directly launches custom dav-2201 kernels: AIV im2col, AIC `AscendC::MatmulImpl`, and AIV NCHW reorder/bias/cast. No host-side convolution or ACLNN operator performs the result computation.

```bash
ASCEND_RT_VISIBLE_DEVICES=2 ./run.sh --case 1 --device 0
ASCEND_RT_VISIBLE_DEVICES=2 ./run.sh --all --device 0
```

The original 20 cases come from `third_party/cann-bench/tasks/level3/conv_2d`. A clean real-device regression passes 20/20. BF16 results persist the FP32-accumulation mathematical oracle as primary correctness and the unchanged default oneDNN/ACL output as a separate diagnostic.
