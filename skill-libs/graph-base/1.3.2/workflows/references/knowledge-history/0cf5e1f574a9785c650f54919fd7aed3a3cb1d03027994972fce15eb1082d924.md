---
schema_version: aprof.knowledge-record/v1
id: implementation.memory-transfer.strided-pad
kind: recipe
version: 1.0.0
status: active
title: 规则跨行 DataCopyPad 与双端 stride 单位
scope:
  platforms:
  - dav-2201
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/data_copy_ub.h
  original_path: examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/data_copy_ub.h
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 21
  - 145
  sha256: sha256:f5ca47ce371eb60e16d3fac8bb0a5f8921c62de8515d22de92b900e3c7733911
  excerpt_sha256: sha256:848f0dfa47facbfcddf126f931b9a62f125a0aced77b4f9229eb7eb23768b8f0
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_GMToUB.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_GMToUB.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 3
  - 320
  sha256: sha256:8fd9166a39e7ab163695f1d965ad633725afa1c60cff08708b439f58f2a646ee
  excerpt_sha256: sha256:643aefa2bdb90c4fa26a228d9f36b5d487f11b9ebbcc80c4d7d3f52273abf98c
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_UBToGM.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_UBToGM.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 58
  - 148
  sha256: sha256:23e9b37e62ff5c2fed4b142ad65b346f8987aa6be527e291dae63466dc88f315
  excerpt_sha256: sha256:e4fc628736c5c7870254ce95b9ef24afb65e80df4762615190a2b173e22cb01d
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/arch22/datacopy_optimization_design.md
  original_path: ops/ascendc-performance-best-practices/references/common/arch22/datacopy_optimization_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 55
  sha256: sha256:dbb672d9f6f872d02ba5a255ac9b1949595d8fa869efb174c27895da04560a38
  excerpt_sha256: sha256:10621504e99f08b702f2b096bf353ab282bc4da997e2d7e8b96df1a9f60c4c45
learning: {}
tags:
- strided-copy
- datacopypad
- arch22
- padding-units
seed_reason: 审读固定开源修订并提炼中文实现配方，保留既有 ID 语义；API 单位以实际 API 文档为准；未做目标 SDK 编译或 NPU 性能验证。
parent: implementation.memory-transfer
references:
- implementation.tiling-tail.valid-length
- implementation.buffer-lifetime.reuse
evidence_status: source_reviewed_not_benchmarked
---

# 用 DataCopyPad 一次搬运规则跨行有效片段

## 解决的问题与平台边界

二维 GM 中每行只需一段连续列时，逐行 copy 增加调用次数，整行载入再裁剪又浪费流量。GM→UB 的多块 DataCopyPad 可用 `blockCount` 描述行数，用 `blockLen/srcStride` 描述每行有效段及间隙，同时在 UB 内形成对齐行。适用于行宽、物理 pitch 和有效列段固定的规则矩形；任意索引 gather、负 pitch、跨页不规则列表不能靠同一组 stride 表达。

本配方核验的是 Atlas A2/A3 的无 mode 模板参数重载。API 文档分别列出产品支持与参数范围：这里不使用 950 的 Compact、负 `srcStride` 或更宽字段语义；目标为 910C 时仍需按实际 SoC/SDK 对照其 A3 支持表。`scope=dav-2201` 表示 arch22 路径证据，不把架构名当作型号到版本的替代证明。

## 参数的单位与地址公式

设 `R` 行、每行有效 `C` 元素、GM 物理行跨度 `Sg` 元素、每元素 `s` 字节，`Sg>=C`。`base` 是第 0 行所需列段的 GM 元素偏移。源第 `r` 行起点 `base+r×Sg`，有效字节 `L=C×s`。无显式左右 padding 时，UB 第 `r` 行从 `r×U` 字节开始，`U=AlignUp(L,32)+32×dstStride`。

| 字段/变量 | GM→UB 本重载的含义及单位 |
|---|---|
| `blockCount` | 行数，A2/A3 为 0…4095；实际分块取正数 |
| `blockLen` | 每行有效字节 `L`，小于 `2^21` 且是 `sizeof(T)` 的倍数 |
| `srcStride` | 前一有效段结束到下一行有效段起点的间隔，字节 `(Sg-C)×s` |
| `dstStride` | UB 对齐行结束后的额外间隔，单位为 32B DataBlock，不是字节 |
| `leftPadding/rightPadding` | 元素数；各自所占字节不能超过 32B |

