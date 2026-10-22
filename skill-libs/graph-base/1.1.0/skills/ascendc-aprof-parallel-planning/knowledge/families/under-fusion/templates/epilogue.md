---
schema_version: aprof.knowledge-record/v1
id: planning.under-fusion.epilogue
kind: template
version: 1.0.0
status: active
title: MatMul epilogue 融合
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/matmul/guide.md
  original_path: ops/ascendc-performance-best-practices/reference/matmul/guide.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 14
  sha256: sha256:595a41d757e618346bd981b603077f346471d990ee63ec8086369faf3b17f9d0
  excerpt_sha256: sha256:595a41d757e618346bd981b603077f346471d990ee63ec8086369faf3b17f9d0
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.under-fusion
references: []
evidence_status: source_reviewed_not_benchmarked
---

# MatMul epilogue 融合

## 适用域与算法骨架

MatMul 输出紧跟 bias、Cast 或逐元素函数，消费者无额外全局依赖。

在一次完整 K 累加或 split-K 合并之后执行 epilogue，再写 GM；比较 AIC/AIV 节拍和中间转换。

## 任务所有权、归约与同步

最终 MN owner 执行 epilogue；partial 不施加非线性或 bias。

## 资源与成本公式

UB=epilogue输入+中间+输出+tmp；省去 C 的一轮写读；增加 AIV 时间和跨引擎等待必须计成本。

容量、可用核数、API 临时区由当前平台与 SDK 核验。所有容量使用字节，保留对齐和同时存活区间；不得把上游 4KB、固定 tile 或核数当通用约束。

## 参数空间与替代方案

epilogue 链、dtype、分块和槽数；Fixpipe layout 能力需确认。

精度/接口不兼容或拖慢 Cube 时保留独立 epilogue。

## 伪代码

```text
finish complete K accumulation (including any split merge)
convert only at declared precision boundaries
apply bias/activation once on valid output
write final C tile
```

## 可复用 Ascend C 关键片段

```cpp
// epilogue 只在最终累加结果上执行；count 为有效输出元素。
AscendC::Adds(outLocal, accLocal, biasScalar, validCount);
// 一般 bias tensor 使用匹配广播方案；不能把标量示例推广到所有 bias。
```

片段省略工程与已声明的张量/变量，不是完整可运行算子；API 重载、作用域、别名和平台支持在 C3 核验。C2 冻结算法、所有权、合并顺序和数值语义；tile、局部 buffer/API 实现只在已声明容量/语义边界内调整。

## 验证与证据状态

来源审读完成，当前没有 NPU 性能验证。验证覆盖空/极小输入、对齐边界、尾块、多 task、特殊值和最大资源需求；完整正确性通过后才用统一计时协议比较。历史模板结果不构成当前性能承诺。

