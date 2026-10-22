# CPU跨轮与交接回放的覆盖

这些测试使用合成观测、源码文本和FakeRunner结果；不编译AscendC、不连接NPU。测试确认协议与身份约束，不确认任意C++的语义正确性。

| 行为 | 用例位置与核对点 |
| --- | --- |
| R1→R3继续同路线 | `test_round_three_replays_complete_feedback_without_forced_action_change`：读取不可变前驱/反馈，未测预测保持待验证，不能因轮次要求换Action |
| 联合改善与回归 | `test_compound_feedback_support_and_regression_are_scoped_not_single_factor`、`test_whole_scheme_predictions_drive_feedback`：整体有效结果影响方案预测，单项归因不补造 |
| 无效计时、修复和未测 | `test_invalid_measurement_and_repair_do_not_force_new_action`：分别保留测量状态/修复理由，不把无效结果作性能反证 |
| 探索父本与重开 | `test_round_three_can_return_to_bound_ancestor_parent_with_exact_lineage`：允许回到经完整链绑定的祖先；任意同任务旁支不等于可复用父本，已验收/仅正确/失败状态分开 |
| 参数改变与重复试验 | `test_real_parameter_change_can_retest_same_prediction_but_renaming_cannot`：真实变参可回答旧预测，仅改ID不构成新信息；预算按C0外部范围继续传递，本用例不模拟预算计费 |
| 多实例、多Action与共享计划 | decision/v3、handoff/v4分别覆盖同Action不同目标和不同Action，逐成员走真实router，不合并命中文档冒充兼容 |
| 资源与保证条件 | 相交生命周期按共同峰值；共享物理分配只计一次；计划保证仍为unknown直到最终源码核实。生产者参数改变使旧消费者保证失效 |
| KEEP和重规划 | P_KEEP须完整有效共同计划；O_KEEP只是该成员不加局部优化；改P仍实施新计划，全KEEP才NOOP；越过owner/通路等许可边界拒绝 |
| 结果关联与旧交接 | 新CLI记录整个方案及每个成员实际文档；旧v1/v2决策、v3交接回放原义，禁止混装版本 |

具体断言见[decision/v3测试](../../../runtime/tests/test_action_decision_v3.py)、[handoff/v4测试](../../../runtime/tests/test_action_handoff_v4.py)、[公开CLI测试](../../../runtime/tests/test_scheme_cli.py)。完整运行命令和精确结果随[RESULTS](RESULTS.json)保存。

另有四次真正无工具模型后继请求，见[行为回放](BEHAVIOR.md)。它们检验摘要输入是否改变比较；CPU合成分支与模型无工具后继不能互相冒充覆盖。
