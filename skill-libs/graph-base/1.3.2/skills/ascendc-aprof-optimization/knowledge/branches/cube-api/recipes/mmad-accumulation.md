---
schema_version: aprof.knowledge-record/v1
id: implementation.cube-api.mmad_accumulation
kind: recipe
version: 1.0.0
status: active
title: 本地 Mmad 基本块、K 累加与尾块控制
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
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute/Mmad.md
  original_path: docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute/Mmad.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 349
  sha256: sha256:1ebb798bb29605a5cbabb2b52964032fff2e5a3b0c02b9ba7556b05f573e062a
  excerpt_sha256: sha256:1ebb798bb29605a5cbabb2b52964032fff2e5a3b0c02b9ba7556b05f573e062a
- path: skills/ascendc-aprof-optimization/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/fused_infer_attention_score/op_kernel/arch22/attn_infra/gemm/tile_common/fused_tile_mmad.hpp
  original_path: attention/fused_infer_attention_score/op_kernel/arch22/attn_infra/gemm/tile_common/fused_tile_mmad.hpp
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 91
  sha256: sha256:4a0a41c147c79d642a6b55d43bf7dcd0f1738eff0868ae0c9ae4297a556a5ab5
  excerpt_sha256: sha256:4a0a41c147c79d642a6b55d43bf7dcd0f1738eff0868ae0c9ae4297a556a5ab5
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
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute_key_features/UnitFlag.md
  original_path: docs/zh/api/SIMD-API/basic_api/cube_compute_ISASI/mmad_compute_key_features/UnitFlag.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 78
  sha256: sha256:aae10d46db710c9ae9b24e5a6544267d1c67ed3294ab005d934f37ced21ac185
  excerpt_sha256: sha256:aae10d46db710c9ae9b24e5a6544267d1c67ed3294ab005d934f37ced21ac185
learning: {}
tags:
- accumulator-init
- local-k
- mmad
- tail-k
seed_reason: 审读五个固定开源修订中的直接来源，以中文提炼实现契约；保留旧 ID 含义，不承诺目标 SDK 编译结果或 NPU 性能收益。
parent: implementation.cube-api
references:
- implementation.cube-api.fixpipe_output
- implementation.cube-api.matmul_config
- implementation.precision-boundaries.bounds
- implementation.precision-boundaries.numeric
evidence_status: source_reviewed_not_benchmarked
---

# 本地 Mmad 基本块、K 累加与尾块控制

## 原理与适用范围

本条实现一个核已拥有的输出 tile，在 L0A/L0B 放入合法分形后，沿本地 K 次序累加到同一 L0C。首 K 块初始化 C，后续块保留 partial，尾 K 只计算有效长度，最后才输出；减少不必要初始化、参数计算和局部等待的前提是严格保持累加依赖。它不决定 Split-K 任务、跨核 workspace、atomic 或最终归约所有权。

C2 必须已固定 local M/N/K、base 切片、dtype/layout、bias 与顺序；当前平台有 Mmad/Fixpipe 支持、真实 L1/L0 预算和完成边。A2/A3 的 A 在 L0A/A2、格式 Zz，B 在 L0B/B2、格式 Zn，C 在 L0C/CO1、格式 Nz；A2/B2 是存储位置名称，不表示芯片 A2 代际。950 的 A 格式约束另有 Nz，不能复用 A3 LoadData 参数而只换编译宏。

## 实施步骤与资源代价

