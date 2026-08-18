# Optional CANNBot Knowledge Index

本文只用于 **精确点读** CANNBot 的单个 reference 文件。Diagnosis agent 默认不得加载
CANNBot 大型 `SKILL.md` 入口，也不得把这些 skills 加入默认 `skills:` 列表。

## 使用规则

1. 先使用 AProf 本地 reference 完成诊断假设、metric 选择和 evidence 分级。
2. 只有 API 参数、算子族机制或平台约束无法从 AProf 本地 reference 判断时，才读取下表中一个最相关的具体文件。
3. 点读后只提取诊断所需的源码锚点、metric 需求、反证和 missing evidence；不要把优化方案当成诊断结论。
4. 禁止打开 `third_party/cannbot-skills/**/SKILL.md` 作为 diagnosis 默认流程的一部分。

## 精确点读索引

| 触发条件 | 最多读取一个文件 | 只提取这些信息 |
| --- | --- | --- |
| `DataCopy` / `DataCopyPad` 参数、非对齐、stride、`blockCount` 不确定 | `third_party/cannbot-skills/ops/ascendc-api-best-practices/references/api-datacopy.md` | 对齐要求、Ext 参数、有效长度 vs 对齐长度、常见错误 |
| MTE2 高但不确定是真带宽还是小块搬运 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/common/datacopy_optimization_design.md` | copy 粒度、连续/stride、批量合并、带宽利用反证 |
| DoubleBuffer 配置后仍无 overlap | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/elementwise/double_buffer_design.md` | 预取/稳态/收尾循环、TQue/InitBuffer 语义、UB 预算 |
| UB 常驻、buffer 生命周期、bank conflict 不确定 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/common/ub_resident_design.md` | bank/group 冲突模式、padding 证据、resident/zone reuse 约束 |
| Scalar 高且源码没有明显逐元素循环 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/scalar/guide.md` | ScalarBound 定义、LoadStore/spill 方向、9 条原则入口 |
| 需要检查具体 Scalar 编码反模式 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/scalar/coding_principles.md` | 动态下标、热循环分支、状态机、成员变量、constexpr 等源码锚点 |
| Vector 高、Cast/reduce/UB 融合链可疑 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/elementwise/vector_efficiency_design.md` | Counter mode、UB chain、低延迟 reduce、Cast 密集证据 |
| Vector API `repeatTime` 或 mask 上限不确定 | `third_party/cannbot-skills/ops/ascendc-api-best-practices/references/api-repeat-limits.md` | `repeatTime <= 255`、分批处理、受影响 API |
| API 黑名单、`std::`、kernel 编译期限制可疑 | `third_party/cannbot-skills/ops/ascendc-api-best-practices/references/api-restrictions.md` | 禁用 API、替代方向、诊断清单 |
| Buffer/TQue/TBuf 生命周期或同步语义不确定 | `third_party/cannbot-skills/ops/ascendc-api-best-practices/references/api-buffer.md` | queue/buffer 使用约束、生命周期、潜在死锁/覆盖 |
| Pipeline event、EnQue/DeQue、SetFlag/WaitFlag 语义不确定 | `third_party/cannbot-skills/ops/ascendc-api-best-practices/references/api-pipeline.md` | event 契约、同步点、流水 ordering |
| MatMul 只需策略总览来定位机制 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/matmul/guide.md` | pingpong/SWAT/StreamK/FullLoad/scale coalescing/MTE2 preload 的适用条件 |
| MatMul pingpong 已开但 trace 有 PING/PONG gap | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/matmul/mte2_preload_design.md` | PONG gap 证据、准 no-bound 条件、尾片反证 |
| MatMul 真 MTE2 bound 且一侧矩阵小 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/matmul/fullload_design.md` | 小侧 L1 驻留条件、真/假 MTE2 bound 反证 |
| MatMul MN 尾碎片或负载不均 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/matmul/swat_design.md` | tail tile、serpentine/window、负载均衡证据 |
| MatMul MN 欠并行且 K 很长 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/matmul/streamk_design.md` | StreamK 适用/互斥条件、workspace reduce evidence |
| MatMul 小 scale/bias/LUT 搬运造成假 MTE2 bound | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/matmul/scale_coalescing_design.md` | 小块合并载入、带宽低但指令密集证据 |
| Softmax/FA online softmax 状态或跨 S2 workspace 可疑 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/softmax/state_resident_design.md` | state buffer resident、preLoadNum、UB 预算、索引反证 |
| FA/Softmax 算法是否应在线增量而不是全量矩阵 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/softmax/online_softmax_design.md` | running max/sum、O(S) 状态、tile loop evidence |
| Sort/TopK 标量路径、跨核同步或大数据多遍扫描可疑 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/sort/radix_sort.md` | 二分/分桶权衡、TQue DB、Sync/barrier、稀疏输出例外 |

## 记录方式

若使用了点读材料，在 `related_references` 或最终报告里只记录具体文件路径和用于诊断的结论，例如：

```text
related_reference: cannbot-knowledge-index -> api-datacopy.md
used_for: verify DataCopyPad alignment and effective-length vs aligned-length distinction
```

不要记录或要求加载 CANNBot 大型 skill 入口。
