# 核任务并行策略

本族历史 `strategy_id` 固定为 `ai_core_task_parallelism`。新方案仍使用既有 Action、P 模板和 O recipe 的真实 ID/hash。历史经验检索以该固定 ID 关联，阶段 schema 中使用现有字段，迁移说明和下列检查记录放在引用报告内。

## 指标与输入

指标统一使用[指标字典](../../ascendc-aprof-profiling/references/metrics.md)。必需输入包含同次调用的 Block Dim、Task Duration、完整每核耗时、可见同类核数和 TilingData。逐项保存原字段、单位、文件 hash、行定位、采集窗口与证据性质。缺项时先补证据。

## 判定顺序与互斥条件

按以下顺序筛查，同一形状可以有后继机会，每轮先选择有证据的主问题。

1. 核实语义、架构、容量和同步参与者。实际等待来自搬运或流水时，转[搬运](../knowledge/branches/memory-transfer/ROUTER.md)或[流水同步](../knowledge/branches/pipeline-sync/ROUTER.md)选择对应方法。
2. 若 `block_dim > total_tasks`，比较减核与合法空闲退出。普通独立输出可取 `used_core_num = min(total_tasks, available_cores)`，Host 按动态 shape 重算。只有在退出核没有输出、没有 barrier/flag/combine 职责时，允许入口执行 `block_idx >= used_core_num` 的退出判断。
3. 若 `block_dim < min(total_tasks, available_cores)`，比较增加启动核数。每核工作量须满足下节的搬运与启动成本约束。
4. MatMul 令 `MN = m_count*n_count`。`MN < aic_cores` 进入欠并行方案比较，`MN >= aic_cores` 且 `MN % aic_cores != 0` 才进入末轮碎片方案比较，余数为 0 时跳过该分支。阅读[Split-K](../../ascendc-aprof-parallel-planning/knowledge/families/matmul/templates/splitk.md)与[StreamK](../../ascendc-aprof-parallel-planning/knowledge/families/matmul/templates/streamk.md)。
5. 完整核覆盖下 `imbalance > 0.10` 时比较均衡划分，超过 0.30 时优先检查极端任务与尾块。归约、Sort、FA 分别核对阶段的依赖和合并代价。

StreamK、MoE 与跨核归约的空闲参与者可能仍承担同步或归并工作。减核时重写并验证整个参与者集合，保留输出覆盖与完成边。

## 容量和成本实例化

令 `C = active_cores_attainable`，`E = ceil(total_elements/C)`。任务配置给出 `useful_bytes_per_core_min`，比较 `E*dtype_bytes >= useful_bytes_per_core_min`。该阈值来自同平台启动/搬运 microbenchmark 或已记录任务策略，缺少测量时比较多个合法 C 并保留未知收益。

UB 峰值按同时存活对象计 `sum(q_j * align(elements_j*bytes_j)) + api_scratch + reserved_bytes <= available_ub_bytes`，双物理槽用 q=2，队列深度另行核对。BT、FP 和频率使用[独立资源口径](../../npu-arch/references/buffers-and-frequency.md)。

Split-K 对每个输出 tile t 计算 `workspace_bytes = sum(split_count_t * aligned_M_t * aligned_N_t * partial_dtype_bytes)`，再计入槽位、系统 workspace 与对齐。新增 partial GM 读写和 combine 时间进入完整调用比较。

FA Split-KV 令 split 数 S、查询块 Bq、输出宽度 D、输出状态宽度 sO 和归约状态宽度 sR，则 `workspace_bytes = align(S*Bq*D*sO) + align(S*Bq*state_count*sR)`，`state_count` 按 max/sum 或 log-sum-exp 表示确定。阅读[Split-KV](../../ascendc-aprof-parallel-planning/knowledge/families/flash-attention/templates/splitkv.md)。

词汇统一采用 MN 输出 tile 数、K 归约切片、DP+SK（数据并行加 StreamK 尾部）、S2（KV 序列长度）、LSE（log-sum-exp 状态）与 fan-in（单个合并任务消费的 partial 数）。Sort 的排序和归并阶段按[层次归并模板](../../ascendc-aprof-parallel-planning/knowledge/families/sort-topk/templates/merge.md)记录真实阶段名。

## pre_patch_checks

- 核类型、可见核数、block_dim、total_tasks 和每核工作量均有来源，动态 shape 的合法范围已冻结。
- 输出所有权区间互斥且完整，主 shape、tail、小 shape 和对齐边界 shape 均进入正确性集合。
- UB/L1/L0、BT/FP 与 GM workspace 的峰值、单位、对齐及来源分别核验。
- 跨核通信列出全部生产者、消费者、flag/barrier 与退出路径，partial 合并顺序满足精度约束。
- 记录固定 strategy_id、实际 Action/P/O 身份、基线源码 hash 和可判定的 expected_metric_delta。

## post_patch_checks

构建成功后对原 oracle 执行完整正确性验证，覆盖上述四类形状与声明的 dtype/特殊值。核对 dispatch、used_core_num、输出覆盖、combine 和同步参与者。独立[reviewer](../../../workflows/agents/reviewer.md)复核当前源码 hash 的检查结果，再按[统一计时](../../ascendc-aprof-profiling/references/unified-timing.md)比较同源 A/B。

## expected_metric_delta

预测在实施前填入本轮引用报告，明确指标、来源、方向、阈值和失败条件。

- 减核或空闲退出的预测为 `idle_fraction` 降到 0，同时保持完整输出覆盖。`head_fraction` 以同窗口比较，目标下降至少 0.05 个比例点需由任务配置明确采用。
- 增核的预测为 `active_cores_attainable` 增加且 `elements_per_core` 至少保留原值的 1/2，并通过任务配置的最小有效字节门槛。
- 均衡划分的筛查目标为 `imbalance` 从大于 0.10 降至不大于 0.10，保留每核工作量与完整覆盖证明。
- 默认探索目标为主 shape Task Duration 至少下降 5%，任一小 shape 回退至多 3%。任务可覆盖默认值，结果保存实际阈值。正式接纳继续按现行统一计时协议。
- Split-K/Split-KV 比较额外 partial 流量和 combine 时间。字节用 B，时间用 us，先以实测带宽换算流量成本，再与节省时间比较。

## failure_handoff

正确性失败交 [precision-debug](../../ascendc-precision-debug/SKILL.md)，运行错误交 [runtime-debug](../../ascendc-runtime-debug/SKILL.md)，挂起或 AIC 错误交 [crash-debug](../../ascendc-crash-debug/SKILL.md)，缺采集产物交 [profiling](../../ascendc-aprof-profiling/SKILL.md)。保留失败源码、命令、退出码、证据和当前父版本，修复后创建新候选。

指标回退记录到跨轮摘要并回到方案比较。MTE 或流水证据占主导时转出本族，重新选择对应 Action 和执行知识。构建或正确性失败时停止候选计时。
