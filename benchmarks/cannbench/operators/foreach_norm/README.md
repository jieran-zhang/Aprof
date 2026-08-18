# foreach_norm AscendC 直调

对 `Tensor[]` 中每个张量独立计算 `torch.norm(x, p=scalar)`，返回同 dtype 的标量张量列表。实现保持 cann-bench level1 的原始 schema：

```text
foreach_norm(Tensor[] x, float scalar) -> Tensor[] y
```

支持 FP16、FP32、BF16，以及原始 cases 覆盖的正阶、负阶和 `inf` 范数。FP16/BF16 在 FP32 中计算后转换回输入 dtype。

## 构建与运行

```bash
./run.sh --case 1 --device 2
./run.sh --all --device 2
./run.sh --all --skip-build --device 2
```

`run.sh --all` 原样执行 `third_party/cann-bench/tasks/level1/foreach_norm/cases.yaml` 的 20 个 case，不缩减 shape、TensorList 或 case 数量。逐 case 结果及汇总保存在 `results.json`。

## 目录

```text
op_host/foreach_norm.asc                 ACL host 直调入口
op_kernel/foreach_norm_kernel.asc        AscendC partial/finalize kernels
op_kernel/foreach_norm_tiling.h          dtype、mode 与 tiling
scripts/cases.py                         原始 20-case 矩阵
scripts/gen_data.py                      输入和 torch golden
scripts/verify_result.py                 MERE/MARE 与特殊值校验
scripts/summarize.py                     results.json 汇总
docs/foreach_norm/                       定义、设计、STATE 与排障记录
```

当前验证目标为 Ascend910_9362 / `dav-2201`，真实设备 2 上 20/20 case 通过。按加速开发要求未做性能优化或 profiling。
