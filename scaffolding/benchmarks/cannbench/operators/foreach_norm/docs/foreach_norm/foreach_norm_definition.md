# foreach_norm 定义

来源：`third_party/cann-bench/tasks/level1/foreach_norm/{desc.md,proto.yaml,golden.py,cases.yaml,cases.csv}`。

## Schema 与语义

```text
foreach_norm(Tensor[] x, float scalar) -> Tensor[] y
```

输入列表的第 `j` 个张量独立产生一个标量张量：

```text
y[j] = (sum_i abs(x[j][i]) ** p) ** (1 / p)
```

其中 `p=scalar`。`p=0` 为非零元素数，`p=+inf` 为最大绝对值。负阶遵循 `torch.norm`；输入含零时相应结果可为零。输入张量可有不同 shape，但列表内 dtype 一致。

## dtype

- 输入/输出：FP16、FP32、BF16。
- FP16/BF16 先转换为 FP32 计算，再转换回输入 dtype，与 golden.py 一致。
- 每个输出是与对应输入 dtype 相同的单元素标量，按 TensorList 顺序写出。

## 特殊值与边界

- `p=+inf` 保留 IEEE `inf`，取全张量绝对值最大值。
- 全零张量的正阶范数为零。
- 原始用例包含 1D–5D、非 32B 对齐尾块、TensorList 长度 1–4、单张量约 1M–49.7M 元素。
- case 12 的输入范围含 `-inf/+inf`，校验同时比较 NaN/正负 Inf 分类。

## Golden

数据生成器先按输入 dtype 量化，再执行源 golden 的等价逻辑：FP16/BF16 转 FP32，调用 `torch.norm(tensor, p=scalar)`，最后转回原 dtype。
