# 优化候选设计

本文说明如何把一项有证据的优化意图变成候选。参数调整与结构修改均可，选择满足任务的最小改动；配套修改可包含多行代码、循环、函数或 Host Tiling，但共同服务于同一 `strategy_id`。

## 按需读取

- 默认读取本文件；解释历史先验时再读 `optimization-strategy-routing.md`。
- 再按 `problem_family` 只读取 1 个对应分支 reference。
- 如果 candidate 是复杂算子机制，额外读取 一份算子优化手册：MatMul、Softmax/FA、Reduction/Sort 或 Vector/Scalar。
- 只有 API overload、平台约束或算子族机制无法从本地 reference 确认时，才读取
  `optimization-local-knowledge-index.md` 并点读一个具体 AProf local reference。

## 候选修改层级

| 等级 | 允许改动 | 使用场景 | 必须额外证明 |
| --- | --- | --- | --- |
| 参数级 | tile/block/cache/repeat 参数调整 | 证据集中、风险低 | UB/边界公式仍成立 |
| 局部结构级 | 重排 tile loop、合并 DataCopy、拆 tail 分支、调整 queue 顺序 | 小块搬运、流水不重叠、tail 慢路径 | loop invariant、valid count、lifetime 不变 |
| 算法局部级 | 改 Reduction/Softmax/Sort/MatMul 局部策略、增加 split/reduce/workspace | 任务不足、长 K、在线状态、阶段性低活跃核 | 数值语义、workspace slot、跨核同步 |
| 片上融合级 | 把连续 Vector/Reduce/Cast/MatMul 后处理留在 UB/L1/L0 | GM 往返或中间结果落盘 | buffer 存活期、精度、容量公式 |

## 可执行计划模板

候选意图应能说明以下 5 个部分，记录在 candidate 交接（同名参考，非历史原件：[candidate.md](../../../../../contracts/candidate.md)） 的结果/引用产物中。既有 JSON 格式保持不变；已有设计对象可引用，不额外生成同义计划。

| 模板字段 | 写什么 | 不合格示例 |
| --- | --- | --- |
| `decision_gate` | 进入该 candidate 的源码/metric/model 条件，以及反证 | “看起来可能更快” |
| `capacity_formula` | UB/L1/L0/workspace/核数/API limit 的分母、公式和来源 | “确认容量足够” |
| `structural_patch_shape` | 具体函数、loop、buffer、Host Tiling、workspace 或 API 调整形态 | “优化 DataCopy” |
| `metric_delta` | 期望哪些 metric 怎么动，什么幅度算有效 | “性能会提升” |
| `abort_conditions` | 缺证据、API 不确定、语义风险、平台风险时停止条件 | “失败就回退” |

## 候选设计示例

| 候选 | decision_gate | capacity_formula | structural_patch_shape | metric_delta | abort_conditions |
| --- | --- | --- | --- | --- | --- |
| MatMul StreamK | MN tile 少、K 长、active AIC 低 | `workspace = MN_tail * kCnt * baseM*baseN*sizeof(float)` | Host Tiling 增加 K split，Kernel 写 FP32 partial，AIV reduce+cast | active AIC 上升，tail round 缩短 | combine/FP32 partial/flag 不明确 |
| Softmax online | score/prob 完整落 GM 或 S2 很长 | `score_tile + Q/K/V + m/l/O_acc <= UB` | S2 tile loop + running max/sum/O_acc + final normalize | GM bytes 从 O(S^2) 降到 state/workspace | mask/padding/数值稳定不明确 |
| Sort two-level | `N > tileSize*coreNum` 且 Sync 轮数可控 | `ws = usedCore * elementsPerCore * proposal_bytes * 2` | tile sort、核内 merge、跨核 merge、Core0 extract | Phase 1/2 全核活跃，Sync 次数可解释 | tie-break/index/NaN 规则不明确 |
| UB fusion | Vector 段之间有 MTE3+MTE2 | `sum(live tensors aligned bytes) <= UB` | 删除中间 GM write/read，延迟 CopyOut | GM round trip 下降，VEC repeat 不回退 | lifetime alias 或 padding 不清 |

