---
schema_version: aprof.knowledge-record/v1
id: planning.moe-routing
kind: router
version: 1.0.0
status: active
title: MoE 路由与结果回收组合
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_finalize_routing/README.md
  original_path: moe/moe_finalize_routing/README.md
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 111
  sha256: sha256:86f63ff730adb5c47fb9d3943d5b1bcbf0c77e9be9bef09a6562ebff9776251d
  excerpt_sha256: sha256:86f63ff730adb5c47fb9d3943d5b1bcbf0c77e9be9bef09a6562ebff9776251d
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_finalize_routing/docs/aclnnMoeFinalizeRouting.md
  original_path: moe/moe_finalize_routing/docs/aclnnMoeFinalizeRouting.md
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 25
  - 176
  sha256: sha256:d1262d33987e3de7c383f188fd2ba14a26d5e8d0c80c9e135868b89ff6209309
  excerpt_sha256: sha256:0dc23e648ece7696d7ad9cefd2b66aaf6f178b270cc3625a2d128edc1ab94ffd
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_finalize_routing/op_host/moe_finalize_routing_tiling.cpp
  original_path: moe/moe_finalize_routing/op_host/moe_finalize_routing_tiling.cpp
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 631
  sha256: sha256:99719b9d340b9ea251b70ae4ab566218799f5f76bcf90c89fe085d4fe1f2a7b5
  excerpt_sha256: sha256:99719b9d340b9ea251b70ae4ab566218799f5f76bcf90c89fe085d4fe1f2a7b5
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_finalize_routing/op_kernel/moe_finalize_routing_fp_db.h
  original_path: moe/moe_finalize_routing/op_kernel/moe_finalize_routing_fp_db.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 267
  - 397
  sha256: sha256:deb901b7427aae6ec4e65ac429e7e8b1852934b21ae7035b0a0fbab4bbff4ecc
  excerpt_sha256: sha256:df75554c19b8f81f6ddd0e4c488b0130e071953a3a2020f2e6f2ed40880d5e6a
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_finalize_routing/op_kernel/moe_finalize_routing_bf16.h
  original_path: moe/moe_finalize_routing/op_kernel/moe_finalize_routing_bf16.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 274
  - 419
  sha256: sha256:7842e5c84291ad0783eda0bbb52575db17b4c6139aa75ca1dc94bd74656bfa8c
  excerpt_sha256: sha256:bca6438616541c2a766e783efa910414ae11c3db7d9dd2c46bca1d3973acdda8
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_finalize_routing/op_kernel/moe_finalize_routing_fp_cuth.h
  original_path: moe/moe_finalize_routing/op_kernel/moe_finalize_routing_fp_cuth.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 457
  sha256: sha256:fbc870846fc337335f2eb571cac2668aef0add86a231be6bc664c02522500f65
  excerpt_sha256: sha256:fbc870846fc337335f2eb571cac2668aef0add86a231be6bc664c02522500f65
learning: {}
tags: []
seed_reason: 固定开源修订审读并以中文提炼；未做性能训练或硬件收益验证。
parent: planning.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: planning.moe-routing.finalize_weighted_reduce
  match: []
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.moe-routing.finalize_weighted_reduce
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.task_ownership
  - constraint.index_mapping
  - constraint.workspace_ownership
  prior_score: 2
  fallback: false
  seed_reason: 属于本分支的条件性方案；先核验正文的能力、语义和资源前提，再比较成本。
- target: planning.moe-routing.route_sort_gather
  match: []
  exclude:
  - field: excluded_templates
    op: contains
    value: planning.moe-routing.route_sort_gather
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.task_ownership
  - constraint.index_mapping
  - constraint.workspace_ownership
  prior_score: 2
  fallback: false
  seed_reason: 属于本分支的条件性方案；先核验正文的能力、语义和资源前提，再比较成本。
- target: planning.moe-routing.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知条件保留现有合法方案并补资料。
---

# MoE 路由与结果回收组合

按 family 与 workload 选择任务划分、所有权和组合方案；可同时进入多个分支。比较适用主方案与保守回退，C2 输出必要内容快照、参数和实现自由度。

- [MoE Finalize：token/hidden owner 的 Gather 加权归约](templates/finalize_weighted_reduce.md)
- [MoE 路由：全载或 Sort/Merge/Gather 阶段组合](templates/route_sort_gather.md)
- [MoE 路由与结果回收组合：保守回退](fallback.md)

来源审读不等于目标硬件收益验证；不确定的能力或容量返回 needs_evidence，不能由模板代填。
