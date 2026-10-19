---
schema_version: aprof.knowledge-record/v1
id: planning.reduction.example.norm-p-specialization
kind: example
version: 1.0.0
status: active
title: norm-p-specialization 历史案例
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/wiki/norm-p-specialization.md
  original_path: wiki/norm-p-specialization.md
  revision: aprof-1.1.0-pre-governance:sha256:3fe41d83888487eb55920e0673f59530e94b2056cc2cee88bd3fd4937d7e0ee2
  lines:
  - 1
  - 26
  sha256: sha256:3fe41d83888487eb55920e0673f59530e94b2056cc2cee88bd3fd4937d7e0ee2
  excerpt_sha256: sha256:3fe41d83888487eb55920e0673f59530e94b2056cc2cee88bd3fd4937d7e0ee2
- path: workflows/migration/archive/wiki/index.json
  original_path: wiki/index.json
  revision: aprof-1.1.0-pre-governance:sha256:dca7200b4542b6e6e54e51d956407a67d3a7b300e255cab77ac97e6932294c0b
  lines:
  - 1
  - 388
  sha256: sha256:dca7200b4542b6e6e54e51d956407a67d3a7b300e255cab77ac97e6932294c0b
  excerpt_sha256: sha256:dca7200b4542b6e6e54e51d956407a67d3a7b300e255cab77ac97e6932294c0b
- path: workflows/migration/archive/wiki/evolution.jsonl
  original_path: wiki/evolution.jsonl
  revision: aprof-1.1.0-pre-governance:sha256:080bde3fc3eb67514d9075453b78f20c1d12dbd48f6db4f48407187da65917f4
  lines:
  - 1
  - 15
  sha256: sha256:080bde3fc3eb67514d9075453b78f20c1d12dbd48f6db4f48407187da65917f4
  excerpt_sha256: sha256:080bde3fc3eb67514d9075453b78f20c1d12dbd48f6db4f48407187da65917f4
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.reduction
references: []
evidence_status: source_reviewed_not_benchmarked
---

# norm-p-specialization 历史案例

此案例仅用于提出候选和识别失败边界；原始记录见[完整历史案例](../../../../../../workflows/migration/archive/wiki/norm-p-specialization.md)，其中硬件/工具链、shape、dtype、原协议、通过/拒绝记录和后续演化均保留原文。来源元数据同时绑定旧索引与 evolution 日志。

本轮没有按 single_role_l2_clean_task_v1 重新测量。历史 validated 只限原实例和协议，不会自动转为当前候选资格。采用时 C2/C3 必须说明相同与不同的前提，并保留原失败记录。

exp 的 tile8192 案例不能推广为通用 tile；预取案例须防止末轮越界；norm 案例须区分 p 特例、partial/广播开销和原始数值语义。

