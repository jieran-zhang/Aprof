# Optional Optimization CANNBot Knowledge Index

本文只用于 optimization agent 在本地 AProf reference 无法确认 API、平台或算子族机制时精确点读
单个 CANNBot reference。默认流程不得打开 CANNBot 大型 `SKILL.md` 入口，也不得把大型优化/design/API
skills 加入 agent 默认 `skills:`。

## Use Rules

1. 先用 AProf 本地 optimization reference 形成 candidate 设计、证据、反证和 gate。
2. 只有具体 API overload、平台边界或算子族机制无法确认时，才读取下表中一个最相关文件。
3. 点读后只提取 candidate 所需的 API 参数、结构性改写约束、反证和验证项。
4. 不要把外部文档整段复制进 plan；在 `references[]` 中记录具体文件即可。
5. 禁止打开任何 CANNBot 大入口；只打开本表中的精确 reference 文件。

## Single-core Pipeline

| 触发条件 | 最多读取一个文件 | 用途 |
| --- | --- | --- |
| MTE 小块、L2 复用、DataCopyPad、UB 原地消费不确定 | `third_party/cannbot-skills/ops/ascendc-perf-optimize/references/single-core-pipeline/memory.md` | 校验真假 memory bound 与小块合并 |
| VEC 指令分类、Cast/超越函数阈值、融合指令、RegBase、DB 生效不确定 | `third_party/cannbot-skills/ops/ascendc-perf-optimize/references/single-core-pipeline/vec.md` | 校验 vector/API/fusion candidate |
| Scalar 反模式、循环轴、分支、TPipe/TBuffer 封装开销不确定 | `third_party/cannbot-skills/ops/ascendc-perf-optimize/references/single-core-pipeline/scalar.md` | 校验 hot-loop scalar rewrite |
| No-bound 气泡、pingpong、UnitFlag、preload、提前发射不确定 | `third_party/cannbot-skills/ops/ascendc-perf-optimize/references/single-core-pipeline/no-bound.md` | 校验 pipeline bubble candidate |

## Tiling / Algorithm

| 触发条件 | 最多读取一个文件 | 用途 |
| --- | --- | --- |
| Vec/UB 与 Cube/L1+UB 两级切分边界不确定 | `third_party/cannbot-skills/ops/ascendc-perf-optimize/references/tiling/index.md` | 校验 tiling 总路由 |
| MatMul SWAT 七步、baseM/baseN、L0C DB、L1 stepK、nBufferNum 不确定 | `third_party/cannbot-skills/ops/ascendc-perf-optimize/references/tiling/matmul/fallback/tiling-flow.md` | 校验 MatMul tiling candidate |
| MXFP scale、batch_matmul、group_matmul 差异不确定 | `third_party/cannbot-skills/ops/ascendc-perf-optimize/references/tiling/matmul/fallback/tiling-variants.md` | 校验 MatMul 变体字段 |
| Reduction FullLoad/TwoPass/Welford/Group Reduce/with-index 路由不确定 | `third_party/cannbot-skills/ops/ascendc-tiling-design/references/reduction/algorithms.md` | 校验 Reduction 算法 candidate |
| Sort/TopK 两级 MrgSort、workspace、UB bytes/elem、Sync 成本不确定 | `third_party/cannbot-skills/ops/ascendc-tiling-design/references/sort/alg-two-level-mrgsort.md` | 校验 Sort/TopK candidate |
| FA S2/D tile、subfamily、workspace 或 split 方式不确定 | `third_party/cannbot-skills/ops/ascendc-tiling-design/references/flashattention/design.md` | 校验 FA tiling candidate |

## Performance Playbooks

