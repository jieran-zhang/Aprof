---
schema_version: aprof.knowledge-record/v1
id: implementation.buffer-lifetime.example.ub-accumulator
kind: example
version: 1.1.0
status: active
title: UB 累加器消除逐 tile scalar 反馈的历史反例
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/wiki/ub-accumulator.md
  original_path: wiki/ub-accumulator.md
  revision: aprof-1.1.0-pre-governance:sha256:792df6e0d5f474660e4f29743f32a703cf794f795dc013d3e684f0d6bb876e3e
  lines:
  - 1
  - 23
  sha256: sha256:792df6e0d5f474660e4f29743f32a703cf794f795dc013d3e684f0d6bb876e3e
  excerpt_sha256: sha256:792df6e0d5f474660e4f29743f32a703cf794f795dc013d3e684f0d6bb876e3e
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
parent: implementation.buffer-lifetime
references: []
evidence_status: source_reviewed_not_benchmarked
---

# UB 累加器消除逐 tile scalar 反馈的历史反例

## 背景、方法与适用域

foreach_norm历史候选把GENERAL/ZERO分支的sum保留在FP32 UB running buffer中，试图减少逐tile的`GetValue`反馈。适用前提是原实现确有逐tile反馈，C2允许等价的局部状态驻留，而且原累计顺序、dtype与最终输出语义可以保持。INF分支仍走原scalar max/GetValue，不能作为该干预生效的正例。

原档案没有给出完整shape列表、具体tile、accumulator元素数、每个p值到分支的映射或源码片段。本页据此说明方法和失败边界，不补造这些细节，也不提供未经来源支持的具体norm公式。索引绑定910C/A3历史观察，可移植性未验证；其它硬件、SDK或norm实现须重新核验。

## 观察与未达条件的结果

在原20-case协议中，suite观察约1.0203×，正式95%加速下界约1.0196×，低于当时预登记1.03门槛，机器verdict为`attribution_uncertain`。FP32 case观察收益约1.2–1.7%，FP16/BF16约2.4–2.6%；原先预期下降的scalar time反而增加。INF case虽略快，但没有应用该UB累计改动，不能证明“消除GetValue”的机制。

这是保留的未达收益条件实验，不能改写成通用加速规则，也不能因小幅点估计更快就晋升。本页仅完成来源审读，没有当前候选正确性或新性能证据；原1.03门槛与旧置信区间协议不自动成为当前任务要求。

## 生命周期和实施检查

以下为本文归纳的迁移检查，不是原实验源码：给每个独立输出归约定义自己的running状态；在原语义规定的位置初始化，逐tile执行原来的更新，直到该输出最后一个有效tile完成后才最终化和释放。同一状态不能每tile重置，不能被下一输出或下一代槽提前覆盖。

若running buffer有R个FP32元素，其显式分配至少按`AlignUp(4*R,32)`字节计入，再加输入输出队列所有物理槽、原有转换区、归约scratch和API预留。R与物理份数必须来自当前C2/源码，原档案没有默认值。局部逻辑值不同时活跃，也不会使多个独立InitBuffer自动共享内存。Vector更新、后续读取与最终搬出的实际完成边必须保持。

验证多tile、单tile、最后短tile、多个独立输出连续运行、所有dtype和原oracle的特殊值域；GENERAL/ZERO与INF分开记录实际改动，未走干预的case不用于机制归因。性能与直接父本和当前完整case域比较；收益不足、UB压力增大或反馈未减少时恢复原路径。改变归约顺序、分核/输出所有者或累计精度须回C2。

原记录来源为`l1:lesson.foreach_norm.003`；[完整档案](../../../../../../workflows/migration/archive/wiki/ub-accumulator.md)及绑定索引/evolution保留原状态与协议。新应用须独立完成容量、完整正确性和当前正式计时，历史小幅观察不转为当前性能资格。
