---
schema_version: aprof.knowledge-record/v1
id: planning.elementwise.broadcast
kind: template
version: 1.0.0
status: active
title: 广播复用与容量分块
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/broadcast/ub-broadcast.md
  original_path: ops/ascendc-tiling-design/references/broadcast/ub-broadcast.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 331
  sha256: sha256:4aa3bffcf13401bfa2e2f2d13525a23bb107cf7ebf50f900db54bb08dccaa6ab
  excerpt_sha256: sha256:4aa3bffcf13401bfa2e2f2d13525a23bb107cf7ebf50f900db54bb08dccaa6ab
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.elementwise
references: []
evidence_status: source_reviewed_not_benchmarked
---

# 广播复用与容量分块

## 适用域与算法骨架

广播轴和连续内轴已确认；输出所有权按连续输出片定义。

先合法合轴，区分连续轴和广播轴；将小输入块装入一次，重复参与一个输出 tile；扩大复用域前重算 UB。

## 任务所有权、归约与同步

每个输出 tile 唯一写；重复使用的输入只读，无全局同步。

## 资源与成本公式

input_bytes=unique_input_elements*s_in；UB=input+expanded/output+tmp；reuse_gain≈重复读取字节−新临时流量。

容量、可用核数、API 临时区由当前平台与 SDK 核验。所有容量使用字节，保留对齐和同时存活区间；不得把上游 4KB、固定 tile 或核数当通用约束。

## 参数空间与替代方案

合轴、splitAxis、tile、是否展开输入；NDDMA 能力和单位需按平台核实。

UB 广播、批量 DMA、按轴迭代；不支持的 layout/dtype 回到通用广播。

## 伪代码

```text
merge only stride-compatible axes
for output tile owned by task:
  load each unique broadcast input slice once
  for output subtile within capacity: expand/index input -> compute -> write valid range
```

## 可复用 Ascend C 关键片段

```cpp
// 将复用输入与输出分别放入合法 LocalTensor；count 为有效元素。
AscendC::Muls(outLocal, inLocal, scale, validCount);
// 此片段仅覆盖标量广播乘法；一般广播使用核验后的 Broadcast API/stride。
```

片段省略工程与已声明的张量/变量，不是完整可运行算子；API 重载、作用域、别名和平台支持在 C3 核验。C2 冻结算法、所有权、合并顺序和数值语义；tile、局部 buffer/API 实现只在已声明容量/语义边界内调整。

## 验证与证据状态

来源审读完成，当前没有 NPU 性能验证。验证覆盖空/极小输入、对齐边界、尾块、多 task、特殊值和最大资源需求；完整正确性通过后才用统一计时协议比较。历史模板结果不构成当前性能承诺。

