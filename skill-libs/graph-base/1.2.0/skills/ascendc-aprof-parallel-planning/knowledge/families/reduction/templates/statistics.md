---
schema_version: aprof.knowledge-record/v1
id: planning.reduction.statistics
kind: template
version: 1.0.0
status: active
title: 方差、Norm 与 Softmax 数值状态
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/reduction/alg-welford.md
  original_path: ops/ascendc-tiling-design/references/reduction/alg-welford.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 74
  sha256: sha256:6c8e784dad546cb1caa07867596721b3d1c8ecc746396df5392054f44d84eb28
  excerpt_sha256: sha256:6c8e784dad546cb1caa07867596721b3d1c8ecc746396df5392054f44d84eb28
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.reduction
references: []
evidence_status: source_reviewed_not_benchmarked
---

# 方差、Norm 与 Softmax 数值状态

## 适用域与算法骨架

分段统计或归一化；必须明确输出是方差、std、norm 还是 softmax。

方差用 (n,mean,M2) 合并；norm 先按 p 特例/绝对值变换归约后还原；softmax 使用 max 平移后求和，禁止把三者当普通求和。

## 任务所有权、归约与同步

每个输出状态有唯一合并者；输出归一化需要再次访问输入时比较二遍读取与片上保留。

## 资源与成本公式

n=na+nb；δ=μb−μa；μ=μa+δ*nb/n；M2=M2a+M2b+δ²*na*nb/n；var=M2/(n−correction)。

容量、可用核数、API 临时区由当前平台与 SDK 核验。所有容量使用字节，保留对齐和同时存活区间；不得把上游 4KB、固定 tile 或核数当通用约束。

## 参数空间与替代方案

累加精度、两遍/Welford、状态驻留、epsilon/correction、NaN/Inf 策略。

小行全载可用两遍稳定计算；极端输入与特殊值按 oracle 回退通用语义。

## 伪代码

```text
variance: update/merge (count, mean, M2), then divide by count-correction
norm: apply p-specific transform -> reduce -> restore norm
softmax: row max -> shifted exp sum -> normalized output
handle empty/special values per oracle, not a shared sum shortcut
```

## 可复用 Ascend C 关键片段

```cpp
// 向量化 Welford 更新片段：delta1/mean/tmp 为独立且容量足够的 UB 区。
AscendC::Sub(delta1, xLocal, meanLocal, validCount);
AscendC::Muls(tmpLocal, delta1, invCount, validCount);
AscendC::Add(meanLocal, meanLocal, tmpLocal, validCount);
// M2 用新 mean 再求 delta2；不能重复使用旧 mean 的平方差。
```

片段省略工程与已声明的张量/变量，不是完整可运行算子；API 重载、作用域、别名和平台支持在 C3 核验。C2 冻结算法、所有权、合并顺序和数值语义；tile、局部 buffer/API 实现只在已声明容量/语义边界内调整。

## 验证与证据状态

来源审读完成，当前没有 NPU 性能验证。验证覆盖空/极小输入、对齐边界、尾块、多 task、特殊值和最大资源需求；完整正确性通过后才用统一计时协议比较。历史模板结果不构成当前性能承诺。

