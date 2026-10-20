---
schema_version: aprof.knowledge-record/v1
id: implementation.vector-api.fallback
kind: recipe
version: 1.1.0
status: active
title: Vector / API 回退方法
scope:
  platforms:
  - all
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
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/mask_operations/SetVectorMask.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/mask_operations/SetVectorMask.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 149
  sha256: sha256:0de631e061a2e005d01aaf2efe0076a9e2adb3287edf1d1e96dd515ab919a256
  excerpt_sha256: sha256:0de631e061a2e005d01aaf2efe0076a9e2adb3287edf1d1e96dd515ab919a256
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/Vector_logical_arch/Vector_logical_arch.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/Vector_logical_arch/Vector_logical_arch.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 83
  sha256: sha256:3ea2f2b1805ea780d7a3b675bea3288878477fcb8a8fb3b94817f5cc004d91ea
  excerpt_sha256: sha256:3ea2f2b1805ea780d7a3b675bea3288878477fcb8a8fb3b94817f5cc004d91ea
learning: {}
tags: []
seed_reason: 审读五个固定开源修订中的直接来源，以中文提炼实现契约；保留旧 ID 含义，不承诺目标 SDK 编译结果或 NPU 性能收益。
parent: implementation.vector-api
references:
- implementation.precision-boundaries.bounds
- implementation.precision-boundaries.numeric
- implementation.vector-api.batch
- implementation.vector-api.cast
evidence_status: source_reviewed_not_benchmarked
---

# Vector / API 回退方法

保留 C2 已通过完整 oracle 的 Vector 实现；未知 dtype/API、mask/stride、alias、架构支持或转换舍入时，不先改代码碰运气。记录目标产品、`__NPU_ARCH__`、SDK 版本、实际 API 重载、src/dst 类型/位置、有效 count 与物理跨度，再决定是否进入 batch 或 Cast。A3/910C 不以 3510 的 RegBase/VF/SIMT 证据代替本机支持。

逐项补证：count 与 repeat 是否混用，mask 是否按较大 dtype 取 lane，repeat/block stride 是字节、元素还是 32B 块，参数位宽和空调用行为，原地 overlap 是否被文档允许，外部 mask 模式是否恢复，所有 buffer 是否持续活到最后读写完成。对于异宽 Cast，源与目标的连续 repeat stride 不同；不能只改 dtype 而沿用旧参数。mask 只约束向量计算，不保护先前 GM 搬运。

成本先按有效元素 N 与各路字节宽度计算，分别记录真实 UB 地址跨度、所有槽与 tmp 的峰值容量，再比较发射次数；不能通过丢弃尾元素、缩小 dtype、修改 RoundMode 或移除事件使时间变短。若瓶颈证据指向 GM、bank 或 Scalar 等待，选择相应分支，不强行 batch。

失败验证保留原 oracle 全 case，包括零/短/尾 count、repeat 上限附近、stride、别名、极值/NaN/Inf/有符号零。正确性失败先定位第一处坏元素/中间结果，挂起/越界先保留 runtime/crash 日志；不能以性能结果覆盖正确性失败，不能静默换算法继续计时。回到原正确路径，记录排除条件和缺项；越过 C2 的所有权、容量、精度或实现自由度时请求重规划。C3 记录条目 ID/版本、实际参数与未验证范围。

来源事实为固定 Cast、高维切分、mask 与 Vector 架构文档；上述补证顺序是工程提炼。默认回退不引入新的目标 API，也不承诺速度；本条没有上板收益数据。