1. 将有效 `m/n/k` 与实际物理分形容量分开。Mmad 参数是当前逻辑维度，固定文档范围分别为 `[0,4095]`；任一维 0 是 NOP，不能指望 NOP 初始化或清空 C。输入须经合法搬运变为目标分形，A/B 起址各 512B 对齐、C 起址 1024B 对齐，bias BT 起址 64B 对齐。
2. 普通无 bias 路径只在第一个有效 K 片设置 `cmatrixInitVal=true`；后续 false 且不重新清空 C。含 bias 路径按带 bias 的 API 在正确时刻初始化，不能每片再次加 bias，也不能使用已废弃 `isBias` 字段猜累加。源码 wrapper 的无 bias 与 bias 重载分别配置，迁移时理解其语义而非复制调用次数。
3. 完整 K 片的 `k=baseK`，最后非整除片用实际 `kTail`，相应 L1→L0 的布局、K 对齐与容量仍由物理尺寸决定。masked/padded K 数据须按搬运契约处理；不能认为设置有效 k 就允许 GM 读超界。float 的 `kDirectionAlign` 需与 A/B LoadData 布局一致；源 arch22 wrapper 对 float ColumnMajor 设置 true，不代表所有 transpose 都设 true。3510 的该字段仅支持 false，须配套其实际 LoadData 布局，不能沿用 arch22 的 true 分支。
4. 每片 MTE1→M 完成后才能读 A/B，M 使用结束后才能覆写其 L0 槽；同一 L0C 连续累加还要遵守 M 流水自身依赖。固定 API 与 arch22 实现使用 `(m/16)*(n/16)<10` 时插入 `PipeBarrier<PIPE_M>()`；它只作用于该依赖，不能替代跨流水事件。未核验目标 SDK/布局时保留保守正确同步，不将此阈值泛化为所有 Cube 指令规则。
5. 初次实现保持 unitFlag=0 与原显式完成边。仅在最终输出覆盖、方向和读取完成都能证明时使用 unitFlag：多片同一 C 的中间 Mmad=2，最后 Mmad=3，单次覆盖该 C 的 Fixpipe=3，复位其标记后才可复用；不要让中间片的 C 被提前输出。

令对齐后的局部尺寸为 `Ma/Na/Ka`，L0A 约 `MaKa×sizeof(A)`，L0B 约 `KaNa×sizeof(B)`，L0C 约 `MaNa×sizeof(acc)`；A/B 双缓冲各乘槽数，全部满足实际分配和硬件格式。逻辑计算量约 `2mnK` FLOP；实际分形计算/搬运还受 padding 影响。更大 m/n 减少块数却提高 L0C 占用，小 tile 控制开销更大；不能只为越过 barrier 阈值扩大 tile 超预算。

## 独立参数片段

`aL0/bL0` 为已完成 MTE1 写入的 half 分形 tensor，`cL0` 为当前输出的 float L0C，容量和对齐已证明；本示例限定 `1<mValid≤4095`，`nValid/kValid` 为本片非零有效元素数且≤4095，`firstK` 为当前输出首片，`lastK` 为当前输出最后片。示例不使用 bias 和 unitFlag，工程保留原 MTE1↔M、M↔FIX 及 L0C 生命周期。

`mValid=1` 时默认启用 GEMV，A 必须按 ND 布局准备，应走独立的布局和加载路径，不能直接调用下面的分形片段。只有 3510 在目标 API 支持、格式与加载均重新核验时才可考虑 `disableGemv=true`；A2/A3 不采用此开关。M 尾恰为 1 也必须遵守该边界。

```cpp
AscendC::MmadParams p{};
p.m = mValid;
p.n = nValid;
p.k = kValid;
p.cmatrixInitVal = firstK;
p.cmatrixSource = false;
p.unitFlag = 0;
AscendC::Mmad(cL0, aL0, bL0, p);
if ((mValid / 16) * (nValid / 16) < 10) {
    AscendC::PipeBarrier<PIPE_M>();
}
// 只有 lastK 的结果可交给原 Fixpipe 输出路径；firstK==lastK 同时成立合法。
```

调用处必须为每片准备不同 K 子区间，不能反复传同一 A/B 内容；K=0 单独按 oracle 处理 bias/零输出，不执行上述非零片段。unitFlag 版本由完整 Mmad/Fixpipe 配对状态表替换最后参数，不单独修改这段代码。

## 数值、失败与证据

half/bfloat16→float 与 int8→int32 是不同组合，不能在本条内改为低精度累加。局部 K 切片变化可能改变舍入顺序，按原数值契约验证大动态范围、抵消、极小值、NaN/Inf、±0 与最大 K；Mmad 固定文档提示避免 NaN 输入且饱和模式会改变 Inf/NaN，原域要求特殊值而该路径不能满足时保留原正确路径，不删 case 或改 overflow 设置来掩盖。整数溢出也须按原 oracle 处理。

测试一片/两片/多片、K tail、m=1 的 GEMV 特殊布局、M/N tail、小分形 barrier 两侧、不同 transpose 和 bias 只加一次。首片漏清空导致跨 tile 污染，后片清空只剩最后 K，尾 K 倍数场景通过但非整除错，unitFlag 配错挂起均应撤回。来源事实为固定 Mmad/UnitFlag API、basic high_performance 与 arch22 fused_tile_mmad 源码；步骤、公式与失败映射为工程提炼。dav-2201/A2/A3 与 dav-3510/950 分别编译，3510 `disableGemv`、新格式/类型不能推广到 A3，无目标硬件收益证据。
