---
schema_version: aprof.knowledge-record/v1
id: implementation.cube-api
kind: router
version: 1.0.0
status: active
title: Cube / Matmul 计算执行
scope:
  platforms:
  - all
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
tags: []
seed_reason: 固定开源修订审读并以中文提炼；未做性能训练或硬件收益验证。
parent: implementation.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: implementation.cube-api.fixpipe_output
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.cube-api.fixpipe_output
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.l1_l0_budget
  - constraint.target_api
  - constraint.precision
  - constraint.output_layout_stride
  - constraint.unitflag_pairing
  prior_score: 2
  fallback: false
  seed_reason: 属于本分支的条件性方案；先核验正文的能力、语义和资源前提，再比较成本。
- target: implementation.cube-api.matmul_config
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.cube-api.matmul_config
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.l1_l0_budget
  - constraint.target_api
  - constraint.precision
  - constraint.static_dynamic_tiling
  prior_score: 2
  fallback: false
  seed_reason: 属于本分支的条件性方案；先核验正文的能力、语义和资源前提，再比较成本。
- target: implementation.cube-api.mmad_accumulation
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.cube-api.mmad_accumulation
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.l1_l0_budget
  - constraint.target_api
  - constraint.precision
  - constraint.local_accumulation_lifetime
  prior_score: 2
  fallback: false
  seed_reason: 属于本分支的条件性方案；先核验正文的能力、语义和资源前提，再比较成本。
- target: implementation.cube-api.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知条件保留现有合法方案并补资料。
---

# Cube / Matmul 计算执行

按 C2 冻结的方案与 features 选择实现技巧；可同时进入多个分支。保持算法、所有权和数值契约；超出已声明自由度时请求重规划。

- [Fixpipe 输出布局、stride、dtype 与 UnitFlag 配对](recipes/fixpipe-output.md)
- [Matmul API 模板与常量 Tiling 配置](recipes/matmul-config.md)
- [本地 Mmad 基本块、K 累加与尾块控制](recipes/mmad-accumulation.md)
- [Cube / Matmul 计算执行：保守回退](fallback.md)

来源审读不等于目标硬件收益验证；不确定的能力或容量返回 needs_evidence，不能由模板代填。
