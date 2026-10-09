# resize_bilinear 设计

输出按 NCHW 连续展开，每个 core 获得按 64B 对齐的连续区间，逐输出读取四个输入点并
以 FP32 计算。FP32 直接写 GM；dav-2201 上 B16 标量写不可靠，因此 FP16/BF16 先写
1024 元素 FP32 UB tile，再 `Cast` 到 B16 UB 并通过 `DataCopyPad` 写回。B16 输入用
IEEE 位级软件解码，避免 device scalar cast 差异。

FP32 无 UB；B16 `liveBytesPerElem=6B`，总 UB 6144B。尾 tile 的 `blockLen=count*2`
按字节传递，无 UB-to-UB copy。验证逐 batch 计算 PyTorch golden，避免大 case 内存峰值。
相对误差采用带绝对地板的混合判定，并独立检查 NaN/+Inf/-Inf。

坐标计算严格先生成 PyTorch 同序的 FP32 `scale`，再与输出索引相乘；不能把乘法移到
除法前，否则 align=true 的大倍率上采样会放大坐标舍入差。
