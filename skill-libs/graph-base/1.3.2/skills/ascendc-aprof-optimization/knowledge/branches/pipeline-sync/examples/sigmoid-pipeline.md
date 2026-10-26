---
schema_version: aprof.knowledge-record/v1
id: implementation.pipeline-sync.example.sigmoid-pipeline
kind: example
version: 1.1.0
status: active
title: sigmoid 两槽历史观察与队列语义纠偏
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/wiki/sigmoid-pipeline.md
  original_path: wiki/sigmoid-pipeline.md
  revision: aprof-1.1.0-pre-governance:sha256:e41563e1e12e9f4c13c116aae042f3cffaefb8011fbded70f34cd350ea8bf7f6
  lines:
  - 1
  - 50
  sha256: sha256:e41563e1e12e9f4c13c116aae042f3cffaefb8011fbded70f34cd350ea8bf7f6
  excerpt_sha256: sha256:e41563e1e12e9f4c13c116aae042f3cffaefb8011fbded70f34cd350ea8bf7f6
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
- implementation.pipeline-sync.example.prefetch-boundaries
evidence_status: source_reviewed_not_benchmarked
---

# sigmoid 两槽历史观察与队列语义纠偏

## 历史事实保留

[完整历史记录](../../../../../../workflows/migration/archive/wiki/sigmoid-pipeline.md)绑定旧索引和evolution日志，记录了原协议、通过项及停止原因，不能以本页覆盖。初轮20-case normal/swapped task-sum suite约1.303×只是历史观察，末次A/A存在精度不足cell及CV问题；case20的MTE2 active time还升约15.6%，不能将总时下降全部解释为重叠。

2026-10-14在910C/A3（9392）、CANN9.0.0的独立复验中，两实现各通过声明20 case及额外57 case，正式样本观察到几何平均1.317478×。但后置同源A/A的case8一角色跨会话漂移3.563358%，超过预登记2%门限，流程停止；未采机制profile、未晋升。第二轮只运行baseline对自身控制，仍有角色偏差，未重跑候选A/B。2026-10-15 Task v5在审查预算处退出，未构建、未采集硬件数据；这是流程拒绝，不能写成流水正确性/性能反例。

## 从案例抽取的实现契约

旧叙述“队列深度1→2”不足以确定实际启用方式。当前审读S1明确区分：`TQue<position,depth>`的depth限制连续未DeQue数量，`InitBuffer(queue,num,bytes)`的num决定物理buffer数。重用此案例必须查看实际源码两处参数、队列最大存活项和输出回收位置，不能把历史文字改写成“修改任意depth参数即可提速”。

若既定sigmoid语义是`1/(1+exp(-x))`，C3仍须保留原来的中间dtype、溢出/饱和和特殊值处理；引入float中间计算、调整近似或用其它激活函数不是流水变换。将多个Vector操作留在UB属于融合/驻留，增加输入输出物理槽属于存储策略，预取属于排程，评估时分开列出实际改变。

```text
对每个tile:
    input槽: MTE2写 -> V逐步读取 -> 最后一次读完后可复用
    output槽: V写 -> MTE3读 -> 搬出读完后可复用
    nextTile = tile+1 只有在 nextTile<tileCount 时才形成预取地址
最后一tile: 不预取；必须写出最后结果并收尾
```

此为本文归纳，不是历史代码的逐行重现。两类槽的字节预算为`dIn*align(nIn*eIn,aIn)+dOut*align(nOut*eOut,aOut)+scratch+API预留`，不能只算输入副本；若输入、输出同一GM对象，还要证明下一tile读取与上一tile写出不重叠。

## 当前使用边界

C2必须先冻结tile、任务所有权、dtype和允许的缓冲改动；C3按[流水配方](../recipes/pipeline.md)补齐队列/事件和drain。若需要改变核划分、融合region或内存拓扑，返回C2。零/单tile、两tile、非整tile、奇数tile及跨槽回卷为必要正确性边界；新结果使用当前统一计时协议，历史置信区间和旧A/A门限不直接成为本轮协议。

本页没有本轮新测量；1.317478×不构成当前候选资格。先通过完整正确性和当前控制实验，再判断Task Duration，最后用timeline验证是否发生预期重叠。

## 固定来源与证据级别

- S1：[ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md](../../../sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md)，行 40–249；修订 `41377d0a442cd5b1c2356874873a3dda591c6633`。

来源事实、本文推导与待验证项在正文分别标注。冻结源码及仓库许可证随包保存；本次仅完成审读，未在目标 SDK 构建，未运行 NPU 正确性或性能测量。源码存在不代表当前 shape 已分派到该路径，任何收益都须由当前候选的完整正确性、Task Duration 与针对性 timeline 证明。
