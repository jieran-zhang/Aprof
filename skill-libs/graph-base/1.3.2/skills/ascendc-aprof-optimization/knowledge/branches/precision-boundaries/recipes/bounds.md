---
schema_version: aprof.knowledge-record/v1
id: implementation.precision-boundaries.bounds
kind: recipe
version: 1.1.0
status: active
title: Padding、容量和地址边界约束
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 151
  sha256: sha256:a41ac2ff57f181c342d823a1b453bfabfb20c56bf840e31f4dff7232cefdc80a
  excerpt_sha256: sha256:a41ac2ff57f181c342d823a1b453bfabfb20c56bf840e31f4dff7232cefdc80a
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/data_structures/LocalTensor/LocalTensor_constructor.md
  original_path: docs/zh/api/SIMD-API/basic_api/data_structures/LocalTensor/LocalTensor_constructor.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 296
  sha256: sha256:103ec2d4324f59620a49df8b4ddaec36c81552c1a5a850233177ecec77a34946
  excerpt_sha256: sha256:103ec2d4324f59620a49df8b4ddaec36c81552c1a5a850233177ecec77a34946
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/type_conversion/Cast.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/type_conversion/Cast.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 643
  sha256: sha256:a41d8e8b10d541452de9c4542158d0bba6bc53f15e68c3d1d929712856a11f12
  excerpt_sha256: sha256:a41d8e8b10d541452de9c4542158d0bba6bc53f15e68c3d1d929712856a11f12
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute/Mmad.md
  original_path: docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute/Mmad.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 349
  sha256: sha256:1ebb798bb29605a5cbabb2b52964032fff2e5a3b0c02b9ba7556b05f573e062a
  excerpt_sha256: sha256:1ebb798bb29605a5cbabb2b52964032fff2e5a3b0c02b9ba7556b05f573e062a
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/cube_compute_store/Fixpipe_L0CToGM.md
  original_path: docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/cube_compute_store/Fixpipe_L0CToGM.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 327
  sha256: sha256:1f55a31fe89adbed8b4eca9e8eb8c8ef8b2e6668d8a3fe35b23401e50ddacf35
  excerpt_sha256: sha256:1f55a31fe89adbed8b4eca9e8eb8c8ef8b2e6668d8a3fe35b23401e50ddacf35
learning: {}
tags:
- bounds
- capacity-liveness
- overflow
- padding
seed_reason: 审读五个固定开源修订中的直接来源，以中文提炼实现契约；保留旧 ID 含义，不承诺目标 SDK 编译结果或 NPU 性能收益。
parent: implementation.precision-boundaries
references:
- implementation.buffer-lifetime.reuse
- implementation.cube-api.fixpipe_output
- implementation.precision-boundaries.numeric
- implementation.vector-api.batch
evidence_status: source_reviewed_not_benchmarked
---

# Padding、容量、生命周期与地址边界约束

## 原理与适用条件

任何动态尾、padding、workspace、静态 offset、dtype 或 batch 大小变化，都必须重新证明“物理容量够、有效数据正确、地址在界内、同时存活不冲突”。逻辑 count 不等于物理步长，Vector mask 不保护 GM 搬运，API NOP 也不清零输出。C2 的所有权、容量与允许变换仍是硬边界；发生挂起/异常先进入 debug，不在错误运行上比较性能。

先为每个 tensor 列 `(物理存储位置, dtype, 起始字节, 有效shape, 物理stride, 对齐, producer, 最后consumer, 完成边)`。同一 base 上的 ReinterpretCast 共享物理字节，不能算作新独立存储；独立分配的 buffer 即便数学内容相同也各占容量。静态 LocalTensor 只在所有 dtype/layout/feature 的布局已覆盖时使用，不把某一个 feature 的不重叠推广到全部路径。

## 逐层闭合步骤

