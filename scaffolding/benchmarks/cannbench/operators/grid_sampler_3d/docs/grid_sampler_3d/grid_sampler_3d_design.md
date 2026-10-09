# grid_sampler_3d 设计

## 计算与切分

输出按 `[N,C,Do,Ho,Wo]` 连续线性展开。每个 vector core 获得一个连续区间，
区间长度向上对齐到 64B：FP16 为 32 元素，FP32 为 16 元素。这样不同 core 不会
标量写入同一 cache line。每个输出独立读取三项 grid 坐标和最多八个输入体素。

线性索引解码：

```text
spatial = linear % (Do*Ho*Wo)
nc      = linear / (Do*Ho*Wo)
c       = nc % C
n       = nc / C
grid    = (n*(Do*Ho*Wo)+spatial)*3
x_base  = (n*C+c)*(D*H*W)
```

该 correctness-first 版本有意不做 grid 的通道复用或 UB 向量化，避免引入布局转换
和尾块问题。代价是相同空间点会被每个 channel 重复读取 grid；当前需求明确优先
保证 20 个 case 精度正确。

## 缓冲区与数据路径

FP32 路径直接做只读 GM 标量加载和连续 GM 标量写回。dav-2201 上 2B GM 标量
写不可靠，因此 FP16 路径用 1024 元素 tile：标量计算结果先写 FP32 UB，经向量
Cast 转成 half UB，再以 `DataCopyPad` 精确字节数写回 GM。因此：

- FP32 `liveBytesPerElem`（UB）为 0；FP16 为 6B（4B FP32 + 2B half）；
- FP16 尾 tile 使用精确 `blockLen=count*sizeof(half)` 的 `DataCopyPad`；两个 buffer
  均无 UB-to-UB copy，`InitBuffer` 与 `Get` 生命周期一致；
- host 负责完整输入 H2D、输出 D2H 和 tiling H2D；
- FP16 GM 读取用 IEEE-754 软件 half 解码，输出转换使用 UB `AscendC::Cast`。

## 精度与验证

FP32 阈值为 `2^-13`，FP16 为 `2^-10`；要求 MERE 小于阈值、MARE 小于十倍阈值，
且特殊值掩码完全一致。相对误差在零附近病态，因此根据真实 NPU 对照结果采用混合
容差：FP16 采用插值算子常见固定绝对地板 `2^-9`（约 `0.001953`）；FP32 不超过
`max(2e-6, 4*eps_fp32*max_abs_input)` 时，该点相对误差记零。FP32 地板随输入量级
缩放，可覆盖三线性八项累加的运算序舍入，又不会掩盖小值域错误；更大的误差仍严格
进入 MERE/MARE。验证逐 batch调用
PyTorch golden，避免最大 case 同时构造
全量 golden。host 用同步 kernel launch 的 wall-clock 微秒数记录 `kernel_us`，仅作
当前基线数据，不进行 profiling 或优化。
