---
schema_version: aprof.knowledge-record/v1
id: planning.flash-attention.splitkv
kind: template
version: 1.0.0
status: active
title: Decode split-KV 与稳定合并
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

# Decode split-KV 与稳定合并

## 适用域与算法骨架

decode 独立 Q task 很少而 KV 很长；合并与 workspace 成本可接受。

各 split 计算未归一化 (mi,li,Oi)；仅在非空 partial 上取 M=max_i mi，L=Σexp(mi−M)li，O=Σexp(mi−M)Oi/L；若存的是归一化 Oi，必须额外乘 li。

## 任务所有权、归约与同步

槽位键 (task,kvSplit) 唯一；等待所有 partial 完成后唯一合并者写 O。

## 资源与成本公式

workspace≈tasks*S*(Br*D+2*Br)*sAcc；并行缩短的 KV 时间必须覆盖 partial 写读与合并成本。

容量、可用核数、API 临时区由当前平台与 SDK 核验。所有容量使用字节，保留对齐和同时存活区间；不得把上游 4KB、固定 tile 或核数当通用约束。

## 参数空间与替代方案

S、KV chunk、partial dtype、merge tile、空 split 策略。

空 split 用 m=-inf、l=0、O=0，并在合并时跳过 l=0 的 partial；所有 partial 空/全 mask 时直接按 oracle 返回，不能计算 exp(-inf−-inf)；收益不足回退 task streaming。

## 伪代码

```text
each (task,split) independently computes unnormalized (mi,li,Oi)
store partials in unique workspace slots and complete producers
ignore empty partials (m=-inf,l=0,O=0); if all empty, take oracle branch
merge owner: M=max(mi); L=sum(exp(mi-M)*li)
O=sum(exp(mi-M)*Oi)/L; handle empty/all-masked splits
write each output exactly once
```

## 可复用 Ascend C 关键片段

```cpp
// 局部 O 未归一化的合并：weight=exp(mi-M)。
AscendC::Muls(partLocal, partLocal, weight, validD);
AscendC::Add(accLocal, accLocal, partLocal, validD);
// 同时累计 weight*li，最后统一除 L；L==0 按 mask/特殊值契约处理。
```

片段省略工程与已声明的张量/变量，不是完整可运行算子；API 重载、作用域、别名和平台支持在 C3 核验。C2 冻结算法、所有权、合并顺序和数值语义；tile、局部 buffer/API 实现只在已声明容量/语义边界内调整。

## 验证与证据状态

来源审读完成，当前没有 NPU 性能验证。验证覆盖空/极小输入、对齐边界、尾块、多 task、特殊值和最大资源需求；完整正确性通过后才用统一计时协议比较。历史模板结果不构成当前性能承诺。