1. Host 先检查加乘和对齐溢出，再把结果写入 API/tiling 的实际位宽字段。对有效元素 `N`、字节 `s`、对齐 `a`，先验 `s>0,a>0,N≤MAX/s`；计算 `raw=N×s` 后还需 `raw≤MAX−(a−1)` 才可用向上对齐公式。字段转换前再验 API 上限；uint64 检查通过不代表 uint16 stride 可装下。
2. GM 访问使用原分配范围和真实物理 stride，末行/末页不能向上补读。非对齐输入用有目标支持的 DataCopyPad 有效字节参数或原合法尾路径；padding 在 UB/L1 内产生不意味着 GM 也有补齐空间。非连续 tensor 每一行/每个 page 分别核验。
3. UB 的行偏移按物理对齐长度，计算有效 count 按原长度。多行 `rowOffset=row×alignedCols`、reduction 的 count 为 validCols；用 alignedCols 当有效计数会让 padding 混入结果。
4. 为 padding 填对应算法中性值：普通 sum 常用0、max 常用负无穷，但量化有零点、乘法和统计状态不同；Welford 的 padding 不参与 count。全 mask/空归约的结果仍由 oracle 分支决定，不能靠“中性值自然算出来”替代。
5. 每种物理存储分别做峰值预算：`Peak_mem=max_t(sum(bytes(buffer), buffer在t仍存活))`，包含所有 queue 槽、双缓冲、dtype 扩宽、padding、API tmp、bias/scale 和 workspace。对静态重叠复用，前一 buffer 最后读写完成早于后一写入才可共享；不只按 C++ 对象作用域判断。
6. 重算所有输出矩形的地址集合与互斥性。tail 以有效长裁剪，不能为了32B/16列对齐扩大用户输出写范围；Fixpipe 对目的重叠写可能不报警且顺序不保证，不能依靠“最后写回者”实现未计划归约。

## 可执行的 Host 对齐检查

下例仅使用标准无符号整数运算；`validElements` 为有效元素数，`elementBytes` 为正 dtype 字节数，`alignBytes` 为任意正对齐字节，`availableBytes` 是本 buffer 可用字节上限，`alignedBytes` 输出物理分配大小。函数失败时必须选原合法方案或报告容量不足，不能截断 N。N=0 合法得到0，但后续 API 是否允许零调用另行检查。

```cpp
#include <cstdint>
#include <limits>
bool CheckedAlignedBytes(uint64_t validElements, uint64_t elementBytes,
                         uint64_t alignBytes, uint64_t availableBytes,
                         uint64_t& alignedBytes) {
    const uint64_t limit = std::numeric_limits<uint64_t>::max();
    if (elementBytes == 0 || alignBytes == 0) return false;
    if (validElements > limit / elementBytes) return false;
    const uint64_t raw = validElements * elementBytes;
    const uint64_t remainder = raw % alignBytes;
    const uint64_t padding = remainder == 0 ? 0 : alignBytes - remainder;
    if (raw > limit - padding) return false;
    alignedBytes = raw + padding;
    return alignedBytes <= availableBytes;
}
```

使用余数计算避免 `raw+a−1` 自身先溢出；它只证明一个 buffer 字节数，后续仍要检查偏移 `base+bytes`、多行 stride 和同位置峰值总额。对于 `[rows,cols]` 的行稀疏范围，最后有效元素偏移是 `(rows−1)×rowStrideElements+(cols−1)`，仅在 rows/cols 非零时计算，并逐项检查乘加；零维走原空输入分支，避免 `rows−1` 下溢。

## 数值、测试与平台边界

覆盖容量上限前后、最大字段/地址、有效长度0/1、32B与每 repeat±1、非整除 tile、奇数列、多行 stride、GM 保护页、padding 污染和同步压力。检查哨兵区、最后访问地址、每输出只写一次、不同分支实际峰值。ADDR_MISALIGN、随机错、只在 feature/dtype 切换时错、尾核覆盖其他核都是失败；保留日志回到 C2 fallback，不能减小合法输入或降低精度以过容量。

来源事实：AR 全载文档区分 rLengthAlign 的 buffer/偏移和 rLength 的 count；LocalTensor 构造说明起址与字节范围、size 的元素单位；Cast/Mmad/Fixpipe 提供不同对齐、mask、NOP 与输出约束。峰值存活模型、溢出检查函数和验证步骤是工程提炼。条目契约适用 all；192KB UB、具体 32B/512B/1024B 对齐、参数字段上限和 zero-count 行为来自相应 dav-2201/dav-3510 API，不是所有芯片/SDK通用容量。目标产品能力以实际平台查询、SDK文档和编译为准，未上板验证。
