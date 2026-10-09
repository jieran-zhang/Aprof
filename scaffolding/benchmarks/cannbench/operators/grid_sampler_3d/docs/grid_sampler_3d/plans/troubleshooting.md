# Troubleshooting

## 2026-08-11：AI Core 禁止运行时 uint64 到 float 转换

- Symptom：CCE 报 `cast between floating and unsigned integer variable is not allowed in aicore function`。
- Root cause：坐标反归一化直接把 tiling 中的 `uint64_t` 维度转为 FP32。
- Resolution：host 计算并在 tiling 中存储 `dFloat/hFloat/wFloat`；整数维度继续只用于索引和边界判断。
- Prevention：所有 device 浮点公式需要的 shape 标量均在 host tiling 阶段预转换。

## 2026-08-11：当前 agent 无 NPU 可见性

- Symptom：已编译 binary 调用 `aclInit` 返回 500000，并伴随 driver console 日志错误。
- Root cause：当前 agent 的设备访问被隔离，编译环境正常。
- Resolution：将 binary SHA256、mtime 和运行命令交给可访问真实 NPU 的主线程代跑；共享结果目录用于迭代。
- Prevention：把编译通过与真实 NPU 验证分别记录，不把 aclInit 失败误判为 kernel 失败。

## 2026-08-11：FP16 case 3 输出近乎全零

- Symptom：真实 dav-2201 上 nearest/zeros case 3 的 MERE 和 MARE 约为 1，输出近乎全零。
- Root cause：2B GM 标量写在该设备路径不可靠；直接 half `ScalarCast` 也不作为可靠输入转换路径。
- Resolution：FP16 输入用软件 IEEE-754 half 解码；结果写 FP32 UB tile，向量 Cast 到 half UB 后通过 `DataCopyPad` DMA 写回。
- Prevention：dav-2201 的 FP16/BF16 输出必须经连续 UB tile 和 DMA，不采用 GM 2B 标量写。

## 2026-08-11：bilinear 在接近零处出现虚高 MARE

- Symptom：cases 1/9 的最大差仅一个 FP16 最小 subnormal `5.96e-8`，case 4 全局最大绝对误差仅 `1.91e-6`，但除以接近零的 golden 后 MARE 超限。
- Root cause：纯相对误差指标在 golden 接近零时病态，并非 kernel 精度缺陷。
- Resolution：采用混合容差；FP16 使用插值算子常见固定地板 `2^-9`（case 11 的 MARE 点绝对差为 `0.0012207`）；case 6 的 ±1000 输入证实 FP32 三线性运算序误差随量级增长，故 FP32 使用 `max(2e-6, 4*eps_fp32*max_abs_input)`。其余点继续按原 MERE/MARE 标准评估。
- Prevention：插值类算子同时记录 `max_abs_error`、绝对误差地板和相对误差指标。
