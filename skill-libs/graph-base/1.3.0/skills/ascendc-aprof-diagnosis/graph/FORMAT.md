# v0004 模板与关系格式

当前机器规范是包内diagnosis-record/region/graph schema；旧knowledge-record、index、route与handoff/v2只供历史回放。模板唯一源仍是symptoms、problems、actions、edges中的Markdown，重复ID或YAML键、非法关系、来源hash错误均拒绝。

## 共同字段与声明

record使用`schema_version=aprof.diagnosis-record/v1`。保留稳定id、kind、version、status、中文title、scope、sources、tags。旧learning和seed_reason原样迁移为历史先验，不用于新机制总分或自动动作选择。scope中的all不是已验证所有平台能力。

slots逐项定义name、kind、description、required；对象槽位按实例绑定，不把一个tensor的证据用于另一个。sources保存包内完整文件路径、original_path、固定revision、1-based闭区间lines、文件sha256和excerpt_sha256。正文应独立可用，来源用于追溯。

claims逐项包含id、text、basis、source_indexes、review_status和limitations。basis区分source_statement、code_fact、mechanism_inference、case_support和legacy_seed。来源审阅、模板active状态和任务判断分别维护；旧内容不直接升级为已验证机制。review分别说明source_credibility、discriminating_power、observed_frequency及gaps，不混成单一权重。

## 类型职责

- Symptom保留view和evidence规则，observation补object_slots、comparison_basis、unknown_when、interpretation_boundary和required_components。字段值／源码观察与机制解释分开，复合观察明确all-of成员，单位与分母范围不可省略。extractor未实现保持原状态。
- Problem的analysis补mechanism_chain、objects_and_stages、predictions、supporting_checks、counter_checks、具体alternatives及辨别check、可考虑actions的干预前提／代价与limits。必要概念和机制正文写全，不用“其他相邻问题”替代可区分解释。
- Action保留transformation、原preconditions[{fact,state}]、invariants与expected_effect；instantiation补target_slots、required_bindings、effect、costs、unknown_policy、replan_triggers。不同意图不复用旧ID，原前提不得放宽。
- 边保留from/to/relation和历史conditions，binding补object_bindings、joint_requirements、exceptions、rationale、discriminating_checks。支持／反驳／可缓解及P之间alternative_to、may_coexist、may_cause均是条件知识；联合要求不是单边充分因果。

## 实例、构建与扩展

任务推理、案例和提案不放进graph节点目录。当前任务写私有工作区；包内examples是paper演练，proposals是不具执行资格的知识草案。详细状态、证据身份、两阶段路由和晋升见[机制与交接](../../../workflows/references/diagnosis-v4.md)。

新增知识先查旧模板和来源，说明差异及适用域；新Problem可以没有Action。新family/branch不自动造Action，方法在P/O内部选择；路由提示不能代替facts或架构证据。独立复核和contract校验后才注册新快照。

使用`diagnosis build --root <包> --parent-snapshot <父快照目录>`构建，`diagnosis verify --root <包>`复核源和lineage。首迁移v0004显式父v0003，文件SHA256不同于handoff规范JSONhash。冻结快照不可覆盖，旧v0003显式graph route回放。
