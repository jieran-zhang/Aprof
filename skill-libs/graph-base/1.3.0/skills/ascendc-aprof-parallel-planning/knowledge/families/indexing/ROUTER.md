---
schema_version: aprof.knowledge-record/v1
id: planning.indexing
kind: router
version: 1.0.0
status: active
title: 索引访问与索引写入
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/index/gather_elements_v2/README.md
  original_path: index/gather_elements_v2/README.md
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 1
  - 106
  sha256: sha256:c8df45df36e823c8531e2e64a7d396d53f04c7e75ddc223dfb476c3910ffc43e
  excerpt_sha256: sha256:c8df45df36e823c8531e2e64a7d396d53f04c7e75ddc223dfb476c3910ffc43e
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/index/gather_elements_v2/op_host/gather_elements_v2_tiling.cpp
  original_path: index/gather_elements_v2/op_host/gather_elements_v2_tiling.cpp
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 105
  - 273
  sha256: sha256:c7bb8d76d1741b5c3212a8de9f28bf6f9de5fe2f7d012bfa90780b25e6f12793
  excerpt_sha256: sha256:e80d0fcbd0b582c83e9a37fb8fd61dcff95d5c1b98af493630cba1ff467fb9c8
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/index/gather_elements_v2/op_host/gather_elements_v2_last_dim_tiling.h
  original_path: index/gather_elements_v2/op_host/gather_elements_v2_last_dim_tiling.h
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 1
  - 369
  sha256: sha256:c5c10605e8e2621e3c8fec9e8844b5c541b65877b2037d5c3991689e4f31ec5c
  excerpt_sha256: sha256:c5c10605e8e2621e3c8fec9e8844b5c541b65877b2037d5c3991689e4f31ec5c
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/index/gather_elements_v2/op_kernel/gather_elements_v2_scalar.h
  original_path: index/gather_elements_v2/op_kernel/gather_elements_v2_scalar.h
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 35
  - 187
  sha256: sha256:d7038ab1282e3a89aaecc2123a5b5c6bd3e6ce041703dfcbc63c34a0fbace77f
  excerpt_sha256: sha256:27c6ffe9981fd02e7bf51e3722407a0bbe0b2ec0a73904fb0162e78f43843ab3
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/index/gather_elements_v2/op_kernel/gather_elements_v2_transpose.h
  original_path: index/gather_elements_v2/op_kernel/gather_elements_v2_transpose.h
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 1
  - 522
  sha256: sha256:cc2ec40a9f9d3cfce1021e356e4e8f2a5f27e1528caaeb2ff1796a6a530c0d75
  excerpt_sha256: sha256:cc2ec40a9f9d3cfce1021e356e4e8f2a5f27e1528caaeb2ff1796a6a530c0d75
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/index/gather_elements_v2/op_kernel/gather_elements_v2_last_dim.h
  original_path: index/gather_elements_v2/op_kernel/gather_elements_v2_last_dim.h
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 1
  - 523
  sha256: sha256:caf8774a67ba31a55ef29be6b785545a877eea0eb856777d588f00f6f94a858c
  excerpt_sha256: sha256:caf8774a67ba31a55ef29be6b785545a877eea0eb856777d588f00f6f94a858c
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/index/gather.md
  original_path: ops/ascendc-tiling-design/references/index/gather.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 25
  - 184
  sha256: sha256:0f63900de53cd6e704572f14fc896b4e477b47b74ebf1371c130db2810992c63
  excerpt_sha256: sha256:08be2c49bafe17407829de0a4e1d8bd47f7aef8216d7f499d8a589ced28c61a1
learning: {}
tags: []
seed_reason: 固定开源修订审读并以中文提炼；未做性能训练或硬件收益验证。
parent: planning.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: planning.indexing.gather_output_owned
  match: []
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.indexing.gather_output_owned
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.task_ownership
  prior_score: 2
  fallback: false
  seed_reason: 属于本分支的条件性方案；先核验正文的能力、语义和资源前提，再比较成本。
- target: planning.indexing.indexed_write_reduce
  match: []
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.indexing.indexed_write_reduce
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.task_ownership
  - constraint.duplicate_index_semantics
  - constraint.precision
  prior_score: 2
  fallback: false
  seed_reason: 属于本分支的条件性方案；先核验正文的能力、语义和资源前提，再比较成本。
- target: planning.indexing.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知条件保留现有合法方案并补资料。
---

# 索引访问与索引写入

按 family 与 workload 选择任务划分、所有权和组合方案；可同时进入多个分支。比较适用主方案与保守回退，C2 输出必要内容快照、参数和实现自由度。

- [Gather 输出所有权、行列分区与尾轴路径](templates/gather_output_owned.md)
- [索引写与重复目标：目标所有权、原子和分组归约](templates/indexed_write_reduce.md)
- [索引访问与索引写入：保守回退](fallback.md)

来源审读不等于目标硬件收益验证；不确定的能力或容量返回 needs_evidence，不能由模板代填。
