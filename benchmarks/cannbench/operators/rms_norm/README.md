# rms_norm AscendC 直调算子

面向 Ascend910 / dav-2201，支持 float16、float32、bfloat16，gamma/weight 和正 epsilon，
所有归一化内部计算采用 FP32。

```bash
./run.sh --case 1 --device 2
./run.sh --all --device 2
```

原始 20 cases 的逐 case 结果位于 `build/cases/`，汇总位于 `results.json`。
