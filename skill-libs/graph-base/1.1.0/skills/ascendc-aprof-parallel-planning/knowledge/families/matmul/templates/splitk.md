---
schema_version: aprof.knowledge-record/v1
id: planning.matmul.splitk
kind: template
version: 1.0.0
status: active
title: split-K/StreamK 与部分结果合并
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/matmul/streamk_design.md
  original_path: ops/ascendc-performance-best-practices/reference/matmul/streamk_design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 374
  sha256: sha256:7fbd5d30ca6333991a4d9cf8d30c7e0468dd9ed4d09d2a2f0abe6ba8d934edb9
  excerpt_sha256: sha256:7fbd5d30ca6333991a4d9cf8d30c7e0468dd9ed4d09d2a2f0abe6ba8d934edb9
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.matmul
references: []
evidence_status: source_reviewed_not_benchmarked
---

# split-K/StreamK 与部分结果合并

## 适用域与算法骨架

MN 任务不足或末轮空核且 K 足够长；部分结果可稳定合并。

把部分 MN tile 的 K 拆成 S 段；每段写高精度 partial；全部完成后由合并阶段求和并执行一次 epilogue。

## 任务所有权、归约与同步

唯一槽位键 (group,mTile,nTile,kSplit)；最终输出只写一次；bias/activation 不能每个 split 重复施加。

## 资源与成本公式

workspace=splitTiles*S*BM*BN*sAcc；额外流量约 2*workspace；只有节省的关键路径大于合并/同步/启动成本才采用。

容量、可用核数、API 临时区由当前平台与 SDK 核验。所有容量使用字节，保留对齐和同时存活区间；不得把上游 4KB、固定 tile 或核数当通用约束。

## 参数空间与替代方案

S、全量 split 或末轮 split、合并 tile、partial dtype。

短 K、workspace 受限或精度不通过回退 MN；不复用上游固定 K 阈值。

## 伪代码

```text
map task -> (group,mTile,nTile,kSplit)
compute partial C over this K interval
write unique partial slot -> signal completion
merge owner waits for all splits -> sum -> one epilogue -> one output write
```

## 可复用 Ascend C 关键片段

```cpp
// 合并已经同步完成的 partial，保留高精度到最后一次 cast。
AscendC::Add(accLocal, accLocal, partLocal, validCount);
// 合并完全部 S 段才加 bias、激活、转换输出 dtype。
```

片段省略工程与已声明的张量/变量，不是完整可运行算子；API 重载、作用域、别名和平台支持在 C3 核验。C2 冻结算法、所有权、合并顺序和数值语义；tile、局部 buffer/API 实现只在已声明容量/语义边界内调整。

## 验证与证据状态

来源审读完成，当前没有 NPU 性能验证。验证覆盖空/极小输入、对齐边界、尾块、多 task、特殊值和最大资源需求；完整正确性通过后才用统一计时协议比较。历史模板结果不构成当前性能承诺。

