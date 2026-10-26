---
schema_version: aprof.knowledge-record/v1
id: implementation.fusion-composition
kind: router
version: 1.0.0
status: active
title: 算子组合与 Cube–Vector 交接
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/00_introduction/03_fusion_operation/matmul_leakyrelu_advanced_api/matmul_leakyrelu_advanced_api.asc
  original_path: examples/01_simd_cpp_api/00_introduction/03_fusion_operation/matmul_leakyrelu_advanced_api/matmul_leakyrelu_advanced_api.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 24
  - 188
  sha256: sha256:50399b2e9cd19fe656777c2245c8e599f5b8ed159d16c6687caa9ca9b272a9fa
  excerpt_sha256: sha256:7f68ed19c2f76ff461be3265ef9d516961f93c50d15240f9e1b78a44c3032c0f
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/00_introduction/03_fusion_operation/matmul_leakyrelu_basic_api/matmul_leakyrelu_basic_api.asc
  original_path: examples/01_simd_cpp_api/00_introduction/03_fusion_operation/matmul_leakyrelu_basic_api/matmul_leakyrelu_basic_api.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 48
  - 195
  sha256: sha256:64086c964d5df9daf2dd0b81ba07b9352564ee06ede372423b58fea8a46b05e6
  excerpt_sha256: sha256:81c4437d75f7642307a9f02749f3af0761cf1b928cbf6df7899dee357c70ae13
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/mmad_gelu.asc
  original_path: examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/mmad_gelu.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 21
  - 613
  sha256: sha256:2fb232c81805420c88755d9bc41ea3561c3f4107946306425d1a43b48c31dd1d
  excerpt_sha256: sha256:a9dc9e4064f9198bc1a959600b5ec80e454c71f38ac2681b7cbe3e0a8d5d9728
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/README.md
  original_path: examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 31
  - 157
  sha256: sha256:f455633ee4affaed0ad5591c0acc1d47c2d7099c3bc25a8a87a3f2259783008e
  excerpt_sha256: sha256:cce28e26891a94ea183739fcf3345e32edd588c63c48de46dbc427b2878e36cd
- path: skills/ascendc-aprof-optimization/knowledge/sources/cann-samples/17c948bb961fc6a660e4fcab45f6bf217c9c6239/Samples/1_Features/hardware_features/cv_datapath/README.md
  original_path: Samples/1_Features/hardware_features/cv_datapath/README.md
  revision: 17c948bb961fc6a660e4fcab45f6bf217c9c6239
  lines:
  - 1
  - 200
  sha256: sha256:75fd879ecc4bf94dd4c72e40bdc1b1a343c250292430cb6c0b5c566144fd2283
  excerpt_sha256: sha256:7011f96f11ead5fed7515f5e1295dbe7c24de55cfeecbc6b60e67690409b3e5d
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md
  original_path: docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 28
  - 151
  sha256: sha256:69845e8fa794040e321959eaa57105a79cdf880c2d9460b7bf65a53f3c644827
  excerpt_sha256: sha256:02edbe3918b020be18c5b07b81c9bc18153e3f3ab7ba41a9962391c7173aa399
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md
  original_path: docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 28
  - 151
  sha256: sha256:fb6098e64301d056e53eb0f083dcc96083075fc8da78409492f905653c311f96
  excerpt_sha256: sha256:c5145c71c4361eef7d3e7a5597dfa8bc235c92153767ab8322ebee5109ed0b5d
learning: {}
tags: []
seed_reason: 固定开源修订审读并以中文提炼；未做性能训练或硬件收益验证。
parent: implementation.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: implementation.fusion-composition.cube_vector_epilogue
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.fusion-composition.cube_vector_epilogue
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.fusion_boundary
  - constraint.dependency_lifetime
  - constraint.cross_engine_dependencies
  - constraint.target_api
  - constraint.workspace_ownership
  prior_score: 2
  fallback: false
  seed_reason: 属于本分支的条件性方案；先核验正文的能力、语义和资源前提，再比较成本。
- target: implementation.fusion-composition.cv_multistage_handoff
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.fusion-composition.cv_multistage_handoff
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.fusion_boundary
  - constraint.dependency_lifetime
  - constraint.cross_engine_dependencies
  - constraint.target_api
  - constraint.workspace_ownership
  prior_score: 2
  fallback: false
  seed_reason: 属于本分支的条件性方案；先核验正文的能力、语义和资源前提，再比较成本。
- target: implementation.fusion-composition.vector_chain_residency
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.fusion-composition.vector_chain_residency
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.fusion_boundary
  - constraint.dependency_lifetime
  - constraint.target_api
  prior_score: 2
  fallback: false
  seed_reason: 属于本分支的条件性方案；先核验正文的能力、语义和资源前提，再比较成本。
- target: implementation.fusion-composition.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知条件保留现有合法方案并补资料。
---

# 算子组合与 Cube–Vector 交接

按 C2 冻结的方案与 features 选择实现技巧；可同时进入多个分支。保持算法、所有权和数值契约；超出已声明自由度时请求重规划。

- [Cube 输出最终化后的 Vector epilogue 融合](recipes/cube-vector-epilogue.md)
- [dav-2201 的 C1–V1–C2–V2 多阶段交接](recipes/cv-multistage-handoff.md)
- [Vector 算子链融合与 UB 中间值驻留](recipes/vector-chain-residency.md)
- [算子组合与 Cube–Vector 交接：保守回退](fallback.md)

来源审读不等于目标硬件收益验证；不确定的能力或容量返回 needs_evidence，不能由模板代填。
