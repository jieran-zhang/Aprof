# AI Core Utilization Optimization Strategies

本文用于 `problem_family=ai_core_utilization` 的 candidate 设计。目标是增加有效并行任务、平衡核间负载，
而不是盲目把 `blockDim` 拉满。

## Deep Routing

| 场景 | Decision gate | Structural patch shape |
| --- | --- | --- |
| 任务数少于核数 | `totalTasks < availableCores` 且 workload 不是 tiny-limited | split outer/group/head/batch/M/N/S2，重算 offset/tail |
| tail 集中拖尾 | per-core time 方差高，尾核任务明显更重 | 轮转分配 tile、按 work weight 分 group、分散 tail |
| MatMul MN 欠并行长 K | `mCnt*nCnt` 远小于 AIC 数且 K 长 | StreamK / split-K + FP32 partial workspace + AIV reduce |
| MatMul 末轮空核 | `mCnt*nCnt % aicNum` 小尾轮拖慢 | DP+SK 只切 tail MN tile，减少全局扰动 |
| Batch/GMM 分核 | batch/group 可独立，或 group M_i 不均 | batch 维、split-M/split-N、按累积 M_i 分配 |
| FA decode task 不足 | batch/head/S1 少但 KV/S2 长 | split-KV，增加 partial O/LSE combine |
| Reduction 阶段性低活跃 | A 小 R 大，单核 reduce 轴太长 | Group Reduce、workspace partial、combine stage |
| Sort 阶段性低活跃 | Phase 3/4 退化到少数核 | 调整 fan-in、两级归并、TopK 输出策略 |

## Capacity / Work Model

- `totalTasks = product(split_dims)`，`activeCores = min(totalTasks, availableCores)`。
- `work_per_core` 必须高于小块 MTE/launch/Sync 启动成本；增核不能把 copy 粒度切碎。
- split-K/StreamK：`parallel_tasks = MN_tasks * kCnt`，但要加 `workspace_partial + reduce/cast + sync` overhead。
- FA split-KV：`partial_O + partial_lse` workspace 与 combine time 必须小于 KV 并行收益。
- Sort/Reduction：阶段模型要分别估算并行阶段和串行/递减核归并阶段。

## Required Evidence

- totalTasks、blockDim、usedCoreNum、AIV/AIC 核数、per-core work。
- active core count、per-core time、tail/core imbalance。
- workload model：tiny/small/large 与 attainable utilization。
- 算子族阶段模型：MatMul MN/K、FA S2/KV、Reduction R/A、Sort merge phases。

## Abort Conditions

- tiny/small workload 低利用率已经接近 attainable utilization。
- 增核后每核 copy 粒度跌入小块 MTE bound。
- split-K/StreamK/FA split-KV 缺少 workspace combine、数值稳定或输出顺序证明。
- hardcoded core count 或 shape-specific 分核未标 `benchmark_specialized`。
- Sort/Reduction 的 Sync/merge 开销超过并行收益。

## Metric Delta

- active core count 上升且 per-core work 不过小。
- per-core time 方差和 tail 拖尾下降。
- 大 shape duration 下降，小 shape 不明显回退。
- split/reduce 类候选的 workspace overhead 小于并行收益。
