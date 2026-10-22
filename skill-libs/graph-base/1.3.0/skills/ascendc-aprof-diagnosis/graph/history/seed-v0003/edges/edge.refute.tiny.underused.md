---
schema_version: aprof.knowledge-record/v1
id: edge.refute.tiny.underused
kind: edge
version: 1.0.0
status: active
title: symptom.workload.tiny_or_overhead_limited → problem.underused_task_parallelism
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/ai-core-utilization-diagnosis-metrics.md
  original_path: skills/aprof/diagnosis/references/ai-core-utilization-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:0a70b21924e9ba29d6a75280699009b1f46afd4e9bd0fd3eb9880d592105e475
  lines:
  - 121
  - 125
  sha256: sha256:0a70b21924e9ba29d6a75280699009b1f46afd4e9bd0fd3eb9880d592105e475
  excerpt_sha256: sha256:0544abe69ef28224b6c0df320bf46cc91e9bdb528909026dfebdff419c44efa9
learning:
  weight: 3
tags: []
seed_reason: 3 分：已核验的“工作量不足以摊薄固定启动开销”明确反对“已有独立任务并行度未暴露”；字段缺失不能触发此反证。
relation: refutes
from: symptom.workload.tiny_or_overhead_limited
to: problem.underused_task_parallelism
conditions: []
---

# symptom.workload.tiny_or_overhead_limited → problem.underused_task_parallelism

关系为 refutes，专家排序初值为 3。3 分：已核验的“工作量不足以摊薄固定启动开销”明确反对“已有独立任务并行度未暴露”；字段缺失不能触发此反证。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
