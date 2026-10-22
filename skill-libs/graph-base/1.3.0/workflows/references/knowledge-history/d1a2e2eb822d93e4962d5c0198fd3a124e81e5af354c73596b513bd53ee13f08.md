---
schema_version: aprof.knowledge-record/v1
id: implementation.vector-api.batch
kind: recipe
version: 1.1.0
status: active
title: Repeat / mask / stride 与批量 Vector API
scope:
  platforms:
  - Ascend 910B
  - Ascend 910C
  - Ascend 950
  - dav-2201
  - dav-3510
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/SIMD_compute/high_dim_split.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/SIMD_compute/high_dim_split.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 84
  sha256: sha256:ac8379ef50685c20af258928e6805097ddf1cedbfacf2adb1fca65fc6d8bf915
  excerpt_sha256: sha256:ac8379ef50685c20af258928e6805097ddf1cedbfacf2adb1fca65fc6d8bf915
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/basic_arithmetic/Add.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/basic_arithmetic/Add.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 190
  sha256: sha256:d0fe0a42a4720850442a3745e2ac9551654a1fd26c3debecd42f8755d0af461b
  excerpt_sha256: sha256:d0fe0a42a4720850442a3745e2ac9551654a1fd26c3debecd42f8755d0af461b
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/mask_operations/SetVectorMask.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/mask_operations/SetVectorMask.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 149
  sha256: sha256:0de631e061a2e005d01aaf2efe0076a9e2adb3287edf1d1e96dd515ab919a256
  excerpt_sha256: sha256:0de631e061a2e005d01aaf2efe0076a9e2adb3287edf1d1e96dd515ab919a256
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/type_conversion/Cast.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/type_conversion/Cast.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 643
  sha256: sha256:a41d8e8b10d541452de9c4542158d0bba6bc53f15e68c3d1d929712856a11f12
  excerpt_sha256: sha256:a41d8e8b10d541452de9c4542158d0bba6bc53f15e68c3d1d929712856a11f12
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/elementwise/vector_efficiency_design.md
  original_path: ops/ascendc-performance-best-practices/references/elementwise/vector_efficiency_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 211
  sha256: sha256:103bb67af7b9bc8316403167dbfd6e57da2a757dd0bfbc8af03336378051b13e
  excerpt_sha256: sha256:103bb67af7b9bc8316403167dbfd6e57da2a757dd0bfbc8af03336378051b13e
learning: {}
tags:
- count-overload
- mask
- repeat
- stride
seed_reason: 审读五个固定开源修订中的直接来源，以中文提炼实现契约；保留旧 ID 含义，不承诺目标 SDK 编译结果或 NPU 性能收益。
parent: implementation.vector-api
references:
- implementation.buffer-lifetime.reuse
- implementation.precision-boundaries.bounds
- implementation.vector-api.cast
evidence_status: source_reviewed_not_benchmarked
---

# Repeat、mask、stride 与批量 Vector API

## 原理与条件

对同一计算、规则地址和相同有效 lane 的短调用，count 或高维 repeat 重载可减少 Scalar 参数计算与 API 发射。先确定是 API 发射/地址控制热点；如果瓶颈是 GM 搬运、数据依赖或 UB bank conflict，仅增加 repeat 不一定缩短 Task 时间。C2 需允许该局部实现，算法、算术操作顺序、跨核所有权和同步不变；归约重排、跨算子融合与改累加精度不属于本条。

普通 memory vector API 的一 repeat 处理 8 个 32B DataBlock，共 256B；FP16 为 128 元素、FP32 为 64 元素。具体 API/混合 dtype 以支持文档为准。固定高维 API 文档的 repeatTime 上限为 255，不能将任意长 tensor 强塞进 uint8_t 发生截断。count 重载的参数是有效元素数，由 API 合法处理前 n 个数据，受 UB/具体类型范围约束；它与 repeat 重载不是同一单位。

## 落地步骤和地址闭合

