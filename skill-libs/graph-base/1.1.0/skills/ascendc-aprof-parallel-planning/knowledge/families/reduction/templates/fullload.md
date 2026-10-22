---
schema_version: aprof.knowledge-record/v1
id: planning.reduction.fullload
kind: template
version: 1.0.0
status: active
title: AR/ARA FullLoad 与行所有权
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 151
  sha256: sha256:c74ad927867806d42723213292831e22c84a2e84d75230e5aa615dee1500782a
  excerpt_sha256: sha256:c74ad927867806d42723213292831e22c84a2e84d75230e5aa615dee1500782a
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.reduction
references: []
evidence_status: source_reviewed_not_benchmarked
---

# AR/ARA FullLoad 与行所有权

## 适用域与算法骨架

归约输入抽象为 A1×R×A0；完整 R 段及临时区可容纳。AR 为 A0=1，ARA 按连续 A0 访问。

AR 将完整行装入 UB 后归约；ARA 保留 A0 向量并沿 R 累积；按非归约维把独立行/列组分核。

## 任务所有权、归约与同步

每个输出行/列组归一个核，核内归约；variance/correction、norm 的 p、softmax 稳定变换分别定义。

## 资源与成本公式

UB=queueDepth*rows*R_align*A0_align*s+output+accum+apiTmp；R 的有效长度只用于数学归约。

容量、可用核数、API 临时区由当前平台与 SDK 核验。所有容量使用字节，保留对齐和同时存活区间；不得把上游 4KB、固定 tile 或核数当通用约束。

## 参数空间与替代方案

rows、A0 tile、输入/累加 dtype、队列深度；tmp 使用当前 API 查询。

容量失败转 ColSplit/RowSplit；A 很小而 R 大比较分段归约。

## 伪代码

```text
map task -> (A1 range, A0 range)
load full valid R with aligned storage stride
AR: reduce each row over R
ARA: vector accumulate A0 lanes across R
write the owned output once
```

## 可复用 Ascend C 关键片段

```cpp
// AR 的 count 使用 rLength，行起点使用 rLengthAlign。
AscendC::ReduceSum<T>(resultLocal, xLocal[row * rLengthAlign], tmpLocal,
                     static_cast<int32_t>(rLength), false);
// 使用前核实该 SDK 的类型、临时区、count 和别名约束。
```

片段省略工程与已声明的张量/变量，不是完整可运行算子；API 重载、作用域、别名和平台支持在 C3 核验。C2 冻结算法、所有权、合并顺序和数值语义；tile、局部 buffer/API 实现只在已声明容量/语义边界内调整。

## 验证与证据状态

来源审读完成，当前没有 NPU 性能验证。验证覆盖空/极小输入、对齐边界、尾块、多 task、特殊值和最大资源需求；完整正确性通过后才用统一计时协议比较。历史模板结果不构成当前性能承诺。

