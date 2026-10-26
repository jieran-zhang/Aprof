---
schema_version: aprof.knowledge-record/v1
id: implementation.pipeline-sync.example.prefetch-boundaries
kind: example
version: 1.1.0
status: active
title: 预取边界、直接父本与算术反例归属
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/wiki/prefetch-boundaries.md
  original_path: wiki/prefetch-boundaries.md
  revision: aprof-1.1.0-pre-governance:sha256:24e01b7a1c612ea1f5323fce9e5e54c4a2ef6aaa768df6748013c2981152d997
  lines:
  - 1
  - 32
  sha256: sha256:24e01b7a1c612ea1f5323fce9e5e54c4a2ef6aaa768df6748013c2981152d997
  excerpt_sha256: sha256:24e01b7a1c612ea1f5323fce9e5e54c4a2ef6aaa768df6748013c2981152d997
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
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md
  original_path: ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 40
  - 249
  sha256: sha256:142cc0055136ff3bc203672f4c4365cf4f09b41a175a7bfa1d89f3df3b2500ae
  excerpt_sha256: sha256:28c3372885746552f8fc7c07805f7f715efc2c32ef72a3a0155dcbd49a0967a3
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: implementation.pipeline-sync
references:
- implementation.pipeline-sync.pipeline
- implementation.pipeline-sync.fallback
evidence_status: source_reviewed_not_benchmarked
---

# 预取边界、直接父本与算术反例归属

## 历史证据与不能越过的结论

[完整历史记录](../../../../../../workflows/migration/archive/wiki/prefetch-boundaries.md)保留原协议、shape、dtype、原失败及evolution事件。masked_scale的四个PMU sentinel中MTE2 stall下降，但20-case任务时间异质，case11和case20有点估计回退。exp候选相对原始baseline较快，同时继承了父本tile放大；相对直接父本，case8小回退，13个case/config点估计低于1。因此不能把“更大tile的收益”和“预取的增量收益”合并为预取结论，也不能将历史倍率连乘。

2026-10-14在910C/A3、CANN9.0.0，masked_scale baseline和候选各通过声明20 case。第一项额外边界`shape=[33], FP16 x=65504, int8 mask=2, scale=0.5`中，原PyTorch oracle按FP16中间乘法溢出，期望33个+Inf；baseline在FP32中计算，得到33个65504，特殊值mask检查失败。该差异baseline已存在，不能归因于预取。按计划停止，候选尚未运行这一边界及其余60个额外边界，没有后续A/A、候选计时或PMU结论；原算术与verifier未修改。

## 预取成立的依赖与容量

当前task存在独立的next tile，MTE2有可隐藏间隙，双槽加scratch/API预留不超UB，而且下一个地址合法时，才考虑提前搬入。输入第i槽的有效生命期从CopyIn(i)发起至Vector最后读取完成；输出槽持续到MTE3最后读取完成。增加物理块不能消除对旧代的等待。

```text
tileCount = ceil(totalElements/tileElements)
for i in [0,tileCount):
    valid_i = min(tileElements,totalElements-i*tileElements)
    if i+1 < tileCount:                      # 先判边界，再算地址/发DMA
        nextOff = (i+1)*tileElements
        nextValid = min(tileElements,totalElements-nextOff)
        prefetch(nextOff,nextValid,free_slot) # 契约伪代码，需映射到队列或事件
    consume_current_and_write_valid_output(i,valid_i)
drain_all_submitted_output()
```

上段未规定必然先预取再Compute。若depth=1且当前输入尚未DeQue，再EnQue下一输入会超出队列契约；可以先DeQue/发当前Compute再发next，或使用目标SDK允许的更深队列并重算预算。S1的示意排程不应被当作可原样粘贴的工程。对只有一个tile的case不发预取；分块改变后尾块、DMA字节和最终输出有效长度须同步更新。

## 如何获得可归因的当前结果

C2固定原oracle、dtype、中间舍入、tile及允许自由度。C3只落实其允许的预取和生命周期；发现既有语义问题时保留反例并交回对应决策，不把修oracle或换float计算混入纯预取候选。若同时改变tile，至少分别记录相对直接父本与原始baseline的结果，不能借父本收益掩盖预取回退。

正确性覆盖0/1/2 tile、长度为tile±1、奇数tile、多次回卷和特殊值。性能使用当前协议的完整case集；PMU stall仅是机制线索，仍需Task Duration和timeline支撑。可隐藏间隙不足、UB挤压导致tile过小、标量控制/同步增加、in-place存在跨tile重叠时，保留单槽或关闭预取的正确路径。需要改task拆分或数据拓扑时由C2重规划。

## 固定来源与证据级别

- S1：[ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md](../../../sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md)，行 40–249；修订 `41377d0a442cd5b1c2356874873a3dda591c6633`。

来源事实、本文推导与待验证项在正文分别标注。冻结源码及仓库许可证随包保存；本次仅完成审读，未在目标 SDK 构建，未运行 NPU 正确性或性能测量。源码存在不代表当前 shape 已分派到该路径，任何收益都须由当前候选的完整正确性、Task Duration 与针对性 timeline 证明。
