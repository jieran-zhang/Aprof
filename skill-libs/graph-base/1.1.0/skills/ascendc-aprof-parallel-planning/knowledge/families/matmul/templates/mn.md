---
schema_version: aprof.knowledge-record/v1
id: planning.matmul.mn
kind: template
version: 1.0.0
status: active
title: MN 分块与 GMM 负载均衡
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/matmul/ascendc-api-gmm-tiling.md
  original_path: ops/ascendc-tiling-design/references/matmul/ascendc-api-gmm-tiling.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 313
  sha256: sha256:90d9b2c693a9fb876326157a618e383413c28cf660e8d4f92941a96b6c593cb1
  excerpt_sha256: sha256:90d9b2c693a9fb876326157a618e383413c28cf660e8d4f92941a96b6c593cb1
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.matmul
references: []
evidence_status: source_reviewed_not_benchmarked
---

# MN 分块与 GMM 负载均衡

## 适用域与算法骨架

MatMul/GMM，组形状和 layout 已知；优先从输出 MN 任务独立性建立基线。

tasks=Σg ceil(Mg/BM)*ceil(Ng/BN)；按任务估计的 K 工作量调度；K 在核内迭代，尾 M/N 保持有效长度。

## 任务所有权、归约与同步

一个 MN tile 的完整 K 由一个输出所有者完成；GMM 任务必须带 group 和独立基址。

## 资源与成本公式

L0A=BM*BK*sA，L0B=BK*BN*sB，L0C=BM*BN*sAcc；L1 计入所有槽与对齐；比较 max_core_work。

容量、可用核数、API 临时区由当前平台与 SDK 核验。所有容量使用字节，保留对齐和同时存活区间；不得把上游 4KB、固定 tile 或核数当通用约束。

## 参数空间与替代方案

BM/BN/BK、任务顺序、核数、A/B 驻留；硬件 fragment 与 row stride 由平台核实。

小 MN 长 K 转 split-K；末轮不均衡比较进一步 MN 切分；fallback 通用 MatMul。

## 伪代码

```text
tasks = concatenate group-specific (mTile,nTile) grids
schedule output tiles by estimated K work
for task: for kTile: load A/B -> accumulate C in declared precision
final owner writes only valid M,N
```

## 可复用 Ascend C 关键片段

```cpp
// 核内任务枚举；任务表的组/输出所有权由 C2 给出。
for (uint64_t task = AscendC::GetBlockIdx(); task < totalTasks; task += usedCores) {
    // 解码 group/m/n；执行当前 SDK 已核验的 MatMul 接口；仅写有效 M/N。
}
```

片段省略工程与已声明的张量/变量，不是完整可运行算子；API 重载、作用域、别名和平台支持在 C3 核验。C2 冻结算法、所有权、合并顺序和数值语义；tile、局部 buffer/API 实现只在已声明容量/语义边界内调整。

## 验证与证据状态

来源审读完成，当前没有 NPU 性能验证。验证覆盖空/极小输入、对齐边界、尾块、多 task、特殊值和最大资源需求；完整正确性通过后才用统一计时协议比较。历史模板结果不构成当前性能承诺。

