# rms_norm troubleshooting

## [Phase 7] gamma 初始化跨流水污染

**现象：** 首次真实 NPU case 1 的输出含异常大值和 NaN；按 `y/(x*invRms)` 反推的
gamma 在不同输入行的同一列固定一致，但与输入 gamma 完全不同。

**根因：** Init 中 gamma 的 GM→UB DMA 后缺少跨 MTE2/V 同步，且 Cast count 直接使用
GM tiling 字段；gamma Cast 在数据就绪前执行并产生污染。

**解决方案：** DMA 后执行 `PIPE_MTE2` 与 `PIPE_ALL` barrier，并将 hidden 拷贝到
device-local `int32_t count` 后再调用 Cast。

**经验：** 常驻 UB 参数在 kernel Init 中也必须显式建立 MTE2→V 依赖。

**预防：** 所有 GM→TBuf→向量计算路径都检查跨流水同步和 device-local API 参数。

## [Phase 7] Rsqrt 近似误差放大近零相对误差

**现象：** gamma 污染修复后 special mask 正确，case 1 MERE 已低于阈值，但 MARE
为 0.02969；少量近零 half 输出跨一个量化格。

**根因：** `AscendC::Rsqrt` 是近似值，其约 1e-3 量级的比例误差在近零相对误差中
被放大。float→half 的 `CAST_NONE` 已按文档执行 RINT，不是 Cast 模式问题。

**解决方案：** 对 Rsqrt 结果执行两步 FP32 Newton-Raphson 修正，再用于归一化。

**经验：** 归一化的硬件倒平方根应在严格 golden 精度下做 FP32 refinement。

**预防：** 涉及 Rsqrt 的 correctness 初版默认检查近零 MARE 并预留 Newton 修正。
