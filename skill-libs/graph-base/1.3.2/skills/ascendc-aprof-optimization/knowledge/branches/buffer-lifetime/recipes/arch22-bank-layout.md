---
schema_version: aprof.knowledge-record/v1
id: implementation.buffer-lifetime.arch22-bank-layout
kind: recipe
version: 1.0.0
status: active
title: arch22 UB bank 地址、padding 与 repeat 联合布局
scope:
  platforms:
  - dav-2201
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/04_memory_access/bank_conflict_ub/README.md
  original_path: examples/01_simd_cpp_api/05_best_practices/04_memory_access/bank_conflict_ub/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 7
  - 207
  sha256: sha256:2e26c33689d8ffdc94543961c8ac2e3d118c24b2c03bfa18bbc7455bfac85490
  excerpt_sha256: sha256:e776bac807cddc244dae13ef3a6c90043caa38b09f0af8adb8908770f04eccb2
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/04_memory_access/bank_conflict_ub/bank_conflict_ub.asc
  original_path: examples/01_simd_cpp_api/05_best_practices/04_memory_access/bank_conflict_ub/bank_conflict_ub.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 29
  - 104
  sha256: sha256:de73d61fa8836689a9f86df41ed1ed1c44903e98be7bb7cbe9c7bb816d29c81b
  excerpt_sha256: sha256:6e2c96f3993d3ee2f8e315af28835914c9a379bc2e95b48a9ee533d1cfd3f3a5
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/04_memory_access/bank_conflict_ub/config.h
  original_path: examples/01_simd_cpp_api/05_best_practices/04_memory_access/bank_conflict_ub/config.h
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 72
  sha256: sha256:87c457b04c578b421ba9c096aaba2853be7a6d41b0fffeb31625c901f7c488c2
  excerpt_sha256: sha256:87c457b04c578b421ba9c096aaba2853be7a6d41b0fffeb31625c901f7c488c2
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/arch22/ub_bank_conflict.md
  original_path: ops/ascendc-performance-best-practices/references/common/arch22/ub_bank_conflict.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 117
  sha256: sha256:11c277b4ec0a5470a8b3ad2b6ed5564773e2ccc18e08a0ac07d9d625f44ef388
  excerpt_sha256: sha256:11c277b4ec0a5470a8b3ad2b6ed5564773e2ccc18e08a0ac07d9d625f44ef388
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/00_vector_compute/add_high_performance/add.asc
  original_path: examples/01_simd_cpp_api/05_best_practices/00_vector_compute/add_high_performance/add.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 27
  - 345
  sha256: sha256:f7d075958365a8fc1af9879e90ab6494573f8869d3a538832c537d8e0f905042
  excerpt_sha256: sha256:d2b85d269202c81ba81366f010df36bf3c512f17f84bd0b145c0dd1425e49cda
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/00_vector_compute/add_high_performance/README.md
  original_path: examples/01_simd_cpp_api/05_best_practices/00_vector_compute/add_high_performance/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 357
  - 485
  sha256: sha256:b5b6a86283fe52b79c7990bb8ccf5072ead5a50fbd46ae5aaa7a3e056aab1580
  excerpt_sha256: sha256:5c6d2994aaf79df1876377bb814db5f8bee465813e3dbac2fbe8cf3ad7a959cc
learning: {}
tags:
- ub-bank
- arch22
- address-layout
- repeat-stride
seed_reason: 审读固定开源修订并提炼中文实现配方，保留既有 ID 语义；API 单位以实际 API 文档为准；未做目标 SDK 编译或 NPU 性能验证。
parent: implementation.buffer-lifetime
references:
- implementation.buffer-lifetime.reuse
- implementation.buffer-lifetime.fallback
evidence_status: source_reviewed_not_benchmarked
---

# arch22 上按实际地址和 repeat 模式调整 UB bank 布局

## 适用域与原理

适用于来源明确标为 Atlas A2/A3、DAV_2201/arch22 的 SIMD/Vector UB 路径，且计算阶段存在可复现的 bank 冲突候选。并发读请求落在同一 bank group、读写落在同一 bank，可能导致仲裁串行化；仅仅把三块首地址排成不同数值，不能证明没有冲突。C2 必须允许 UB 地址/padding 变化，数学地址关系和合法 alias 保持不变。本文不覆盖 3510 VF、SIMT、ND2NZ 或不同平台 bank 结构。

来源样例给出此结构：UB物理192KiB，16个bank group，每组3个bank，每bank128行、每行32B。实际 kernel 可用容量须由目标平台/API/workspace预算给出，不能把物理192KiB全部默认占满。对来源18位字节地址 `A`：