| 触发条件 | 最多读取一个文件 | 用途 |
| --- | --- | --- |
| MatMul 策略总览 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/matmul/guide.md` | 选择 pingpong/SWAT/StreamK/FullLoad 类候选 |
| MatMul MN tail 或负载不均 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/matmul/swat_design.md` | 设计 SWAT / tail balance candidate |
| MatMul MN 欠并行长 K | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/matmul/streamk_design.md` | 校验 StreamK / DP+SK candidate |
| MatMul 小侧可驻留 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/matmul/fullload_design.md` | 校验 FullLoad candidate |
| MatMul PING/PONG gap | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/matmul/mte2_preload_design.md` | 校验 MTE2 preload candidate |
| MatMul scale/bias/LUT 小块搬运 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/matmul/scale_coalescing_design.md` | 设计小参数合并载入 |
| Softmax/FA online state | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/softmax/online_softmax_design.md` | 设计 online softmax candidate |
| Softmax/FA resident state | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/softmax/state_resident_design.md` | 校验 state resident / workspace slot |
| UB resident、zone reuse、bank conflict、buffer layout | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/common/ub_resident_design.md` | 设计 resident / layout candidate |
| MTE coalescing、连续/stride 搬运、理论 traffic | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/common/datacopy_optimization_design.md` | 设计 traffic reduction candidate |
| Tail path 或 padding 策略 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/common/tail_block_design.md` | 校验 tail 主路径复用 |
| Elementwise vector efficiency、Cast、融合指令、repeat | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/elementwise/vector_efficiency_design.md` | 设计 vector/API/fusion candidate |
| DoubleBuffer / prefetch / drain 结构 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/elementwise/double_buffer_design.md` | 校验 prolog/steady/drain |
| Scalar 编码原则 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/scalar/coding_principles.md` | 校验 hot-loop rewrite |
| Sort/TopK radix 或局部排序策略 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/sort/radix_sort.md` | 设计 sort/topk 算法 candidate |
| Broadcast mask / conversion / transpose fusion 不确定 | `third_party/cannbot-skills/ops/ascendc-performance-best-practices/reference/conversion/transpose_fusion_design.md` | 校验 conversion/broadcast candidate |

## API Guard

| 触发条件 | 最多读取一个文件 | 用途 |
| --- | --- | --- |
| DataCopy/DataCopyPad 参数、对齐、padding 不确定 | `third_party/cannbot-skills/ops/ascendc-api-best-practices/references/api-datacopy.md` | 校验 overload、valid length、padding 语义 |
| Buffer/TQue/TBuf 生命周期或 event ordering 不确定 | `third_party/cannbot-skills/ops/ascendc-api-best-practices/references/api-buffer.md` | 校验生命周期、FreeTensor、覆盖风险 |
| Pipeline event、SetFlag/WaitFlag 语义不确定 | `third_party/cannbot-skills/ops/ascendc-api-best-practices/references/api-pipeline.md` | 校验同步契约和 ordering |
| repeatTime/mask 上限不确定 | `third_party/cannbot-skills/ops/ascendc-api-best-practices/references/api-repeat-limits.md` | 校验分批和 API 上限 |
| API 黑名单或平台限制可疑 | `third_party/cannbot-skills/ops/ascendc-api-best-practices/references/api-restrictions.md` | 避免非法 API candidate |
| MatMul API 平台或参数边界不确定 | `third_party/cannbot-skills/ops/ascendc-api-best-practices/references/api-matmul.md` | 校验 MatMul API candidate |
| GMM API 平台或参数边界不确定 | `third_party/cannbot-skills/ops/ascendc-api-best-practices/references/api-gmm.md` | 校验 GMM candidate |
| Reduce API 或 reduce pattern 不确定 | `third_party/cannbot-skills/ops/ascendc-api-best-practices/references/api-reduce.md` | 校验 Reduce API candidate |
| MrgSort API、proposal、index、merge 参数不确定 | `third_party/cannbot-skills/ops/ascendc-api-best-practices/references/api-mrgsort.md` | 校验 Sort/TopK API candidate |
| Host runtime、blockDim、launch 语义不确定 | `third_party/cannbot-skills/ops/ascendc-api-best-practices/references/api-host-runtime.md` | 校验 launch/tiling 连接 |
