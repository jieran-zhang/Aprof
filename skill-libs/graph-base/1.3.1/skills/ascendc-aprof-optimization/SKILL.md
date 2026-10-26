---
name: ascendc-aprof-optimization
description: 按 C2 的算法、所有权和实现自由度，在隔离工程实施 Ascend C 候选，完成审查、构建与完整正确性，并用执行知识树记录 C3。
---

# AProf 候选实现
数据相关路径的触发粒度、准备工作收支及修复后的选择更新，统一见[Action 选择规则](../../workflows/references/action-selection.md)；沿用现有方案与交接，不新增必跑工具。


按[完整方案](../../workflows/references/optimization-schemes.md)实施本轮必要步骤，允许多个注册 Action 与配套 P/O、Host/Kernel 修改共同完成，不要求单因素或按修改数分轮。对照联合工作量检查减少的工作是否被初始化、转换、同步或暂存抵消，记录未改变范围及共同资源。正确性修复可以沿用 Action，性能仍待测；越过计划自由度返回 C2。通用或参数化方案足够时不增加分派入口。

按[来源知识与性能假设](../../workflows/references/action-selection.md)使用正文：当前结构适用、实施条件可满足时，可提出具体假设试验，不要求先取得本算子的性能证明。性能 unknown 留给预测验证；地址、依赖、精度等缺项才阻止直接实施。记录正文如何改变实现、参数或拒绝理由，并与实际 patch 对照，不能只交已读路径/hash。可向 C1 提供方法可行性反馈，正式实施仍遵循 C2。

职责见 [optimization 角色](../../workflows/agents/optimization.md)，输入输出见 [C3](../../workflows/contracts/candidate.md)。输入包含 C0、[code-understanding 报告](../../workflows/contracts/code-understanding.md)、C2 的共同计划、方案/成员 action 及模板快照、具体参数、自由度和实际父版本；无需重新读取诊断图或规划知识目录。复用当前算法、分派、所有权和依赖解释，仅复核实际修改及其影响范围；源码或相关条件变化时局部更新理解并保存后继，所有后继先读[跨轮摘要](../../workflows/references/optimization-history.md)再按需展开；纯新 profiling 不触发全量重读。

从 [执行知识树](knowledge/ROUTER.md) 选择 tiling/tail、搬运、存活期、流水同步、Vector/API、Cube/API、标量控制、融合组合与精度边界方法。完整方案的成员可分别引用多个分支，逐成员路由并核对共同兼容，不把独立命中直接合并。格式、来源和初值见 [知识规范](knowledge/FORMAT.md)。

1. 在隔离工程按选定方案完成必要步骤及依赖。逐成员记录实际方法 ID/版本、参数、源码变化、共同计划符合性及保证条件的实际兑现；未知硬前提不能靠模板自动补足，无需逐步构建或测量中间候选。
2. 修改算法、任务/输出所有权、归约顺序或 workspace 所有权时，先交 coordinator 重规划。只在 C2 已授权自由度内调 tile、buffer、局部 API。
3. 构建前调用 ascendc-code-review；API/单位不明调用 ascendc-api-best-practices 或 ascendc-docs-search。只有裸 kernel 时使用 ascendc-kernel-direct-invoke。
4. 保留命令、退出码、冻结源码/binary 与完整 correctness。同一候选源变化后不得沿用旧正确性。失败先返回，精度问题用 ascendc-precision-debug，异常/超时/挂起用 ascendc-runtime-debug 或 ascendc-crash-debug。
5. 只有审查、构建和原 oracle 完整正确性通过，计时配置、输入与完整 kernel 序列齐备，才返回 C3 completed 供 profiling 采 B。

使用 `knowledge route --root <包> --owner optimization --context <evidence.json>`，features 按执行问题命中多个分支。C3 记录实际采用的知识条目，不把命中的全部条目当作已执行。历史案例的原协议、失败与适用域必须保留；没有新协议下的性能承诺。

新方案候选使用 aprof.handoff/v4 和 action-decision/v3；历史 v3 交接保持原义，不伪造旧 candidate_draft/RouteDecision/episode。明确授权的图外实验保留 unadmitted 与授权来源；不自动变成图训练样本。性能比较、继续父版本和最终裁决由 coordinator 推进。联合方案整体可评价，缺少消融仅限制单项归因，不要求默认补消融。

## 中文技术条目的使用

features 可含 cube-api、scalar-control、fusion-composition，分别读取计算原语、地址/控制和组合交接技巧，仍可叠加旧技术分支。recipe 正文给出关键代码上下文及资源代价，不要求读取上游仓库。融合不等于省去所有 GM 中间值；只在 C2 确定的阶段、所有权、数据通路和允许的资源范围内实施。公共数值与有效域约束继续由 precision-boundaries 承接。

路由的 `attributes.platform` 使用已核验 architecture_profile 的架构标识，例如 `dav-2201` 或 `dav-3510`；产品型号仍保留为原始证据。runtime 不自动把任意型号字符串转换为架构，未知或未映射时保持未知并走保守回退。不能仅为命中模板而改写平台。

## 当前Action实例交接

按[机制与交接规则](../../workflows/references/diagnosis-v4.md)核对Action实例与目标范围。路由提示不是事实，不能改platform/family/dtype/features或facts以强行命中。P/O分别运行内部router，具体recipe由C3选择；组合结果在选择后记录。成员 O_KEEP 只不追加对应局部优化，P 改变仍须实现新计划；P_KEEP 且所有成员 O_KEEP 才是 NOOP。unknown可供C2分析，C3实施受所绑定版本的Action安全/结构条件及方法合法性约束，性能未知可用于有依据的假设试验。

输入复用先区分：同一原输入的多个消费者保留 UB 值，读取 [input-tile-residency](knowledge/branches/memory-transfer/recipes/input-tile-residency.md)；不同临时值共用存储读 buffer-lifetime.reuse；仅改善缓存距离读 l2-reuse-order；改变融合区间读 fusion-composition。Action ready 不能替代原值、有效地址域、生命周期和物理容量的逐项核验。选中的正文及必要支持资料随实际选择记录，不把多个命中等同于多个已执行变换。

方案咨询已经点名具体 API 或数值替换时，按[选择规则](../../workflows/references/action-selection.md)展开对应叶：语义、调用粒度、尾块和内部 scratch 必须进入比较。通用分支概述不能替代具体 API 约束；不要把包内可查条件推迟为笼统 unknown。
