---
schema_version: aprof.knowledge-record/v1
id: implementation.tiling-tail.valid-length
kind: recipe
version: 1.0.0
status: active
title: 有效长度、对齐长度与动态尾块
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
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
parent: implementation.tiling-tail
references: []
evidence_status: source_reviewed_not_benchmarked
---

# 有效长度、对齐长度与动态尾块

## 适用条件

任何非整齐 shape、归约、转换或尾块写回。 输入是 C2 的 action/模板快照、实例参数、实现自由度、源码及架构证据。

## 操作步骤与约束

分开 validElements/alignedElements/bytes；算各核实际有效范围；零任务不进入 loop；循环次数用有效长度的 ceilDiv，尾部不制造额外零长迭代。

UB 分配/rowOffset 用对齐长度，DMA blockLen 与数学 count 使用有效长度。

## 关键代码

```cpp
AscendC::DataCopyExtParams cp{1, static_cast<uint32_t>(validCount * sizeof(T)), 0, 0, 0};
AscendC::DataCopyPadExtParams<T> pad{false, 0, 0, 0};
AscendC::DataCopyPad(xLocal, xGm[offset], cp, pad);
// 该 GM->UB 重载的 blockLen 是字节；边界和 uint32 范围须预先核验。
```

片段用于表达关键契约，变量与工程由候选补齐。当前只完成来源审读；需按目标 SDK 编译和运行完整正确性，尚未进行 NPU 性能验证。

## 验证方法

边界前一元素/正好边界/后一元素、空任务、单 tile、多 tile；核验最后地址与 oracle。 构建前调用 ascendc-code-review；正确性失败调用 ascendc-precision-debug，异常或挂起调用 ascendc-runtime-debug/ascendc-crash-debug。

## 失败特征与回退

尾块错、对齐输入通过但奇数 shape 失败、零长 loop 下溢。 保留原失败、完整日志与实际改动，回退到 C2 fallback 或请求重规划；不能静默改算法以继续计时。C3 记录所用条目版本、参数变化及计划符合性。

