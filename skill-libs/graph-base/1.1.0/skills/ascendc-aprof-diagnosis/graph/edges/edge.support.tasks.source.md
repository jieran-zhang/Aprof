---
schema_version: aprof.knowledge-record/v1
id: edge.support.tasks.source
kind: edge
version: 1.0.0
status: active
title: symptom.source.fixed_or_undersubscribed_tasking → problem.underused_task_parallelism
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/source-hypothesis-routing.md
  original_path: skills/aprof/diagnosis/references/source-hypothesis-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:ef273a362b02e6e2409ca55e684d55d5f54cf539529acb9154319b996090dd1c
  lines:
  - 19
  - 23
  sha256: sha256:ef273a362b02e6e2409ca55e684d55d5f54cf539529acb9154319b996090dd1c
  excerpt_sha256: sha256:90ed70d6819b14facbb6306ad722df9b8b94026bcc2146415b85b898410a4264
learning:
  weight: 1
tags: []
seed_reason: 1 分：“任务或 blockDim 不随有效工作量扩展”支持“已有独立任务并行度未暴露”；源码形态只提供低特异性线索。
relation: supports
from: symptom.source.fixed_or_undersubscribed_tasking
to: problem.underused_task_parallelism
conditions: []
---

# symptom.source.fixed_or_undersubscribed_tasking → problem.underused_task_parallelism

关系为 supports，专家排序初值为 1。1 分：“任务或 blockDim 不随有效工作量扩展”支持“已有独立任务并行度未暴露”；源码形态只提供低特异性线索。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
