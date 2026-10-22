# Reduction / Sort Optimization Playbook

用于 ReduceSum/Max/Min/Mean/Norm/ArgMax、Sort、TopK、Argsort 和带 index 的局部算法 candidate。Reduction 与
Sort 共用此 playbook，但一次 candidate 只能选择其中一个算法方向。

## Reduction Decision Gate

- **FullLoad**：reduce 轴与输出轴都能放入 UB，直接顺序归约或两遍归约，避免 workspace。
- **TwoPass**：variance/std/layer norm 这类相关统计量可全载时，用两遍保证简单稳定。
- **Welford Online**：分载场景且两遍 IO 明显时，用单遍 running mean/M2；误差累积风险高时 group 化合并。
- **Group Reduce**：reduce 轴 R 太大、输出轴 A 太小导致核数不足时，沿 R 跨核切分，workspace 合并 partial。
- **Dichotomy Sum**：sum/variance 精度敏感或长 R 时，使用二分累加，避免大数吃小数。
- **With-index**：ArgMax/TopK 类必须一起维护 value/index，并证明相等值 tie-break 规则。

## Sort / TopK Decision Gate

- 小 N：单 tile Sort/MrgSort，避免多轮 Sync。
- 中等 N：每核独立 tile sort + workspace，最后少量跨核归并。
- 大 N / Pattern C：采用四阶段两级 MrgSort：tile sort、核内归并、跨核归并、Core0 final merge+extract。
- TopK：当 K 小于 N 很多时，优先保留 K 个 proposal，减少 workspace 和跨核归并路数。

## Capacity Formula

- Reduction：`UB = input_tile + output_partial + tmp/reduce_state + optional index`；Group Reduce 增加
  `workspace = splitNum * output_elems * sizeof(accum/index)`。
- Welford：保存 count/mean/M2 或 max/sum，多状态常驻要乘 dtype 与 buffer depth。
- Sort Phase 1：value、index、concat tmp、sort tmp、proposal buffer 同时计入；tail 用 pad value 保护比较。
- MrgSort Phase 2/3：`merge_bytes_per_elem = input_queue + output_queue + proposal/index`，按 M-way 路数与 32B 对齐推导。
- Workspace：按 `usedCore * elementsPerCore * proposal_bytes * double_buffer`，不能只按总元素数估算。

## Structural Patch Shape

- Reduction algorithm candidate 同步修改 Host Tiling 字段、kernel partial loop、workspace offset、combine stage 和 tail valid count。
- Welford/online candidate 增加 running state 初始化、tile 内更新、group merge、final normalize。
- Group Reduce candidate 增加跨核 partial 写入、Sync/flag、Core 或多核 combine、输出顺序。
- Sort two-level candidate 增加四阶段状态机、每核 workspace 区域、phase 间 SyncAll、final extract 和 index 输出。

## Metric Delta

- Reduction：GM round trip 下降、active core 数上升、Reduce/VEC time 与 workspace combine 有净收益。
- Sort：Phase 1/2 全核活跃，Phase 3/4 Sync 次数符合 `ceil(log_M(coreNum))`，workspace bytes 可解释。
- With-index/TopK：比较与 index 维护开销没有压过减少的数据量。

## Abort Conditions

- padding 值可能改变 max/min/sum/variance/softmax 或 sort ordering。
- Group Reduce / split candidate 缺少 partial workspace、combine 公式或精度验证。
- Sort 稳定性、相等值 index tie-break、NaN/Inf 规则不明确。
- 跨核 Sync 每阶段成本超过并行收益，或小 N 被强行套两级归并。
