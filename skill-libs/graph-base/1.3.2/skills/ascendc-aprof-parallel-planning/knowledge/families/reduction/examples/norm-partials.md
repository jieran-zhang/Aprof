---
schema_version: aprof.knowledge-record/v1
id: planning.reduction.example.norm-partials
kind: example
version: 1.1.0
status: active
title: norm-partials 历史案例：TensorList 成员的独立 partial 划分
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/wiki/norm-partials.md
  original_path: wiki/norm-partials.md
  revision: aprof-1.1.0-pre-governance:sha256:f01f135530a55dbaf0223a5e43453e07438aaf98edeebadd9731e82930afd3e3
  lines:
  - 1
  - 30
  sha256: sha256:f01f135530a55dbaf0223a5e43453e07438aaf98edeebadd9731e82930afd3e3
  excerpt_sha256: sha256:f01f135530a55dbaf0223a5e43453e07438aaf98edeebadd9731e82930afd3e3
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
seed_reason: 从已绑定的包内历史档案、索引和演化记录补足中文案例正文；保留原协议、失败与适用边界，不迁移历史性能资格。
parent: planning.reduction
references: []
evidence_status: source_reviewed_not_benchmarked
---

# norm-partials 历史案例：TensorList 成员的独立 partial 划分

## 背景、方法与规划边界

来源记录的是 910C/A3 上 `foreach_norm` 的条件性观察。每个 TensorList 成员可具有不同元素数、原 partial 数和核内工作量；先分别核算这些独立归约任务，再决定是否增加某些成员的 partial 分区。每个 partial 只处理自己声明的输入区间、写唯一 workspace 槽，最终归并保持该成员的 p、dtype、归约与广播语义。增加 partial 后要重新计算任务覆盖、合并成本、workspace 容量与最终输出所有者，不能仅凭核利用率低扩大分区。上述机制归属于 C2 并行规划；C3 只能在交付的分区、所有权和数值边界内选择实现。

历史候选把部分成员由每成员 4–5 个 block 扩到 48；相关组观察倍率约 7.52–10.08×，20-case 等权 suite 约 4.03×。原来已有 32/42/41 个 block 的 case 仅约 1.40/1.14/1.23×；已达 48 block 且 tiling 不变的 case3/9 约 1×。这些数字属于冻结输入、环境及历史计时协议，正式 verdict 为 `benchmark_specialized_gain`；48 不是通用核数或分派阈值。原档案没有列出完整 shape/dtype 清单，不能据此推断其他 TensorList 或精度域也适用。

## 已保留的独立复验失败

2026-10-14 在 910C/A3（Ascend910_9392）、CANN 9.0.0 上，baseline 与动态 partial 候选均通过原 20 个声明 case。参考计算沿用历史已核验的 32 个 PyTorch CPU 线程；首次 2 线程参考的 FP32 p=3 偏差及 FP64 复核记录均保留，未改生成器或容差。

预先声明的额外边界在 **baseline 的 FP16 p=0** 分组发现语义错误：MERE 为 0.1660，阈值 0.0009766，特殊值掩码也不一致。此前五个 p 分组的 baseline/candidate 共 160 个张量检查通过；失败分组的 candidate 及剩余分组按停止规则未运行。该回执的 `accuracy_failed` 表示额外语义范围未完成验收，不能写成动态 partial 候选的原 20 个 case 失败，也不能把 baseline 错误归因于 partial 改动。本次未计时、未 profile、未晋升。

## 适用边界与当前证据

新任务先验证每个成员的 p 特例、尾部、partial/finalize、特殊值和一般 fallback，再比较确有欠并行的候选与未改动基线；已充分并行的成员可保持原划分。历史原协议不等于当前 `single_role_l2_clean_task_v1`；1.3.0 仅审读这些记录，没有重新测量。演化记录初始为 deferred，独立复验为 rejected；该规则仍是 draft，未获得 `production_safe_gain`，950 未验证。scope=all 仅用于检索，不迁移硬件或 validated 资格。

来源：[原始历史档案](../../../../../../workflows/migration/archive/wiki/norm-partials.md)、同目录 index.json，以及 evolution.jsonl 中 `norm-partials-001-independent-20261014`。本正文已保留理解方法、反例与失败归因所需信息。
