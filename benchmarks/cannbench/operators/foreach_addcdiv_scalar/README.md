# foreach_addcdiv_scalar AscendC 直调

实现原始 schema：

```text
foreach_addcdiv_scalar(Tensor[] x1, Tensor[] x2, Tensor[] x3, float scalar) -> Tensor[] y
y[i] = x1[i] + (x2[i] / x3[i]) * scalar
```

工程面向 Ascend 910 (`dav-2201`)。`x1.bin`、`x2.bin`、`x3.bin` 按列表顺序拼接各 tensor，`--lengths` 保存每个 tensor 的元素数；直调 host 在同一进程中按列表成员顺序执行 kernel，并将输出按相同顺序拼接。因此 TensorList 的长度、成员边界、shape 与 dtype 语义均保留。

## 编译与运行

```bash
./run.sh --case 1 --device 0
./run.sh --all --device 0
./run.sh --all --skip-build --device 0
```

`--all` 严格执行 `third_party/cann-bench/tasks/level1/foreach_addcdiv_scalar/cases.csv` 的全部 20 个 case，不缩减 shape、列表长度或 dtype。每例精度结果保存在 `build/cases/case_XX/result.json`，总结果保存在 `results.json`。

## 文件

- `op_kernel/foreach_addcdiv_scalar_kernel.asc`：AscendC device kernel。
- `op_kernel/foreach_addcdiv_scalar_tiling.h`：host tiling。
- `op_host/foreach_addcdiv_scalar.asc`：ACL 初始化、TensorList 流式直调和结果落盘。
- `scripts/cases.py`：原始 20 cases 的本地镜像。
- `scripts/gen_data.py`：确定性输入与 FP32 compute golden 生成。
- `scripts/verify_result.py`：MERE/MARE 及 NaN/Inf 分类验证。
- `results.json`：Ascend 910 device 0 实测汇总。

本 flash 初版仅以可编译、可运行和精度正确为目标，未做性能优化或 profiling。`harness.test_gate=off`，因此未执行额外黑/白盒门禁。
