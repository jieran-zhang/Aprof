---
schema_version: aprof.knowledge-record/v1
id: edge.support.serial.source
kind: edge
version: 1.0.0
status: active
title: symptom.source.serial_queue_or_event_order → problem.pipeline_serialization
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
  - 25
  - 31
  sha256: sha256:ef273a362b02e6e2409ca55e684d55d5f54cf539529acb9154319b996090dd1c
  excerpt_sha256: sha256:62288aede7e5517743c800cd8d289187c768492c7a9515ad7e626a96d3f58bb2
learning:
  weight: 1
tags: []
seed_reason: 1 分：“队列或事件顺序阻断独立阶段重叠”支持“搬运与计算串行”；源码形态只提供低特异性线索。
relation: supports
from: symptom.source.serial_queue_or_event_order
to: problem.pipeline_serialization
conditions: []
---

# symptom.source.serial_queue_or_event_order → problem.pipeline_serialization

关系为 supports，专家排序初值为 1。1 分：“队列或事件顺序阻断独立阶段重叠”支持“搬运与计算串行”；源码形态只提供低特异性线索。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
