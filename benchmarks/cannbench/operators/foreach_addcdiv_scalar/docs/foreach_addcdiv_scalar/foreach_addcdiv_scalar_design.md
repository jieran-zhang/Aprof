# foreach_addcdiv_scalar 设计

## 直调接口

三个输入文件分别按 TensorList 顺序拼接，`--lengths n0,n1,...` 标明成员边界。host 在同一进程内依序处理每个成员，输出按同样顺序拼接，从而忠实承载原始三 TensorList schema。shape 仅影响元素数，逐元素 kernel 不需要维度信息。

为控制最大 case 的 host/device 内存占用，每个列表成员再按最多 8M 元素分 chunk。chunk 只改变 launch 粒度，不改变列表边界或结果。

## Kernel 与 tiling

- block 数：`min(vector_core_count, ceil(chunk_numel / 2048))`，至少 1。
- 每 block 处理连续区间；tile 为 2048 元素，尾 tile 使用 `DataCopyPad` 的字节级长度。
- float32 UB：x1/x2/x3/y 四个 2048 元素 buffer，共 32 KiB。
- float16/bfloat16 UB：四个原 dtype buffer 共 16 KiB，加四个 FP32 compute buffer 共 32 KiB，总计 48 KiB。
- 所有完整 tile DMA 均远大于 32B；尾 tile 由扩展 DataCopy API 处理任意字节数。

计算序列：

1. 三路 GM → UB。
2. FP16/BF16 输入分别 Cast 到 FP32；FP32 直接计算。
3. `Div(x2, x3)` → `Muls(scalar)` → `Add(x1)`。
4. FP16/BF16 输出 Cast 回原 dtype（BF16 使用 `CAST_RINT`）。
5. UB → GM。

目标是精度正确的 flash 初版，不包含性能优化或 profiling。
