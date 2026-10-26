---
schema_version: aprof.knowledge-record/v1
id: implementation.cube-api.fixpipe_output
kind: recipe
version: 1.0.0
status: active
title: Fixpipe 输出布局、stride、dtype 与 UnitFlag 配对
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
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/cube_compute_store/Fixpipe_L0CToGM.md
  original_path: docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/cube_compute_store/Fixpipe_L0CToGM.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 327
  sha256: sha256:1f55a31fe89adbed8b4eca9e8eb8c8ef8b2e6668d8a3fe35b23401e50ddacf35
  excerpt_sha256: sha256:1f55a31fe89adbed8b4eca9e8eb8c8ef8b2e6668d8a3fe35b23401e50ddacf35
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute_key_features/UnitFlag.md
  original_path: docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute_key_features/UnitFlag.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 78
  sha256: sha256:aae10d46db710c9ae9b24e5a6544267d1c67ed3294ab005d934f37ced21ac185
  excerpt_sha256: sha256:aae10d46db710c9ae9b24e5a6544267d1c67ed3294ab005d934f37ced21ac185
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute/Mmad.md
  original_path: docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute/Mmad.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 349
  sha256: sha256:1ebb798bb29605a5cbabb2b52964032fff2e5a3b0c02b9ba7556b05f573e062a
  excerpt_sha256: sha256:1ebb798bb29605a5cbabb2b52964032fff2e5a3b0c02b9ba7556b05f573e062a
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/01_matrix_compute/matmul_basic_api_high_performance/mmad.asc
  original_path: examples/01_simd_cpp_api/05_best_practices/01_matrix_compute/matmul_basic_api_high_performance/mmad.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 644
  sha256: sha256:8891b02f5cbf5f0841041e07bbcf766f07abb53b474ad675c751fe2c9e52cb92
  excerpt_sha256: sha256:8891b02f5cbf5f0841041e07bbcf766f07abb53b474ad675c751fe2c9e52cb92
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/01_matrix_compute/matmul_basic_api_high_performance/README.md
  original_path: examples/01_simd_cpp_api/05_best_practices/01_matrix_compute/matmul_basic_api_high_performance/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 532
  sha256: sha256:fe8df2c2792de115f12584e3444941930d39da00174759871ab98e4f48779c3d
  excerpt_sha256: sha256:fe8df2c2792de115f12584e3444941930d39da00174759871ab98e4f48779c3d
learning: {}
tags:
- fixpipe
- output-layout
- stride-unit
- unitflag
seed_reason: 审读五个固定开源修订中的直接来源，以中文提炼实现契约；保留旧 ID 含义，不承诺目标 SDK 编译结果或 NPU 性能收益。
parent: implementation.cube-api
references:
- implementation.cube-api.mmad_accumulation
- implementation.precision-boundaries.bounds
- implementation.precision-boundaries.numeric
- implementation.vector-api.cast
evidence_status: source_reviewed_not_benchmarked
---

# Fixpipe 输出布局、stride、dtype 与 UnitFlag 配对

## 原理与适用条件

Fixpipe 在 L0C→GM 时可完成 NZ→ND、输出 Cast 或指定量化，减少单独的格式/类型转换与搬运。但直接输出要同时满足目标布局、有效区域、舍入、量化参数与 L0C 释放时刻；并不是把普通 DataCopy 换一个函数名。C2 必须固定输出拥有者、逻辑 shape/物理 stride、输出 dtype、bias/激活/量化语义和允许的实现变换，本条不改变它们。

先明确平台：dav-2201 的 A2/A3 只用本固定文档的 `FixpipeParamsV220`；dav-3510/950 还支持 `FixpipeParamsArch3510`。NZ 目的 `dstStride` 在 V220 为 32B DataBlock，在 Arch3510 为 element，NZ2ND 的 dstStride 两者为目的行元素数；只换结构体名字会产生地址错位。L0C→UB/L1 是其他通路，有独立支持和限制，不能按 GM 通路推导。

本文代码仅覆盖 `ndNum=1`。扩展为多矩阵时，`srcNdStride` 在 V220 的单位为 `16*C0_Size`、范围 `[0,512]`，在 Arch3510 的单位为 `C0_Size`、范围 `[0,65535]`；`C0_Size=16*sizeof(src)`，单位为字节。`dstNdStride` 为目的矩阵间的元素偏移，V220 范围 `[0,65535]`，Arch3510 范围 `[1,2^32-1]`（单矩阵可填 0）。逐矩阵检查源/目的末地址、ND/NZ 布局及目标 API，不能把单矩阵示例的两个 0 直接复制到 `ndNum>1`。

## 配置与生命周期步骤

