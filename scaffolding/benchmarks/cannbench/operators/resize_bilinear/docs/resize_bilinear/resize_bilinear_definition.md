# resize_bilinear 定义

输入 `x[N,C,H,W]`，输出 `y[N,C,Ho,Wo]`。输出尺寸由 `output_size` 指定，或由
`floor([H,W]*scale_factor)` 得到。支持 FP16/FP32/BF16，输出 dtype 与输入相同。

输出坐标 `o` 映射为：align=true 且输出长度大于 1 时
`i=o*(I-1)/(O-1)`；align=false 时 `i=(o+0.5)*I/O-0.5`，并裁剪到输入边界。
周围四点按高宽小数距离做双线性加权。CPU golden 为
`torch.nn.functional.interpolate(mode='bilinear')`。NaN/Inf 按 IEEE 传播并单独验证掩码。
