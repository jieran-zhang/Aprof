---
name: aprof-train-knowledge
description: 离线审阅冻结的 APROF 优化 memory，更新 diagnosis 图及 planning、optimization 知识树的内容和排序参数，产生有来源、可回滚、经留出验证的候选知识版本。
---

# 从优化 memory 学习知识

这里的训练对象是三个知识区的 Markdown、结构与排序参数，不是基础模型权重。输入是 memory 集合、冻结基础包、训练/验证划分与 [准入策略](references/admission-policy.json)。只生成版本化候选，不在运行中的 skill-lib 上热更新。

1. 按 [数据准入与验证](references/admission.md) 固定数据快照和评估范围；使用 [共享校验器](../../tools/validate_learning_records.py) 检查记录，完整回放所需的 runtime 证据。建立纳入/排除清单，成功、失败、未知都保留。
2. 只从 train 提炼命题。按 [更新规则](references/updates.md) 判断修改 graph 的 symptom/problem/action、边，还是某棵树的 router/strategy/template/recipe/example。先查同义条目，优先局部 refine，保留反例、适用域与来源。
3. 在隔离副本中做一组可解释的修订；用 `aprof.knowledge-update/v1` 保存 base、memory、claim、before/after、理由与预期效果。参数更新使用原生 `aprof.knowledge-override/v1`；内容/结构变更走新版本构建，不手改生成图。
4. 跑格式/来源/确定性构建与路由回归。由独立 evaluator 使用冻结的 validation 任务、相同模型/预算/统一计时方法比较基础版和候选版。evaluator 不为 Teacher 提供可回填的训练标签。
5. 输出候选 diff/override、全部支持和反例、剔除原因、CPU 回放、独立评估与失败记录。未满足相应门槛就保持 candidate/deferred；达到门槛才标 validated_candidate。发布与默认切换是后续显式操作。

若没有任何可支持的修改，只交付 deferred 审查报告、纳入/排除清单和补证据计划；不为凑齐 knowledge-update 的必填字段捏造 claim、节点或空洞补丁。该契约用于已经有具体改动的提案。

三个知识区的边界沿用基础包的 FORMAT.md：diagnosis 提供机制与可检验变换方向；planning 给算法、任务所有权、容量与模板；optimization 给计划内的具体执行方法。Teacher 不修改 coordinator 的预算、oracle、测量 gate、硬前提或 schema 来让候选过关。

旧 v2 memory、旧 Wiki 和旧计时结果可以帮助提出问题或补充带原协议标记的案例；它们不能无转换地充当新性能权重标签。确定性路由没有已知探索概率，不捏造 propensity，也不使用旧 `policy train` 训练 v0003。

任务要求仅审阅或制定提案时交付提案；要求实际训练时按上述流程产出候选文件与验证报告。当前没有授权硬件时，完成 CPU 可做部分并将实测门槛明确列为 pending，不能用 replay 替代端到端收益。
