# Optimization Candidate Design

本文定义 AProf optimization agent 生成 candidate 时的通用设计规则。它用于避免只做
`tileLength += x`、`blockDim = y` 这类浅层调参；每个 candidate 可以修改多行代码、重排循环、
拆分函数或调整 Host Tiling，但必须仍然只承载一个 `strategy_id` 的优化意图。

## Loading Policy

- 默认先读 `optimization-strategy-routing.md` 和本文件。
- 再按 `problem_family` 只读取 1 个对应分支 reference。
- 如果 candidate 是复杂算子机制，额外读取 exactly one operator playbook：MatMul、Softmax/FA、Reduction/Sort 或 Vector/Scalar。
- 只有 API overload、平台约束或算子族机制无法从本地 reference 确认时，才读取
  `optimization-cannbot-knowledge-index.md` 并点读一个具体 CANNBot reference。

## Candidate Depth

| 等级 | 允许改动 | 使用场景 | 必须额外证明 |
| --- | --- | --- | --- |
| 参数级 | tile/block/cache/repeat 参数调整 | 证据集中、风险低 | UB/边界公式仍成立 |
| 局部结构级 | 重排 tile loop、合并 DataCopy、拆 tail 分支、调整 queue 顺序 | 小块搬运、流水不重叠、tail 慢路径 | loop invariant、valid count、lifetime 不变 |
| 算法局部级 | 改 Reduction/Softmax/Sort/MatMul 局部策略、增加 split/reduce/workspace | 任务不足、长 K、在线状态、阶段性低活跃核 | 数值语义、workspace slot、跨核同步 |
| 片上融合级 | 把连续 Vector/Reduce/Cast/MatMul 后处理留在 UB/L1/L0 | GM 往返或中间结果落盘 | buffer 存活期、精度、容量公式 |

## Executable Template

每个 candidate plan 都必须能写出以下 5 个部分；现有 JSON schema 不新增必填字段时，可映射到
`required_evidence`、`capacity_model`、`structural_edits`、`expected_metric_delta` 和 `abort_conditions`。

| 模板字段 | 写什么 | 不合格示例 |
| --- | --- | --- |
| `decision_gate` | 进入该 candidate 的源码/metric/model 条件，以及反证 | “看起来可能更快” |
| `capacity_formula` | UB/L1/L0/workspace/核数/API limit 的分母、公式和来源 | “确认容量足够” |
| `structural_patch_shape` | 具体函数、loop、buffer、Host Tiling、workspace 或 API 调整形态 | “优化 DataCopy” |
| `metric_delta` | 期望哪些 metric 怎么动，什么幅度算有效 | “性能会提升” |
| `abort_conditions` | 缺证据、API 不确定、语义风险、平台风险时停止条件 | “失败就回退” |

## Playbook-shaped Candidate Examples

| Candidate | decision_gate | capacity_formula | structural_patch_shape | metric_delta | abort_conditions |
| --- | --- | --- | --- | --- | --- |
| MatMul StreamK | MN tile 少、K 长、active AIC 低 | `workspace = MN_tail * kCnt * baseM*baseN*sizeof(float)` | Host Tiling 增加 K split，Kernel 写 FP32 partial，AIV reduce+cast | active AIC 上升，tail round 缩短 | combine/FP32 partial/flag 不明确 |
| Softmax online | score/prob 完整落 GM 或 S2 很长 | `score_tile + Q/K/V + m/l/O_acc <= UB` | S2 tile loop + running max/sum/O_acc + final normalize | GM bytes 从 O(S^2) 降到 state/workspace | mask/padding/数值稳定不明确 |
| Sort two-level | `N > tileSize*coreNum` 且 Sync 轮数可控 | `ws = usedCore * elementsPerCore * proposal_bytes * 2` | tile sort、核内 merge、跨核 merge、Core0 extract | Phase 1/2 全核活跃，Sync 次数可解释 | tie-break/index/NaN 规则不明确 |
| UB fusion | Vector 段之间有 MTE3+MTE2 | `sum(live tensors aligned bytes) <= UB` | 删除中间 GM write/read，延迟 CopyOut | GM round trip 下降，VEC repeat 不回退 | lifetime alias 或 padding 不清 |

## Generation Rules

- 一个 candidate 只优化一个主问题族，但可以包含该策略必需的配套改动。例如 double buffer candidate
  可以同时减小 tile、调整 `InitBuffer` 深度、重排 prolog/steady/drain。
- 不要把“多行改动”拆成一堆互相依赖的微 candidate；若缺任一部分就无法验证策略，应放在同一个 candidate。
- 每个 candidate_plan 必须写清楚：
  - `structural_edits`：需要修改的函数、loop、buffer 或 Host Tiling 区域。
  - `capacity_model`：UB/L1/L0/workspace/核数/API limit 分母从哪里来。
  - `semantic_invariants`：不能改变的数学、dtype、tail、动态 shape、输出顺序。
  - `abort_conditions`：遇到哪些缺证据或 API 不确定必须停下。
- 如果候选需要硬编码 shape/core/UB/tile、降精度、删动态 tiling 或缩小边界，必须将结果标为
  `benchmark_specialized`，即使速度更快也不能作为默认 `best_op`。

## Evidence Chain

优化前至少形成三类证据中的两类：

| 证据 | 示例 |
| --- | --- |
| 源码锚点 | `DataCopy` 小块循环、`SetFlag` 紧跟 `WaitFlag`、中间结果落 GM、long-K loop |
| 模型证据 | workload class、UB/L1/L0 容量、per-core work、理论最小流量、roofline bound |
| profiling/trace | MTE 指令密度、PipeUtilization、ResourceConflictRatio、per-core time、trace gap |

缺少 profiling 时可以生成 candidate，但必须在 plan 中写 `missing_evidence`，并把结果表述为
`source-hypothesis` 或 `model-only candidate`。

## Acceptance Gates

- Build 和 accuracy 先于 profile。
- 稳定 repeated profile 先于 best 选择。
- 结构性改动必须多 shape 验证：主 shape、tail shape、小 shape、边界对齐 shape。
- 复杂算子必须验证阶段性语义：Reduction partial、Sort 稳定性/索引、Softmax 数值稳定、MatMul/FA workspace combine。
- simulator-only 结果只能作为 proxy，不能替代真实硬件 metric。
