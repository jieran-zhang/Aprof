---
schema_version: aprof.knowledge-record/v1
id: implementation.precision-boundaries.fallback
kind: recipe
version: 1.1.0
status: active
title: 精度与边界 回退方法
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/alg-welford.md
  original_path: ops/ascendc-tiling-design/references/reduction/alg-welford.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 74
  sha256: sha256:6c8e784dad546cb1caa07867596721b3d1c8ecc746396df5392054f44d84eb28
  excerpt_sha256: sha256:6c8e784dad546cb1caa07867596721b3d1c8ecc746396df5392054f44d84eb28
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 151
  sha256: sha256:a41ac2ff57f181c342d823a1b453bfabfb20c56bf840e31f4dff7232cefdc80a
  excerpt_sha256: sha256:a41ac2ff57f181c342d823a1b453bfabfb20c56bf840e31f4dff7232cefdc80a
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
tags: []
seed_reason: 审读五个固定开源修订中的直接来源，以中文提炼实现契约；保留旧 ID 含义，不承诺目标 SDK 编译结果或 NPU 性能收益。
parent: implementation.precision-boundaries
references:
- implementation.precision-boundaries.bounds
- implementation.precision-boundaries.numeric
evidence_status: source_reviewed_not_benchmarked
---

# 精度与边界回退方法

保留 C2 已通过原 oracle 的正确实现。凡 dtype/累加/舍入/特殊值、padding 中性元、分段次序、ABI、地址范围、实际峰值或同步完成边任一缺证据，就不提交该候选的性能结论。未知目标 API 支持时补目标产品、dav-2201/dav-3510 与 SDK 版本，A3 不引用 3510 专属路径作为支持证明。

先固定失败现场：输入 shape/stride/dtype、随机种子或最小复现、原 case 标准、原与新输出、首个偏差中间量、实际编译参数和完整日志。数值错按 Cast→累加→合并→输出找到第一次差异；越界/挂起先核对 byte/element/块单位、空维减1下溢、窄字段截断、buffer 最后使用和事件。NaN/Inf 不同要检查原 API 与 CTRL 模式，不能修改输入域或饱和设置掩盖结果。

补证顺序为：原 oracle 数值与空/全 mask 语义，C2 允许的局部变换，目标 API 支持，地址与容量/生命周期闭合，再运行完整正确性。FP32 partial、“数学公式相同”、随机 case 通过、没有硬件越界报警都不是充分证明。量化/MX 另核验 scale 轴、pack 与支持，不按连续维猜测；padding 只参与存储，不擅自加入有效计数。

在真实瓶颈下比较的候选仍须用相同完整 case 与计时协议，正确性未通过不计时排名，已有性能不能覆盖失败。需要改算法、分段所有权、容差或 shape 域时返回 C2 重规划，不静默采用新近似。C3 记录失败/排除原因、条目版本、参数变化、可恢复的旧实现与仍缺的证据，必要时调用 precision/runtime/crash 调试辅助能力。

来源事实：固定 Welford 状态、AR full-load 的有效/对齐分离、Cast 和矩阵 API 的单位/特殊值约束；回退补证流程为工程提炼。契约适用 all，但不新增硬件 API，也不承诺改动收益；本条仅来源审读，未编译目标 SDK 或上板。
