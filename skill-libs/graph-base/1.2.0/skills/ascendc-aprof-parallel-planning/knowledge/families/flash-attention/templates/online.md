---
schema_version: aprof.knowledge-record/v1
id: planning.flash-attention.online
kind: template
version: 1.0.0
status: active
title: Task 并行、KV streaming 与 online softmax
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/flashattention/design.md
  original_path: ops/ascendc-tiling-design/references/flashattention/design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 634
  sha256: sha256:83ed347947ce330ed2940beb797be67fdc3cc30d60b9cf376d81711d76ab09cb
  excerpt_sha256: sha256:83ed347947ce330ed2940beb797be67fdc3cc30d60b9cf376d81711d76ab09cb
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.flash-attention
references: []
evidence_status: source_reviewed_not_benchmarked
---

# Task 并行、KV streaming 与 online softmax

## 适用域与算法骨架

MHA/GQA 等子族、mask、scale、head 映射已确认；适合按 batch/head/Qblock 分任务。

每个 Qblock 顺序流过 KV chunks；保持 m,l,O 状态；新块最大值 m′=max(m,max(scores))，α=exp(m−m′)，更新 l′=αl+Σexp(scores−m′)，O′=αO+P V。最终 O/l。

## 任务所有权、归约与同步

task 独占 Q 输出；KV 可共享只读。默认 s2 在 task 内顺序推进，避免无合并的跨核状态更新。

## 资源与成本公式

状态 O 大小=Br*D*sAcc，m/l=2*Br*sAcc；UB/L1/L0 逐层预算；容量不够时缩 Br 或按 D/row 分块并计 workspace 流量。

容量、可用核数、API 临时区由当前平台与 SDK 核验。所有容量使用字节，保留对齐和同时存活区间；不得把上游 4KB、固定 tile 或核数当通用约束。

## 参数空间与替代方案

Br/Bc/Dchunk、KV 长度、AIC/AIV 比例、状态驻留位置。

容量允许可驻留 O；容量不足才评估 streaming/workspace；不照搬上游一律搬 O 到 GM 的规则。

## 伪代码

```text
task owns (batch,head,Qblock); initialize m=-inf,l=0,O=0
for valid KV chunk:
  scores=Q*K^T*scale+mask; mNew=max(m,rowMax(scores))
  handle all-masked rows; alpha=exp(m-mNew); P=exp(scores-mNew)
  O=alpha*O+P*V; l=alpha*l+rowSum(P); m=mNew
output=O/l with explicit l==0 semantics
```

## 可复用 Ascend C 关键片段

```cpp
// online rescale 中一行 O 的更新片段，alpha 来自 max 的稳定更新。
AscendC::Muls(oldOLocal, oldOLocal, alpha, validD);
AscendC::Add(newOLocal, oldOLocal, pvLocal, validD);
// 全 mask 行须显式分支，避免 exp(-inf - -inf) 产生 NaN。
```

片段省略工程与已声明的张量/变量，不是完整可运行算子；API 重载、作用域、别名和平台支持在 C3 核验。C2 冻结算法、所有权、合并顺序和数值语义；tile、局部 buffer/API 实现只在已声明容量/语义边界内调整。

## 验证与证据状态

来源审读完成，当前没有 NPU 性能验证。验证覆盖空/极小输入、对齐边界、尾块、多 task、特殊值和最大资源需求；完整正确性通过后才用统一计时协议比较。历史模板结果不构成当前性能承诺。