不能把 `srcStride` 填为完整 pitch，也不能将 UB 的 `dstStride` 填成 `U`。换成 UB→GM 时，单位随内存端改变：`srcStride` 为 32B DataBlock，`dstStride` 为 GM 字节间隙。常见性能笔记里的通用结构体伪代码不替代具体重载说明。

## 实现步骤和可复用片段

Host 先以 64 位整数验证最后一个 GM 元素、乘法溢出与 UB 上界，再窄化字段；超出 `blockCount/blockLen/stride` 范围时切更多组，不能先 `static_cast` 截断。UB 的目标首址必须32B对齐，源 GM 首址按文档只需1B对齐，但数据视图仍应保持 `T` 的有效对象边界。

下例 `T=float`，`gm` 为已绑定整个输入的 `GlobalTensor<float>`；`tile` 为已分配、32B对齐且容量至少 `R×rowElems` 的 `LocalTensor<float>`。`R,C,Sg,base` 由 C2 tile 元数据提供，均为元素/行计数；已证明 `1<=R<=4095`、`C>0`、`Sg>=C`、`C*4<2^21`、`(Sg-C)*4<=UINT32_MAX` 及地址/UB 范围。不要复制样例的固定矩阵尺寸。

```cpp
const uint64_t rowBytes = uint64_t(C) * sizeof(float); // 字节
const uint64_t alignedBytes = (rowBytes + 31) / 32 * 32;
const uint32_t rowElems = alignedBytes / sizeof(float); // UB 行跨度：元素
AscendC::DataCopyExtParams cp{};
cp.blockCount = static_cast<uint16_t>(R);
cp.blockLen = static_cast<uint32_t>(rowBytes);
cp.srcStride = static_cast<uint32_t>((uint64_t(Sg) - C) * sizeof(float));
cp.dstStride = 0; // 额外 32B block 数；仍会逐行自动对齐
cp.rsv = 0;
AscendC::DataCopyPadExtParams<float> pad{false, 0, 0, 0.0f};
AscendC::DataCopyPad(tile, gm[base], cp, pad);
// 沿用队列或显式 MTE2 -> Vector 同步后：
// 第 r 行 UB 视图 tile[r * rowElems]，数学 count=C，不能取 rowElems。
```

`isPad=false` 的 dummy 不保证是归约单位元，不能假设自动补零。只按 `C` 个有效元素计算最直接。若后续 API 必须处理整条对齐行，显式选择数学上正确的 padding 并满足字段上限，例如 Sum 的0、Max 的负无穷需与 dtype/NaN 语义一致。不能因为 pad 的结构体初始化为0，就认为所有 dummy 也是0。

## 收益、存活期与失败回退

逐行搬运 `R` 次可降为一组1次；组内有效 GM 流量仍为 `R×C×s`，对比整行加载的 `R×Sg×s`，理论少搬 `R×(Sg-C)×s`。UB 实占 `R×AlignUp(C×s,32)`（额外 stride 和显式 padding 另加）；double buffer 两槽再乘2。若非对齐行过短，UB padding 比例 `(AlignUp(L,32)-L)/L` 大，未必胜于更大连续块加本地重排。

DMA 完成前 `tile` 被写占用，最后一个消费者完成前整组对齐行仍存活；下一次 DataCopyPad 覆盖同槽必须等待这些消费者。输入输出可能别名时，先证明本组写回不会破坏未来行的读入。测试 `C*s` 为31/32/33字节附近的可表示 dtype 长度、单行/多行、非零列起点、尾行和不同 pitch。出现行错位首先核验单位/UB 行跨度；容量不足缩小 R，跨行不规则保留逐段路径。

来源事实：asc-devkit `data_copy_ub.h` 用 `curCols` 与 `(n-curCols)*sizeof(half)` 搬运矩形尾列，API 文档给出本表单位、dummy 和范围。代码改用 Ext 参数、float 和显式变量定义，是避免字段截断的提炼版本；未引用上游私有 Kernel 类，也未做目标 SDK 编译或性能验证。
