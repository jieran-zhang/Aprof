---
schema_version: aprof.knowledge-record/v1
id: implementation.fusion-composition.fallback
kind: strategy
version: 1.0.0
status: active
title: 算子组合与 Cube–Vector 交接：保守回退
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
parent: implementation.fusion-composition
references: []
evidence_status: source_reviewed_not_benchmarked
---

# 算子组合与 Cube–Vector 交接：保守回退

保持已知合法的实现/任务划分。只有相应事实经核验，才比较本分支方案；缺失的语义、API、容量或平台条件保持未知。

C2 交付允许的算法、所有权和资源边界，C3 不为采用模板而改变这些边界。本条目不提供收益保证，不把其他平台的实现写法当作当前设备能力。
