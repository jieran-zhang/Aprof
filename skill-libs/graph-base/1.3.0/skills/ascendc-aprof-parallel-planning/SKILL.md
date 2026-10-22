---
name: ascendc-aprof-parallel-planning
description: 依据已核验架构和 workload group 规划 Ascend C 算法、任务划分与分发，先于 tile、buffer 和流水调优。
---

# AProf 算法与并行规划
数据相关路径的触发粒度、准备工作收支及修复后的选择更新，统一见[Action 选择规则](../../workflows/references/action-selection.md)；沿用现有方案与交接，不新增必跑工具。


把[完整方案](../../workflows/references/optimization-schemes.md)的工作变化和覆盖落实为共同骨架，逐成员运行 P router，统一所有权、布局/数值、通路、同步与 workspace，按共同生命周期核算资源；仅参考某条原则要明示，不能冒充适用模板。新代价足以改变选择时回传 C1。分派只服务确有不同需求的方案，不以增加 Tiling Key 为优化目标。

可在 Action 最终确定前接收可行性咨询，用来源方案及当前源码给出分区、容量公式和代价，反馈给机会比较；不因此预锁实际 P/O 组合。按[条件分类](../../workflows/references/action-selection.md)，缺实测收益不阻止具体方案。资源实值未知时写合法参数域与必要补项；提取已有计划与真正变更计划分别记录。

工作流中的调用职责见 [parallel-planning 角色](../../workflows/agents/parallel-planning.md)，输入输出和阶段文档见 [planning contract](../../workflows/contracts/planning.md)。本 skill 维护专业操作；跨角色调用由协调者按 contract 分派。

本阶段确定各 workload group 的算法、任务划分和所有权。Agent 提出计划，runtime 负责严格契约和工程判定。相同语义、工作负载域与架构下复用有效计划，不因新 tile/buffer 候选重复算法搜索；每个候选仍需重新绑定 dispatch 实现源码。

从 [规划知识树](knowledge/ROUTER.md) 按算子族和融合与组合模式检索；可同时进入多个分支。C1 携带方案及各成员 action 内容快照，不需要直接读取 diagnosis/graph。历史案例按原协议使用，不能代替当前验证。

## 分析与选择

输入为完整只读 baseline `op_dir`、源码 hash、数学/精度契约、workload 元数据和 [code-understanding 报告](../../workflows/contracts/code-understanding.md)。复用报告中的当前算法、分派、所有权和依赖，仅补查影响本次规划的源码/条件；后继先读[跨轮摘要](../../workflows/references/optimization-history.md)，按需展开相关历史，使用同一适用理解报告，源码或相关条件变化只更新受影响部分并保存后继，纯新 profiling 不重做理解。用 `npu-arch` 建立有效 `architecture_profile`，未知资源与能力保持未知；[算法族路由](knowledge/ROUTER.md) 只读相关部分。

1. 以理解报告为基础核对本次方案涉及的真实算法与语义：归约轴、输出所有权、broadcast/index、舍入、相等值顺序、特殊值和合法 shape；按需复核源码与 reference，不重复全量恢复。不能缩成 benchmark case 集。
2. 根据独立任务数、归约长度、shape/长宽比、dtype/layout、语义属性和容量划分元数据区域，分别分析并保留通用 fallback。
3. 比较合法算法的总工作量、独立任务、复用/GM 流量、同步与合并、workspace 和精度；区分 workload 并行度不足与调度低效。A2/A3 使用 2201 ISA 约束及实际设备资源；950 的 RegBase/SIMT/CV 路径还需 SDK 能力支持。
4. 记录选择及被拒方案，绑定 source/probe/profile 证据 hash。需要改代码时交回协调者，由优化角色建立隔离的 `algorithm_parallel` 候选，按 [主工作流](../../workflows/aprof-performance-workflow.md) 完成构建、完整正确性和计时。书面计划不证明收益。
5. `execution` 调优前冻结计划；以后改变分解、归约、workspace 所有权或全局算法时，生成新的计划身份/hash。

## 严格产物

`parallel_plan` 绑定 `plan_id`、`operator`、分析父版本 `source_hash` 和 `architecture_profile_ref`，保留非空 `semantic_invariants`、`precision_invariants`。每组记录 `group_id`、`algorithm`、`task_partition`、`ownership`、`reduction`、`synchronization`、`workspace_bytes`、`workspace_formula`、`required_capabilities`、`memory_requirements`、`alternatives` 和 `selection_evidence` 的 hash 引用。

