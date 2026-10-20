---
name: ascendc-aprof-optimization
description: 按 C2 的算法、所有权和实现自由度，在隔离工程实施 Ascend C 候选，完成审查、构建与完整正确性，并用执行知识树记录 C3。
---

# AProf 候选实现

职责见 [optimization 角色](../../workflows/agents/optimization.md)，输入输出见 [C3](../../workflows/contracts/candidate.md)。输入包含 C0、C2 的 action/模板快照、具体参数、自由度和实际父版本；无需重新读取诊断图或规划知识目录。

从 [执行知识树](knowledge/ROUTER.md) 选择 tiling/tail、搬运、存活期、流水同步、Vector/API、Cube/API、标量控制、融合组合与精度边界方法。一次变换可引用多个分支。格式、来源和初值见 [知识规范](knowledge/FORMAT.md)。

1. 在隔离工程按选定 action 实现一个可检验意图。记录实际方法 ID/版本、源码差异、参数调整和 C2 符合性；未知硬前提不能靠模板自动补足。
2. 修改算法、任务/输出所有权、归约顺序或 workspace 所有权时，先交 coordinator 重规划。只在 C2 已授权自由度内调 tile、buffer、局部 API。
3. 构建前调用 ascendc-code-review；API/单位不明调用 ascendc-api-best-practices 或 ascendc-docs-search。只有裸 kernel 时使用 ascendc-kernel-direct-invoke。
4. 保留命令、退出码、冻结源码/binary 与完整 correctness。同一候选源变化后不得沿用旧正确性。失败先返回，精度问题用 ascendc-precision-debug，异常/超时/挂起用 ascendc-runtime-debug 或 ascendc-crash-debug。
5. 只有审查、构建和原 oracle 完整正确性通过，计时配置、输入与完整 kernel 序列齐备，才返回 C3 completed 供 profiling 采 B。

使用 `knowledge route --root <包> --owner optimization --context <evidence.json>`，features 按执行问题命中多个分支。C3 记录实际采用的知识条目，不把命中的全部条目当作已执行。历史案例的原协议、失败与适用域必须保留；没有新协议下的性能承诺。

新候选使用 aprof.handoff/v3，不伪造旧 candidate_draft/RouteDecision/episode。明确授权的图外实验保留 unadmitted 与授权来源；不自动变成图训练样本。性能比较、继续父版本和最终裁决由 coordinator 推进。

## 中文技术条目的使用

features 可含 cube-api、scalar-control、fusion-composition，分别读取计算原语、地址/控制和组合交接技巧，仍可叠加旧技术分支。recipe 正文给出关键代码上下文及资源代价，不要求读取上游仓库。融合不等于省去所有 GM 中间值；只在 C2 确定的阶段、所有权、数据通路和允许的资源范围内实施。公共数值与有效域约束继续由 precision-boundaries 承接。

路由的 `attributes.platform` 使用已核验 architecture_profile 的架构标识，例如 `dav-2201` 或 `dav-3510`；产品型号仍保留为原始证据。runtime 不自动把任意型号字符串转换为架构，未知或未映射时保持未知并走保守回退。不能仅为命中模板而改写平台。

## 当前Action实例交接

按[机制与交接规则](../../workflows/references/diagnosis-v4.md)核对Action实例与目标范围。路由提示不是事实，不能改platform/family/dtype/features或facts以强行命中。P/O分别运行内部router，具体recipe由C3选择；组合结果在选择后记录。unknown可供C2分析，C3实施仍受原Action和方法前提约束。

输入复用先区分：同一原输入的多个消费者保留 UB 值，读取 [input-tile-residency](knowledge/branches/memory-transfer/recipes/input-tile-residency.md)；不同临时值共用存储读 buffer-lifetime.reuse；仅改善缓存距离读 l2-reuse-order；改变融合区间读 fusion-composition。Action ready 不能替代原值、有效地址域、生命周期和物理容量的逐项核验。选中的正文及必要支持资料随实际选择记录，不把多个命中等同于多个已执行变换。
