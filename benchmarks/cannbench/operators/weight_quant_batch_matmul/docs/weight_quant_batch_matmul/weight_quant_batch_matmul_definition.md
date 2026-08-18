# WeightQuantBatchMatmul definition

Source: `third_party/cann-bench/tasks/level3/weight_quant_batch_matmul`.

For `x:[M,K]`, signed INT8 `weight:[K,N]`, per-column `scale:[N]` (or `[1,N]`), optional per-column `offset`, and optional per-column `bias`:

```text
dq[k,n] = round_T((round_T(weight[k,n] + offset[n])) * scale[n])
y[m,n]  = round_T(sum_k(float32(x[m,k]) * float32(dq[k,n])) + float32(bias[n]))
```

The inner addition is omitted when offset is absent and bias is omitted when absent. `T` is FP16 or BF16 and is also the output dtype. Bias is FP16 for FP16 input and FP32 for BF16 input. The authoritative cases cover all optional-input combinations, flat and `[1,N]` broadcast shapes, M 1–128, K 2048–28672, and N 1408–14336.
