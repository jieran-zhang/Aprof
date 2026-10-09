# gcd 设计

目标为 Ascend910 / `dav-2201` 的可运行初版。由于经典 AscendC 没有整数向量余数
原语，使用 vector core 多核标量实现。host 将最多 8 维的输出 shape 和两个输入的广播
stride 写入 tiling；每核负责一个连续输出区间，每个元素由线性下标恢复广播坐标。

整数先按位宽转换为 `uint16_t`、`uint32_t` 或 `uint64_t`，以二补码计算绝对幅值，
随后执行 Euclid `%` 循环，最后把位模式转换回原 dtype。此路径不使用 UB、queue、
DMA 或 Cast，因此 `liveBytesPerElem=0`，不存在 32B DMA 尾块与 TBuf 生命周期问题。

`blockNum=min(vector_core_count,totalLength)`，`blockLength=ceil(totalLength/blockNum)`。
输入/输出均为直接 GM 访问；性能优化按用户要求暂不进行。