```text
byteInRow = A & 31
group = (A >> 5) & 15
row = (A >> 9) & 127
bankId = (A >> 16) & 3      // 来源合法bankId是0、1、2
bankNumber = group + 16 * bankId
```

这是样例的地址编码，而不是“每32B对48个bank循环”的泛化公式。常见笔记中的简化轮询模型只能提出候选，不能替代这里的实际位域。对目标910C应先证明当前SoC/SDK采用此A3/arch22布局，未知则退回普通合法对齐布局。

## 逐 repeat 分析后再改地址

1. 从真实编译后/运行期 UB 物理地址出发，列 src0、src1、dst 的每个 DataBlock 地址。高阶API可能生成不同的指令序列，不能只分析源码表面参数。
2. 来源 float Add 的 full mask=64元素，即每repeat256B，连续模式为每操作数8个32B块、block stride=1、repeat stride=8（这些stride为DataBlock数）。对每repeat全部块解码，不仅看首址。
3. 同repeat两读源尽量错开group；写源还需结合跨repeat硬件写回延迟和真实读写顺序。来源scenario4中首址同bank却被硬件错开，scenario5偏移32B反而冲突，说明“随手加32B”并非安全优化规则。
4. 只改变padding或受控arena偏移，重算后续地址、tile容量、queue的ping/pong位置和所有同时存活区间。先排除物理重叠，再看冲突；bank错开不能给非法alias以资格。

## 来源限定的可复现地址例

下面取自 `bank_conflict_ub` scenario1，仅用于核验该float Add、连续stride和长度。`4096` 是来源的元素数，字节数为16384；地址是UB字节偏移。已由本kernel独占预留 `[0,147456)` 的arena，禁止与TPipe其他分配重叠；输入值在调用Add前已完成写入，各个GM搬运/写回保留原有合法完成边。

```cpp
constexpr uint32_t n = 4096; // float元素；本例固定，不是通用tile
constexpr uint32_t bytes = n * sizeof(float); // 16384B
constexpr uint32_t xByte = 0x00000, yByte = 0x10100, zByte = 0x20000;
AscendC::LocalTensor<float> x(AscendC::TPosition::VECCALC, xByte, n);
AscendC::LocalTensor<float> y(AscendC::TPosition::VECCALC, yByte, n);
AscendC::LocalTensor<float> z(AscendC::TPosition::VECCALC, zByte, n);
constexpr uint64_t mask = 64; // float元素/repeat = 256B
constexpr uint8_t repeats = n / 64; // 64次，每段32B stride见参数
AscendC::Add(z, x, y, mask, repeats, {1, 1, 1, 8, 8, 8});
```

首个repeat的x读group0…7，y读group8…15，z写group0…7且bankId=2，与读源bankId=0/1不同；其后repeat必须继续检查。三个有效区间互不相交：x `[0,16384)`、y `[65792,82176)`、z `[131072,147456)`。有效数据仅49152B，arena高水位147456B，不能把49152B当布局容量。对不同tile、dtype、mask和stride，应重新推导，不能照搬这些地址。

Add高性能样例另有half双缓冲变体：arch22侧将实际tile从16384元素缩至16256元素，使相关输入首址差从32768B变为32512B（相差256B），并重新布置ping/pong和输出。它展示“减少少量tile换布局”的真实候选；不能只复制16256而不复制其物理间隔/容量/最后消费者约束，也不能迁入该文件3510分支的不同常量。

## 成本、验证与回退

padding代价是新增高水位和可能降低的tile，额外调用量约为 `ceil(N/Tnew)-ceil(N/Told)`；冲突收益必须大于这些循环/搬运与同步成本。共享arena的活跃重叠要逐时刻查证；queue自动分配时，记录实际地址而不是推定InitBuffer调用一定紧邻。只有代码说明了自定义地址预留方式，才允许直接构造上述物理视图。

保持同输入、同数学count、同同步，比较完整正确性、Vector时间、Task及资源冲突计数；覆盖尾mask、不同长度和多tile，而不只重复1000次Add的微基准。来源cycle数只属于来源测试。若Conflict下降而Task劣化，恢复原tile/布局；目标映射不明或arena容量不足，使用`implementation.buffer-lifetime.fallback`，不要通过删除槽或非法重叠凑容量。

来源事实：bank_conflict_ub README/config/kernel给出位域、具体地址和八个场景；Add样例给出不同架构分支与half布局。地址推导、arena预算及推广步骤为提炼。来源自己的读写冲突概述必须结合其scenario4/5细节解释，本文没有把简化规则写成所有指令的定律；未做目标硬件验证。
