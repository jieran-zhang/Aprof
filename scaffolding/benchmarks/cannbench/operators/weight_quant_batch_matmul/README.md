# weight_quant_batch_matmul direct Ascend C benchmark

Correctness-first direct launch for the 20 authoritative level-3 cases. Build and run on physical device 1 with:

```bash
ASCEND_RT_VISIBLE_DEVICES=1 ./run.sh --all --device 0
```

The implementation performs weight dequantization, Cube matrix multiplication, bias addition, and output conversion on device. It does not call ACLNN and does not precompute outputs on the host.
