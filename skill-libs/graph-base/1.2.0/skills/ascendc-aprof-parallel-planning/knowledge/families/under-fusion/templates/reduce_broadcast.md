---
schema_version: aprof.knowledge-record/v1
id: planning.under-fusion.reduce_broadcast
kind: template
version: 1.0.0
status: active
title: 归约后广播融合
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/reduction/ara-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ara-fullload.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 228
  sha256: sha256:621e3770b5ad87c0a852eb639fac7bfea7b7c231380d66414aa2ba06cd50a1e2
  excerpt_sha256: sha256:621e3770b5ad87c0a852eb639fac7bfea7b7c231380d66414aa2ba06cd50a1e2
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.under-fusion
references: []
evidence_status: source_reviewed_not_benchmarked
---

# 归约后广播融合

## 适用域与算法骨架

行内统计供同行广播/归一化使用，输出所有权能够保持在同一任务内。

先产生行统计，再对同一行/分块应用统计；完整行可驻留则单次读，否则比较二遍读取与保存中间值。

## 任务所有权、归约与同步

行 owner 同时拥有统计和输出；跨核 split 后必须等待统计合并才能广播。

## 资源与成本公式

UB=rowData+state+output+tmp；分段二遍读≈2*inputBytes；保存中间需计 workspace 读写。

容量、可用核数、API 临时区由当前平台与 SDK 核验。所有容量使用字节，保留对齐和同时存活区间；不得把上游 4KB、固定 tile 或核数当通用约束。

## 参数空间与替代方案

行 tile、统计状态、是否二遍、融合 affine/activation。

跨行依赖或容量不满足时保留归约+广播两个阶段。

## 伪代码

```text
owner loads row/chunk and computes local statistics
if cross-task reduction: finish the declared merge first
reuse resident row or reread valid row chunks
apply statistic/affine transform -> write owned output
```

## 可复用 Ascend C 关键片段

```cpp
// mean/std 已依照原数值语义计算；scale 可来自归约输出。
AscendC::Muls(outLocal, centeredLocal, invStd, validCount);
// epsilon 加在 variance 还是 sqrt 后必须与 oracle 一致。
```

片段省略工程与已声明的张量/变量，不是完整可运行算子；API 重载、作用域、别名和平台支持在 C3 核验。C2 冻结算法、所有权、合并顺序和数值语义；tile、局部 buffer/API 实现只在已声明容量/语义边界内调整。

## 验证与证据状态

来源审读完成，当前没有 NPU 性能验证。验证覆盖空/极小输入、对齐边界、尾块、多 task、特殊值和最大资源需求；完整正确性通过后才用统一计时协议比较。历史模板结果不构成当前性能承诺。