## 生成规则

- 默认只有一个主假设、一个候选。candidate 阶段文档引用已有 workload、架构和冻结计划，不重复写多份设计。
- 一个 candidate 只承载一个主优化意图，但可以包含该策略必需的配套改动。例如 double buffer candidate
  可以同时减小 tile、调整 `InitBuffer` 深度、重排 prolog/steady/drain。
- 不要把“多行改动”拆成一堆互相依赖的微 candidate；若缺任一部分就无法验证策略，应放在同一个 candidate。
- 候选设计必须写清楚以下技术内容，可直接在交接正文或引用设计中提供：
  - `structural_edits`：需要修改的函数、loop、buffer 或 Host Tiling 区域。
  - `capacity_model`：UB/L1/L0/workspace/核数/API limit 分母从哪里来。
  - `semantic_invariants`：不能改变的数学、dtype、tail、动态 shape、输出顺序。
  - `abort_conditions`：遇到哪些缺证据或 API 不确定必须停下。
- 合法的固定 tile 等调优参数，只要保持语义、支持域、容量约束和通用 fallback，
  不自动成为 benchmark specialization。若用 case-ID 捷径、未经核验的固定假设、
  降精度或删除动态处理缩小原契约，标为 `benchmark_specialized`，不能默认选为 `best_op`。

## 证据链

按合法图路由收集所需证据；以下是可用来源：

| 证据 | 示例 |
| --- | --- |
| 源码锚点 | `DataCopy` 小块循环、`SetFlag` 紧跟 `WaitFlag`、中间结果落 GM、long-K loop |
| 模型证据 | workload class、UB/L1/L0 容量、per-core work、理论最小流量、roofline bound |
| profiling/trace | MTE 指令密度、PipeUtilization、ResourceConflictRatio、per-core time、trace gap |

缺少 profiling 时，只有现有证据已满足合法 graph route 才可直接生成 routed candidate；
在 plan 中保留 `missing_evidence`，表述为 `source-hypothesis` 或 `model-only candidate`。
若所需 predicate 缺证据，先采最小有效诊断；需要正式来源时使用相应完整采集要求。
未实现的 extractor 保持 unavailable，不能凭源码叙述或短测收益补写机制 predicate。
仍无合法路线时记录 `needs_evidence` 或选择 NOOP。用户明确授权的无路由源码实验
保留为未准入记录，不伪造 route、episode、正式 best 或训练 reward。

## 验收边界

- Build 和 accuracy 先于 profile。
- 每次候选源码变化都执行完整正确性；准备数据命中缓存不能替代这个检查。
- 按 主工作流（同名参考，非历史原件：[SKILL.md](../../ascendc-perf-optimize/SKILL.md)） 使用唯一计时协议：代表 case 反馈、全 case 正式收尾。同源合格证据可复用；异常或近阈值按预声明规则以同方法独立复验，不强制重采或切换旧配对协议。
- PMU 只按路由或机制需求采集；正式工程结果由 runtime 给出，早停和无结论保留原始记录，不编造 verdict 或 reward。
- 结构性改动必须多 shape 验证：主 shape、tail shape、小 shape、边界对齐 shape。
- 复杂算子必须验证阶段性语义：Reduction partial、Sort 稳定性/索引、Softmax 数值稳定、MatMul/FA workspace combine。
- simulator-only 结果只能作为 proxy，不能替代真实硬件 metric。

> 文档适配说明：本页已修复引用；缺失材料的链接已移除，同名补充参考不代表历史原件。来源及历史回放使用[保留的证据原文](../../../../../../sources/document-originals/9525b72487a720ddf75106506f99cf021baaf196245a644fd1c4a5fc8f0de597.txt)。
