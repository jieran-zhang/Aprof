# grid_sampler_3d 定义

## 接口

`grid_sampler_3d(x, grid, interpolation_mode="bilinear", padding_mode="zeros", align_corners=false) -> y`

- `x`: `[N,C,D,H,W]`，FP16 或 FP32。
- `grid`: `[N,Do,Ho,Wo,3]`，与 `x` 同 dtype；最后一维按 PyTorch 约定为
  `(x,y,z)`，分别索引输入的 `(W,H,D)`。
- `y`: `[N,C,Do,Ho,Wo]`，与 `x` 同 dtype。

## 坐标和插值

对每个归一化坐标 `g` 和长度 `S`：

- `align_corners=true`: `p=(g+1)*(S-1)/2`
- `align_corners=false`: `p=((g+1)*S-1)/2`

`nearest` 使用 round-to-nearest-even。`bilinear` 在 5D 输入上是三线性插值：对
`floor(x/y/z)` 及其后一位置的八个体素，以三个轴的小数距离乘积加权求和。

`zeros` 对每个越界邻点贡献零；`border` 将连续坐标裁剪到 `[0,S-1]`；
`reflection` 在 `align_corners=true` 时绕 `[0,S-1]`、false 时绕
`[-0.5,S-0.5]` 重复反射，最后裁剪到有效像素中心。

## 数值策略和边界

坐标、权重和三线性累加统一使用 FP32，FP16 输入先转 FP32，输出最终转回 FP16。
NaN/Inf 遵循 IEEE 浮点传播；验证同时检查 NaN、正 Inf、负 Inf 掩码。尺寸为 1 时
reflection 坐标恒为 0。原始 case 的 grid 均在 `[-1,1]`，但 kernel 实现也支持该
区间之外的重复 reflection。

CPU 参考为 `torch.nn.functional.grid_sample`。FP16 CPU 不支持 5D grid_sample，
验证时先以 FP32 执行参考，再转回 FP16 输出。
