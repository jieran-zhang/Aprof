# rms_norm 设计

目标 Ascend910 / dav-2201。每个 core 处理连续若干行；每行完整放入 UB，D 最大 8192。
raw x/gamma/output 各占 `D*sizeof(T)`，FP32 cast/output/scratch 最坏各 `4D`，总 UB 在
半精度最大 D 时约 176 KiB。序列为 DataCopyPad→Cast FP32→Mul square→ReduceSum→
FP32 mean+epsilon→Rsqrt→两步 FP32 Newton 修正→Muls x→Mul gamma→Cast output→
DataCopyPad。尾长度由扩展 DMA
按实际字节处理。性能优化和 profiling 按用户要求跳过。
