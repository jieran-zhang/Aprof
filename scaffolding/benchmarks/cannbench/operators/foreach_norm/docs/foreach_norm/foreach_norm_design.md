# foreach_norm 设计

## TensorList 直调

host 从一个连续输入文件按 `lengths` 依序读取列表元素。每个张量保持完整长度独立执行两次 AscendC launch，结果按原列表顺序写成同 dtype 的标量序列，因此逻辑输出仍是 `Tensor[]`。

## 两阶段归约

1. `foreach_norm_partial_kernel` 将一个张量分给最多 40 个 Vector Core。每核以 1024 元素 tile 搬入 UB，转 FP32、取绝对值，并按 mode 执行 `Power + ReduceSum`、`ReduceMax` 或非零计数；每核写一个 FP32 partial。
2. `foreach_norm_finalize_kernel` 在单核读取 partial。sum mode 再执行 `Power(sum, 1/p)`，inf mode 取最大值，随后转换为输入 dtype 并写一个标量。

该结构避免跨核原子浮点累加，也保证每个 TensorList 元素独立归约。

## Tiling

- `blockNum = min(vectorCoreNum, ceil(numel / 262144))`，至少 1。
- `blockLength = ceil(numel / blockNum)`。
- `tileElements = 1024`。
- GM/UB 尾块使用 `DataCopyPad`，`blockLen` 按实际字节数传入，不补写逻辑元素。

## UB 预算

最坏 BF16/FP16 partial kernel 活跃缓冲区：输入 2 KiB、cast 4 KiB、work 4 KiB、reduce 4 KiB、scalar 32 B，加 Power API stack workspace；FP32 路径不初始化也不访问 cast buffer。finalize 的 partial/reduce 各 256 B，输出/cast 各 32 B。

## 指令与 dtype

- FP32：`DataCopyPad -> Abs -> [Power] -> ReduceSum/ReduceMax`。
- FP16/BF16：增加 `Cast(T -> FP32)`，finalize 用 `Cast(FP32 -> T)`。
- `TBuf::Get<T>()` 与相应的 `InitBuffer()` 使用相同 `if constexpr` 守卫。
- device 代码不调用 host-only `ceil_div/align_up/align_down`。

## 验证范围

目标为 Ascend910_9362 / `dav-2201`。按用户要求只做编译和原始 20-case 精度验收；`harness.test_gate=off`，未做 profiling 或性能优化。
