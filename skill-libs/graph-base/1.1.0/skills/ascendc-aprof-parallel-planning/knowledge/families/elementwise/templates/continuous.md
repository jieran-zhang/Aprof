---
schema_version: aprof.knowledge-record/v1
id: planning.elementwise.continuous
kind: template
version: 1.0.0
status: active
title: 连续输出分区与均衡尾块
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/elewise/tiling.md
  original_path: ops/ascendc-tiling-design/references/elewise/tiling.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 215
  sha256: sha256:40fd7187bf84f9c454fc5a53b0c5adc1e9594e6054901f21c518cae1ee3ad0ad
  excerpt_sha256: sha256:40fd7187bf84f9c454fc5a53b0c5adc1e9594e6054901f21c518cae1ee3ad0ad
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.elementwise
references: []
evidence_status: source_reviewed_not_benchmarked
---

# 连续输出分区与均衡尾块

## 适用域与算法骨架

各元素独立，输出连续；N=0 由宿主空张量分支处理。

把 N 个元素先按合法搬运粒度分成 Q 个块；各核分 q 或 q+1 块；核内按 UB tile 执行主循环与一个有效尾块。

## 任务所有权、归约与同步

每个输出块只有一个核写；不跨核归约。小 workload 比较较少核数，不能把低利用率直接当欠并行。

## 资源与成本公式

Q=ceil(N/alignmentElements)；q=Q//C，r=Q%C；UB_live=max_t Σ align(n_i(t)*s_i)*depth_i+tmp；所有量统一为字节。

容量、可用核数、API 临时区由当前平台与 SDK 核验。所有容量使用字节，保留对齐和同时存活区间；不得把上游 4KB、固定 tile 或核数当通用约束。

## 参数空间与替代方案

C∈[1,min(Q,availableCores)]；tile 满足容量和 API 限制；最小每核字节由实测成本决定。

较少核/更大 tile 与较多核/更小 tile 比较；fallback 为现有正确分区。

## 伪代码

```text
Q=ceil_div(N, alignmentElements); choose C<=min(Q, availableCores)
(q,r)=divmod(Q,C)
core c owns [c*q+min(c,r), (c+1)*q+min(c+1,r)) blocks
for each owned tile: load valid input -> compute -> write valid output
```

## 可复用 Ascend C 关键片段

```cpp
const uint64_t id = AscendC::GetBlockIdx();
const uint64_t blocks = q + (id < r ? 1 : 0);
const uint64_t beginBlock = id * q + (id < r ? id : r);
// beginBlock/blocks 用块为单位；映射元素后最后一块只处理 validCount。
// GetBlockIdx 片段用于 kernel；q/r 由 host 以溢出安全的整数算术计算。
```

片段省略工程与已声明的张量/变量，不是完整可运行算子；API 重载、作用域、别名和平台支持在 C3 核验。C2 冻结算法、所有权、合并顺序和数值语义；tile、局部 buffer/API 实现只在已声明容量/语义边界内调整。

## 验证与证据状态

来源审读完成，当前没有 NPU 性能验证。验证覆盖空/极小输入、对齐边界、尾块、多 task、特殊值和最大资源需求；完整正确性通过后才用统一计时协议比较。历史模板结果不构成当前性能承诺。

