# gather 设计

目标为 Ascend910 / `dav-2201` 的正确性初版。host 计算 x 的连续 stride，把 index
shape、stride、dim 和 dtype 存入 tiling。每个 vector core 负责一段连续 output，按
index shape 将线性位置恢复为坐标，用 index 值替换 dim 坐标并计算 x 的源偏移。

数据不参与算术，kernel 按 1/2/4/8 字节无符号存储类型直接 GM 读取和写回，确保
NaN、Inf、bfloat16 和整数逐位保真。index 按 int8/int32/int64 分发。host 在 launch
前扫描并拒绝负数/越界 index，device 另有边界保护，避免非法输入导致越界访存。

不使用 UB、queue、DMA 或 Cast，`liveBytesPerElem=0`，不存在 32B DMA 尾块和 TBuf
生命周期。`blockNum=min(vector_core_count, ceil(output_numel/4096))`，避免极小输出
被拆成大量不足一个调度工作单元的 core 区间；本轮按用户要求不做进一步优化。
