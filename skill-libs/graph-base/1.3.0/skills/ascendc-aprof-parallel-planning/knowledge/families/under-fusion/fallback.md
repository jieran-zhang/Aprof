---
schema_version: aprof.knowledge-record/v1
id: planning.under-fusion.fallback
kind: strategy
version: 1.1.0
status: active
title: 融合与组合通用回退
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ops-design-paradigms/references/paradigms/reduction/generic/liveness-fusion.md
  original_path: ops/ops-design-paradigms/references/paradigms/reduction/generic/liveness-fusion.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 111
  sha256: sha256:08f91ab6c5846b60435aa9e70fed185f0947718604320544a99dbd8132ba8477
  excerpt_sha256: sha256:08f91ab6c5846b60435aa9e70fed185f0947718604320544a99dbd8132ba8477
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/README.md
  original_path: examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 208
  sha256: sha256:f455633ee4affaed0ad5591c0acc1d47c2d7099c3bc25a8a87a3f2259783008e
  excerpt_sha256: sha256:169eb97ea7e2c0204004ae0aba222664c39fad78545988faba90d99327f34b79
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.under-fusion
references:
- planning.under-fusion.chain
- planning.under-fusion.reduce_broadcast
- planning.under-fusion.epilogue
evidence_status: source_reviewed_not_benchmarked
---

# 融合与组合通用回退

保留当前任务已验证的分阶段计算图，明确每个 kernel 的输入、可见中间输出、dtype/cast、输出所有权及完成依赖。融合失败的实际原因可以是容量、外部消费者、非局部依赖、别名、精度或 API 通路证据不足；不得仅以 kernel 多判定基线错误。

连续逐元素链使用 `planning.under-fusion.chain`；归约后广播使用 `planning.under-fusion.reduce_broadcast`；矩阵乘后处理使用 `planning.under-fusion.epilogue`。候选分别记录“选定 kernel 边界”与“中间存储路径”。在 A3/dav-2201，来源 MatmulGelu 的 CV 组合经 GM 中转；不能把同 kernel、VECIN 接口或理论融合图解释为必然消除 GM 写读。

每阶段 `UB_peak=max_t Σ live_aligned_bytes(t)+API_tmp(t)`，跨阶段 workspace 计真实同时存活中间量。生产者完成数据写入后发布 ready，消费者结束后再回收；独立 kernel 由流依赖交接。保留所有原始舍入与归约次序，非线性只能作用在完整统计或完整 K 累加之后。

C2 给出真实 fallback entry/key、候选互斥条件、容量峰值和精度缺口；C3 在相同正确性口径与统一计时下比较完整路径。通用算法 scope all，不包含跨平台 API 或性能资格；当前只有固定来源审读。
