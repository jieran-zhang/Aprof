# resize_bilinear Ascend C 直调框架

Ascend 910 / dav-2201 correctness-first 直调实现，覆盖 level2 原始 20 cases，支持
FP16、FP32、BF16，`output_size`/`scale_factor` 和 `align_corners`。

```bash
source /usr/local/Ascend/cann-9.0.0/set_env.sh
./run.sh --case 1 --device 0
./run.sh --all --device 0
```

case 结果位于 `build/cases/case_XX/result.json`，全量汇总写入 `results.json`。
