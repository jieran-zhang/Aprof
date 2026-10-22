---
schema_version: aprof.knowledge-record/v1
id: implementation.precision-boundaries.numeric
kind: recipe
version: 1.0.0
status: active
title: 累加精度、特殊值与数值边界
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/reduction/alg-welford.md
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
parent: implementation.precision-boundaries
references: []
evidence_status: source_reviewed_not_benchmarked
---

# 累加精度、特殊值与数值边界

## 适用条件

归约、方差、norm、softmax、split-K/KV 与 Cast 变更。 输入是 C2 的 action/模板快照、实例参数、实现自由度、源码及架构证据。

## 操作步骤与约束

从 oracle 写出 dtype、舍入、epsilon/correction、NaN/Inf/有符号零语义；选择累加状态；用稳定公式合并；明确全 mask、空归约、计数为零分支。

FP32 partial 不是自动正确的证明；归约顺序变化仍需误差与边界校验。

## 关键代码

```cpp
// Welford 的两段合并使用宿主参考公式核对 kernel 输出。
const double delta = meanB - meanA;
const double count = countA + countB;
// count==0 单独按原语义处理，以下只用于 count>0。
const double mean = meanA + delta * countB / count;
const double m2 = m2A + m2B + delta * delta * countA * countB / count;
```

片段用于表达关键契约，变量与工程由候选补齐。当前只完成来源审读；需按目标 SDK 编译和运行完整正确性，尚未进行 NPU 性能验证。

## 验证方法

大动态范围、抵消、NaN/Inf、全零、极大/极小值、分段数变化和 oracle 全 case。 构建前调用 ascendc-code-review；正确性失败调用 ascendc-precision-debug，异常或挂起调用 ascendc-runtime-debug/ascendc-crash-debug。

## 失败特征与回退

平均误差正常但极值超标、方差负值、全 mask 出 NaN、split 后重复 bias。 保留原失败、完整日志与实际改动，回退到 C2 fallback 或请求重规划；不能静默改算法以继续计时。C3 记录所用条目版本、参数变化及计划符合性。


量化/MX 格式还须单独核验 quantization 轴、scale 对应关系、pack 布局和目标 SDK 支持；不能仅按连续维推导量化语义。
