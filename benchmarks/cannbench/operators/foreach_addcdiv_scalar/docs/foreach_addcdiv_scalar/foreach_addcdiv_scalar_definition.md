# foreach_addcdiv_scalar 定义

来源：`third_party/cann-bench/tasks/level1/foreach_addcdiv_scalar/{desc.md,proto.yaml,golden.py,cases.yaml,cases.csv}`。

对三个等长 TensorList 的对应成员执行：

```text
y[i] = x1[i] + (x2[i] / x3[i]) * scalar
```

- `x1`、`x2`、`x3`：等长 `Tensor[]`，对应 tensor 的 shape 和 dtype 相同。
- `scalar`：必选 float。
- `y`：与输入等长，每个成员 shape/dtype 与对应输入一致。
- 支持 `float16`、`float32`、`bfloat16`。
- FP16/BF16 按 golden 先转换为 FP32 计算，再转换回输入 dtype。
- 运算顺序固定为除法、标量乘法、加法，不允许代数重排。
- `scalar=inf/nan` 与输入特殊值按 IEEE 分类验证；输出 NaN、+Inf、-Inf 的位置必须和 golden 完全一致。

原始 cases 覆盖列表长度 1–4、1D–5D、对齐/非对齐 shape、约 1M–99M（列表合计）元素以及正/负/零/inf/nan scalar。测试不得缩减任何 shape 或列表长度。
