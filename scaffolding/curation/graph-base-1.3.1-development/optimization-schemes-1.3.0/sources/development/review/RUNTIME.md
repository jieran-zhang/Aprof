# 独立runtime技术复核

当前范围内未留下已确认的重大未解决问题。只读复核action_decision_v3、bindings_v4、新schema及公开dispatcher/CLI；未改实现，未运行硬件或训练。

## RR-001 [P2] 保证回执未绑定生产者实际参数：已修复并独立复测

原_checks只绑定目标消费者actual_parameters摘要。生产者在许可域内变参而消费者/源码不变时，旧保证没有关联整体配置，可能继续补消费者unknown。

实现代理复用configuration_hash(selection, execution=execution)加入保证回执；当前核验位于runtime/src/aprof_runtime/bindings_v4.py:278，覆盖共同计划、源码和所有成员实际参数，没有新增流程或生产者字段群。

独立复测使用真实D6的coalesce_contiguous_transfers+batch_writeback链：初始保证通过；仅生产者tile64→128、刷新member/joint兼容身份而保持旧保证时拒绝；重绑保证配置hash后通过。计划fact保持unknown。证据：producer-parameter-postfix.json。

首次修复前脚本与schema升级并发，因新必需字段结束；不把它当成功绕过。修复前缺口由独立源码审查及实现者确认，修复后的拒绝/通过路径由审查者独立运行。

## 其余检查

v3决策与v4交接按显式版本分派，旧v3链仍要求冻结D原有v1/v2决策。方案、成员、模板/目标/参数、共同计划及逐成员P/O路由相连。P_KEEP允许成员为完整计划的target子集，不扩大current范围。资源按互斥dispatch group内timeline核算峰值，不要求新增pool枚举。

计划保证不注入facts；依赖、scope、bool期望、源码locator和最终配置均核验，已知反向前提仍需新不可变推理。性能unknown、实施合法性与收益验证分开；联合候选整体可评价，不能自动分配成员因果。摘要保持三部分Markdown导航，不替代证据/授权。

两个新schema通过Draft202012结构检查。knowledge.py、旧handoff及v3 schema经git diff核对无本次工作树差异。初审common.md:72/95的版本矛盾已修复。

未检查：未独立重跑全runtime/历史回归；实现代理的测试不冒称本审查者执行。hash/locator及声明不证明任意C++语义或硬件效果，没有硬件或训练。