1. 先选最简单合法重载：连续区域优先 count；有规则间隔且同类调用很多时再选高维 mask/repeat/stride。分别列 src/dst 的元素类型、基址、逻辑 shape、块内与 repeat 间跨度。
2. 普通等宽 dtype 设 `s=sizeof(T)`、`E=256/s`、`B=32/s`。`mask` 在一次 repeat 内选择有效 lane；`blockStride` 连接同一 repeat 的不同 32B 块，`repeatStride` 连接相邻 repeat 的同位置块，均以 32B 块计。dst block stride 不可为 0；src stride 0 是广播复用，必须证明符合原语义。
3. 对 r 次 repeat、块 stride b、repeat stride p，最坏地址范围为 `(r−1)×p×32 + (已选最后块索引)×b×32 + 该块有效字节`，每个操作数独立算，并核验参数位宽和 UB 容量。不能只用 `r×mask` 检查非连续 buffer，不能把 Vector mask 当 GM 访问保护。
4. 主块按最多合法 repeat 分组，组间按实际地址跨度推进；尾部有效 lane 不同就单独处理。若外部设置 mask 或 counter，明确模式、mask 值和恢复位置，在下一段 API 前恢复其要求的正常状态；没有接口级证据时保留每次内部 mask 设置。
5. 检查原地 alias：后一个 repeat 的源不得被前一个 repeat 提前覆写，除非具体 API 明确允许。较大 batch 延长 buffer 读写时间，原 queue/event 的完成边必须覆盖整个批量，释放不能只等“第一小段完成”。

设原有 `k` 次小调用，合并后 `ceil(fullRepeats/Rmax)` 次主调用加至多一条 tail，减少的是发射/控制；有效算术与源/目标访问集合应保持不变。UB 需求为各实际跨度而非有用元素简单相加，另计队列槽、padding 和 API tmp。吞吐提升与否看同协议 Task 时间，不能把调用数下降直接报告为加速比。

## 可读且明确的片段

示例为三个独立 float UB tensor：`xLocal/yLocal/zLocal` 均有 `validElements` 个有效连续元素、32B 对齐且互不重叠；原 MTE2→Vector 和 Vector→消费者事件仍保留。`validElements` 是 `uint32_t` 元素数，已由 Host 证明合法；选择 count 方式时：

```cpp
if (validElements != 0) {
    AscendC::Add(zLocal, xLocal, yLocal, validElements);
}
```

选择高维方式且本批次恰有 512 个 float 元素时，可用 `mask=64, repeatTime=8, {1,1,1,8,8,8}`；各路 block stride 1、repeat stride 8 的单位均为 32B 块。对于 513 个元素，不能设 mask=65；须在合法主调用后用独立有效 count=1 的尾部（或合法 count 重载），同时保持尾地址与 buffer 范围。Cast 等异宽 API 的 mask 与 repeat stride 要按较大 dtype 另算，不能沿用 Add 的参数。

## 平台、数值与验证

固定 cannbot vector 文档明确 arch35/3510 的 RegBase、Reg/MicroAPI/VF 内容专属；其收益百分比、32 RegTensor 预算或展开建议不当作 A2/A3 判据。这里的 A2/A3 memory vector count/repeat 依据 asc-devkit API；950 的兼容实现需独立核验支持和零 count 行为。跨平台显式跳过空调用更容易保持语义，不将 3510 SIMT/VF 片段放入 A3 kernel。

普通逐元素 batch 应保持每元素运算和 RoundMode；reduction/scan、随机数或跨 repeat 依赖要单独证明顺序，不进入本条直接合并。测试 count=0/1、每 repeat±1、255 repeat±1、不同 dtype/stride、mask 全开/局部与 bit 模式、alias 合法/不合法，并在 buffer 周围放可检查哨兵。部分 lane 错、每 repeat 周期性错位、后续 API 全错多为 mask/stride/恢复错误；撤回至 count 或原小调用，保留失败日志。来源事实是固定高维 API、Add 与 mask 的单位/状态契约，地址闭合公式与合并步骤为工程提炼；未进行目标 SDK/NPU 验证。