1. 从已完成本地 K 累加的 L0C NZ 数据出发，记录源物理 `mAlign`、源起始地址、输出 N 行跨度与当前 `(m0,n0)` 偏移。源 Fixpipe 起址要求64B对齐；若来自 Mmad，仍须同时满足其1024B 起址要求，不能因输出 API 只要求64B降低上游约束。
2. V220 的 `nSize` 通常须16倍数（float NZ channel split 特例8倍数），`mSize` 为有效行数；NZ2ND 的 mSize 还受文档8192上限。`srcStride` 单位为 `C0_Size=16*sizeof(src)`，数值为源 M 方向对齐长度，不是字节；ND `dstStride` 为输出行元素跨度，不是当前 tile 宽度。
3. 全部字段在窄类型赋值前检查范围。不能把非16对齐的逻辑尾 N 直接塞进要求16倍数的 nSize；选择已证明的尾输出路径，或合法 padded workspace 后仅裁剪有效输出。扩大到对齐 nSize 只有目的分配/物理行跨度明确覆盖且不会覆写他核区间时才可用，绝不写到用户张量行尾之外。
4. float→float/int32→int32 使用 NoQuant；float→half/bfloat16 按支持使用 F322F16/F322BF16，其模式为 RINT，必须与原独立 Cast 的舍入一致才可融合。带 scale 的 quant 模式不是普通 Cast，scalar/tensor scale 类型、布局、轴、位置与生命周期另核验；不得为了兼容接口添加或改变 ReLU。
5. 不启用 UnitFlag 时保留原 M→FIX 完成依赖和 FIX→M 的 C 复用依赖。启用时 Mmad/Fixpipe 双方一起配置，布局转换的计算方向按 API 配套：NZ2ND/ChannelMerge 要求 N 方向优先 `SetMMRowMajor()`，普通相应路径用 `SetMMColumnMajor()`。方向与写读顺序不符会破坏细粒度并行。
6. 标准多 K 累加、一次整 tile 输出的标记序列：中间 Mmad=2（保持 C 可累加），最后 Mmad=3（结果可读），Fixpipe=3（读取完的块可被后续 Mmad 覆写）。不能把 flag=2 理解为“输出已完成”。计算大范围但只搬出一部分可能遗留未复位块，按特性文档重置或回退不启用，不自行删同步处理。

## V220 的明确上下文片段

例中 `cL0` 为 float NZ L0C，逻辑 tile 为 `mValid×nValid`，物理 M 对齐长度 `mAlign`；`nValid` 是正16倍数，`mValid>0`，所有参数在文档范围内。`cGm` 为 float ND 输出，物理每行 `ldcElements` 个 float，当前核独占 `[m0:m0+mValid,n0:n0+nValid]` 且所有写入不重叠；GM 已分配足够范围。示例 dav-2201，无量化、无 ReLU、无 unitFlag，前后完成边沿用工程正确实现。

```cpp
#if defined(__NPU_ARCH__) && (__NPU_ARCH__ == 2201)
AscendC::FixpipeParamsV220 p{};
p.mSize = mValid;
p.nSize = nValid;
p.srcStride = mAlign;           // C0_Size 单位，不是 mAlign*sizeof(float)
p.dstStride = ldcElements;      // CFG_ROW_MAJOR: float 元素/行
p.quantPre = QuantMode_t::NoQuant;
p.ndNum = 1;
p.srcNdStride = 0;
p.dstNdStride = 0;
p.unitFlag = 0;
const uint64_t outputOffset = static_cast<uint64_t>(m0) * ldcElements + n0;
AscendC::Fixpipe<float, float, AscendC::CFG_ROW_MAJOR>(cGm[outputOffset], cL0, p);
#endif
```

`m0/n0/mValid/nValid/mAlign/ldcElements` 均为核入口已核验的整数；`mAlign=ceil(mValid/16)*16` 只在该源实际按此分配时成立。若输出改 half，p.quantPre 必须改为支持的 F322F16，并重新核验目的字节、RoundMode、特殊值与数值误差；本条不授权主动改变输出 dtype。3510 路径另构造其模板布局参数，不从上述 guard 漏出 V220 之外的新特性。

## 成本、数值与验证

有效 GM 输出流量约 `mValid×nValid×sizeof(out)`；源 L0C 容量约 `mAlign×nAlign×sizeof(acc)`，padding workspace 则增加其分配、裁剪搬运与同步。融合 Cast 可省一段中间存储但会把转换放在输出时刻，须维持全部消费者的舍入与读到的数据。UnitFlag 的收益来自更细粒度重叠；若 MTE2/Cube 已主导，Fixpipe 时间指标变化不保证 Task 降低，不能从样例固定512B或收益值推跨平台最优。

检查 ND/NZ、不同 ldc、tile 非零偏移、多矩阵 ndNum、单次/多次输出、尾 M/N、buffer 复用与 unitFlag 开关。对每路验证最后有效字节和目的区间互斥，硬件对重叠目的写可能不报警且不保证顺序。量化/ReLU 参数不得为 NaN/Inf/次正规数；CTRL 饱和模式影响浮点特殊值，不能为了跑通改为新语义。每行错位、尾列覆盖、零尺寸被当作清零、flag 悬挂或特殊值不同应回退原输出/Cast 路径。

来源事实为固定 Fixpipe、UnitFlag API 和 basic high_performance 的 Compute/CopyOut 组合；尾部守卫、资源公式与步骤为工程提炼。dav-2201/910B/910C 与 dav-3510/950 按安装 SDK 单独编译核验，A3 不采用 Arch3510 的布局/stride/新增量化类型，无目标板性能验证。
