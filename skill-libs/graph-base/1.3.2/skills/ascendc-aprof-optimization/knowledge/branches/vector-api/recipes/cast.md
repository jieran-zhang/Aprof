---
schema_version: aprof.knowledge-record/v1
id: implementation.vector-api.cast
kind: recipe
version: 1.0.0
status: active
title: Cast 转换链合并与舍入边界保持
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
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/type_conversion/Cast.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/type_conversion/Cast.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 643
  sha256: sha256:a41d8e8b10d541452de9c4542158d0bba6bc53f15e68c3d1d929712856a11f12
  excerpt_sha256: sha256:a41d8e8b10d541452de9c4542158d0bba6bc53f15e68c3d1d929712856a11f12
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/SIMD_compute/high_dim_split.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/SIMD_compute/high_dim_split.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 84
  sha256: sha256:ac8379ef50685c20af258928e6805097ddf1cedbfacf2adb1fca65fc6d8bf915
  excerpt_sha256: sha256:ac8379ef50685c20af258928e6805097ddf1cedbfacf2adb1fca65fc6d8bf915
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/Vector_logical_arch/Vector_logical_arch.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/Vector_logical_arch/Vector_logical_arch.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 83
  sha256: sha256:3ea2f2b1805ea780d7a3b675bea3288878477fcb8a8fb3b94817f5cc004d91ea
  excerpt_sha256: sha256:3ea2f2b1805ea780d7a3b675bea3288878477fcb8a8fb3b94817f5cc004d91ea
learning: {}
tags:
- cast
- mixed-width
- rounding
- ub-lifetime
seed_reason: 审读五个固定开源修订中的直接来源，以中文提炼实现契约；保留旧 ID 含义，不承诺目标 SDK 编译结果或 NPU 性能收益。
parent: implementation.vector-api
references:
- implementation.buffer-lifetime.reuse
- implementation.precision-boundaries.bounds
- implementation.precision-boundaries.numeric
- implementation.vector-api.batch
evidence_status: source_reviewed_not_benchmarked
---

# Cast 转换链合并与舍入边界保持

## 原理与适用条件

Cast 在 UB 中读入一种 dtype、写出另一种 dtype，除了发射与读写成本，还引入可见的舍入、饱和和特殊值行为。优化目标是合并重复的同语义转换，或让同一转换结果被多个消费者复用；不是消除算法要求的中间舍入。本条只适用于 C2 允许的转换实现自由度，不改变输入/输出、累加 dtype 或量化算法。

先画出实际链 `源 dtype → 中间 dtype → 目标 dtype`，在每条边标注 RoundMode、有效 count、scale、饱和模式、下游使用者与最后使用点。可以考虑：一个输入被重复以同一模式转换后分别消费，计算一次并保持结果到最后消费者完成；或已证明值域内完全精确的往返。`float→half→float` 通常不能删，半精度舍入已改变值；即便源目标同为 float，`CAST_RINT` 等仍可表示数值取整，不能用“同 dtype”判冗余。

## 实施步骤与 API 单位

1. 以目标产品对应的 Cast 支持表核对 `(src,dst,RoundMode)` 三元组。支持某类型不等于支持所有模式，`CAST_NONE` 在有精度损失时按 RINT 解释，不代表无条件截断；RINT 为 ties-to-even，ROUND 与 TRUNC/FLOOR/CEIL 各自不同。低位整数截取、量化 scale 和特殊浮点路径单独核验。
2. 选正确重载：`count` 是有效元素数，容量按实际源/目标字节算；高维重载 `mask` 按两 dtype 中较大字节宽度定义 lane 数，repeat 与 stride 用对应数据块单位。不能把 count 数值塞入 mask 当整个 tensor 长度。
3. 不同位宽的连续转换，令 `s=max(sizeof(src),sizeof(dst))`、一 repeat 的有效元素 `E=256/s`。每路连续 repeat 跨度为 `E*sizeof(该路dtype)/32` 个 32B DataBlock。只在这套普通固定字节 dtype 模式下使用公式；int4 pack 等必须用其独立限制。
4. 合并后为转换结果保留完整存活期，不能在另一个消费者尚未读完前复用其 UB。输入输出分离最易证明；特别是窄类型扩宽时，部分原地重叠可能覆盖尚未读到的输入。仅使用具体 API 明确允许的 overlap，不用“memmove 式前后遍历”猜测硬件行为。
5. 混合宽度、非连续 stride 或不支持直接转换时保留合法中间 dtype 路径，按原边分别设置舍入。不要添加无来源的新近似、多项式或“误差更小”的替代算法。

设有效元素 N、源中间目标每元素字节 a/b/c，一条两段转换的逻辑 UB 流量约 `N×(a+2b+c)`，直接转换约 `N×(a+c)`；只有转换数学等价且 API 支持时才可能省 `2Nb` 字节。复用一个转换结果可减少重复工作，但使 `AlignUp(Nb,32)` 字节中间 buffer 活到最后消费者，需连同原输入、输出、队列槽、API tmp 计算峰值 UB。增加活跃 buffer、缩小 tile 或丢失双缓冲可能抵消收益。

## 有上下文的混合宽度片段

示例固定为 half→int32、CEIL 向正无穷取整。`srcLocal` 与 `dstLocal` 是已分配且不重叠的 32B 对齐 UB tensor，各至少 512 元素；源含有限可转换值，工程已有 producer→Cast 以及 Cast→consumer 的同步。下例只展示计算，源字节数 1024B、目的 2048B。

```cpp
const uint64_t mask = 256 / sizeof(int32_t); // 64 个逻辑元素/repeat
const uint8_t repeats = 8;                  // 512 个元素，总量合法
AscendC::Cast(dstLocal, srcLocal, AscendC::RoundMode::CAST_CEIL,
              mask, repeats, {1, 1, 8, 4});
// dst/src block stride 均为 1 个 32B 块。
// dst repeat stride=8 个块(256B)，src=4 个块(128B)。
```

同一连续转换也可使用 `AscendC::Cast(dstLocal,srcLocal,RoundMode::CAST_CEIL,512)` 的 count 重载，避免手工 repeat；两者必须用相同有效元素和舍入才能比较。int4 的 count/连续 mask 必须为偶数，bit mask 的同字节两 bit 一致，并按半字节 pack 容量分配；不把本例步长套用 int4。

## 精度、失败与平台 guard

验证恰在舍入中点及相邻浮点数、正负非整数、整数目标上下界、大/小有限值、次正规数、±0、NaN/Inf；具体超界和特殊值输出以原 oracle 与目标 API 为准，不凭主机 C++ cast 推断。源值域受限时写出可证明界，而不是只凭随机样本删转换。逐级核对第一个变化的中间结果，既检查误差标准，也检查 mask 外区域未被写坏。

A2/A3 的 count/repeat=0 在本固定文档中为 NOP；3510 兼容层经 VF 实现，不保证零参数 NOP，跨代代码应在调用前显式跳过空转换。Reg Cast、fp8/hifloat/complex/double 支持不能从 3510 表迁移到 A3；本条示例仅 memory vector Cast，适用 910B/910C，950 使用其兼容接口时另按 3510 文档编译。错位每 64 元素重复、尾部污染、只在某 RoundMode 错、扩大转换后随机错是典型撤回信号；回退原 Cast 链，不改 tolerance。来源事实为固定 Cast API 的模式、混合宽度和 overlap 约束；流量/生命周期模型及合并判据为工程提炼，未上板测量。