容量一律使用字节；即使当前尺寸固定，也写清动态公式和适用域，计入同时存活集合。未知容量不能授权特化。严格 schema 不接收自造字段，扩展说明放入引用报告。

`dispatch_plan` 为每组选互斥元数据条件、唯一 uint64 key 和 C kernel entry，并保留通用 fallback。绑定同一 operator/profile 与并行计划 hash。`parallel_plan.source_hash` 是分析父版本或计划基础，`dispatch_plan.source_hash` 是实际实现。新记录在 dispatch 与 `Context.workload` 都保留 `plan_basis_source_hash`、`implementation_source_hash`，分别匹配这两种身份；路由仍使用提议父版本。机器计划 JSON 放在源码快照外，避免 hash 自引用。C2 冻结 key/entry 和派发条件，C3 负责真实接线与身份校验。

```bash
aprofctl contract validate --kind architecture_profile --input <architecture.json>
aprofctl contract validate --kind parallel_plan --input <parallel-plan.json>
aprofctl contract validate --kind dispatch_plan --input <dispatch-plan.json>
aprofctl dispatch select --plan <dispatch-plan.json> --workload <metadata.json>
```

`Context.evidence` 保留三类对象及其规范 `architecture_profile_ref`、`parallel_plan_ref`、`dispatch_plan_ref`，以及 `optimization_stage`（`algorithm_parallel` 或 `execution`）。对象与证据进入任务本地索引；schema 通过不代表来源已验证。group/key/entry 必须有实际启动证据；永久 CAS 导入属于任务后 collector。

## 交接与迭代

执行候选继承冻结计划、选定 group/key、源码谱系和架构档案。每个变更先完成全量正确性，再用 [统一计时协议](../ascendc-aprof-profiling/references/unified-timing.md) 测代表 case，正式收尾覆盖所有 group、fallback 与相邻元数据边界；合格同源计时可复用。先按组分析，再汇总全 case 性能。

连续多轮从上一个通过正确性与运行检查的父版本开始，记录选择证据与父 hash。性能接纳单独记录，`formal_admission=not_evaluated` 不是 production best。失败后保留尝试与原因，回到上一有效父版本；保留 algorithm_parallel/execution 区分、构建和正确性失败、回归与 NOOP，不能为凑迭代数编造收益。

## 知识路由与交接

使用 `knowledge route --root <包> --owner parallel-planning --context <evidence.json>`；family 数组可同时含 elementwise/reduction/matmul/under-fusion/flash-attention/sort-topk/layout/indexing/moe-routing。选择命中模板后实例化容量、成本和所有权，比较至少适用主方案与 fallback。C2 用 aprof.handoff/v4 记录方案/成员身份、逐成员路由路径、条目版本/hash、共同计划、联合兼容、参数和实现自由度；历史 v3 保留原义。把采用模板的必要内容快照交 C3，优化角色不重读本知识树。

## 中文知识的使用

按 family 读取 template/strategy 正文，恢复任务所有权、公式单位及替代方案；无需打开上游源码。indexing 表示数据相关寻址/索引写入，moe-routing 组织多阶段路由与结果回收，under-fusion 叠加选择融合与组合模式。API/架构条件以正文及当前任务证据为准。C2 快照必须携带 C3 实施所需的算法、布局、交换和容量说明，不能只传一个外部链接。

路由的 `attributes.platform` 使用已核验 architecture_profile 的架构标识，例如 `dav-2201` 或 `dav-3510`；产品型号仍保留为原始证据。runtime 不自动把任意型号字符串转换为架构，未知或未映射时保持未知并走保守回退。不能仅为命中模板而改写平台。

## 当前Action实例交接

按[机制与交接规则](../../workflows/references/diagnosis-v4.md)核对Action实例与目标范围。路由提示不是事实，不能改platform/family/dtype/features或facts以强行命中。P/O分别运行内部router，具体recipe由C3选择；组合结果在选择后记录。独立命中不能简单并集，前序步骤保证须明确对象和依赖，C3 核实最终源码兑现；P_KEEP 引用覆盖全部相关目标的完整有效共同计划。unknown可供C2分析，C3实施受所绑定版本的Action安全/结构条件及方法合法性约束，性能未知可用于有依据的假设试验。
