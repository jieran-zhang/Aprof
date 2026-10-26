---
schema_version: aprof.knowledge-record/v1
id: implementation.memory-transfer.example.tile-amortization
kind: example
version: 1.1.0
status: active
title: tile 放大与每 tile 设置开销的历史观察
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/wiki/tile-amortization.md
  original_path: wiki/tile-amortization.md
  revision: aprof-1.1.0-pre-governance:sha256:67e8af670f58f444b5ff228c1dc8cafbd3c11ce278bc385591f673368f6eb2f4
  lines:
  - 1
  - 31
  sha256: sha256:67e8af670f58f444b5ff228c1dc8cafbd3c11ce278bc385591f673368f6eb2f4
  excerpt_sha256: sha256:67e8af670f58f444b5ff228c1dc8cafbd3c11ce278bc385591f673368f6eb2f4
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
parent: implementation.memory-transfer
references: []
evidence_status: source_reviewed_not_benchmarked
---

# tile 放大与每 tile 设置开销的历史观察

## 背景、方法与适用域

历史记录把 exp、mish 和 foreach_addcdiv_scalar 的 tile 放大实验放在一起，用于说明同一候选方向：在既定并行划分内，每核有多个 tile，重复搬运发射和标量设置可能随 tile 次数增加。实现保留算法、任务与输出所有权，仅在 C2 允许范围内增大 tile，并同步重算 UB、队列槽、循环数和动态尾部。不能把三个算子的结果合并成一个效应。

原实验的 tileElements 单位为元素：exp 从4096增到8192，mish从2048增到4096，addcdiv从2048增到4096，随后还探索6144。原综合档案没有给出 mish/addcdiv 的完整 shape、dtype、源码和所有容量参数，不能凭本页补造可直接复制的 kernel 配置。索引将这些观察绑定为910C/A3历史证据；具体工具链仍以各原实例为准，950未验证。

## 观察、失败和资格

原协议下，exp与mish各自20-case task-sum suite的描述性观察约为1.18×与1.23×；addcdiv六case搜索约1.20×。addcdiv的MTE2指令次数下降近半，但case14绝对MTE2时间只降约0.9%，case20的CV约10%；继续增到6144后资源占用和收益又变化。这些结果不证明“调用减少一半，时间也减少一半”，exp/mish当时的A/A、CV或资源控制也不充分。

2026-10-14对exp的独立复验使用910C/A3（9392）、CANN9.0.0：baseline与tile8192候选均通过20个声明case和42个额外边界，但前置同源A/A的case3、9角色偏差为2.4353%、3.6243%，超过原先2%上限。因此候选A/B正式计时尚未启动，不能从这次停止推断tile优化加速或回退。

本综合条目的历史状态仍为draft/deferred。exp后来在其独立条目完成了限定实现的验收，详见`implementation.tiling-tail.example.exp-tile8192`；那次资格仅属于exp/910C A3/CANN9.0.0，不使mish、addcdiv或本综合规则同时获得资格。本页只做档案审读，没有当前协议下的新性能证据。

## 可复用的实现检查

下面是本文归纳的检查方法，不是原实验逐行代码：固定本任务有效量L元素、tile容量T元素，循环数为`L/T+(L%T!=0)`；每轮只搬运和计算`min(T,L-offset)`个有效元素。增大T后，按真实输入/输出dtype、物理槽数、转换区、scratch及API内部预留求静态UB总分配，不能只统计当前活跃的逻辑值。

先检查零/单tile、tile±1、最大shape、最后核和非整齐分区，保留每核区间及尾部所有权。若大tile超容量、迫使关闭已有双缓冲、增加寄存器/Vector成本或使Task劣化，在C2自由度内恢复原tile。改变任务划分、输出所有者或算法须回C2；8192、4096、6144都不是通用最优值。

历史协议、source_keys和失败记录见[完整档案](../../../../../../workflows/migration/archive/wiki/tile-amortization.md)及其绑定索引/evolution。新应用使用当前协议并独立完成审查、构建、完整正确性与比较，历史task-sum倍率不迁移为当前候选资格。
