# 独立决策运行时审阅

审阅包：`skill-libs/graph-base/1.3.0`；基线为任务冻结包。审阅者未修改公共文件。本包保存报告、问题清单和复验摘要；生产回归用例位于包内 runtime/tests/test_action_decision_v2.py。应用 ponytail 技能，重点检查能改变实际选择/交接的身份约束与过度阻断。

## 结论

发现并用 CPU 反例复现 5 项问题，已由实现 agent 修复。独立复测：4 个原绕过输入现在正确拒绝；匹配 workload、候选身份的有效统一计时反馈正确接受；最终增量进一步允许只测冻结语义域的一部分 case，完整域无需回填。当前没有已确认的未修复阻断问题。

- 正常统一计时绝对 request 路径误拒。
- 同任务另一候选/另一 workload 的结构与正确性证据被借用。
- `collect_evidence` 标签与 `experiment` 选择组合绕过继续检查并允许 C3 实施。
- `measured_domain_ids` 未与真实计时 case 交叉核对。
- 替代机会的同名预测覆盖当前所选机会的判别预测。

详细定位和修复见 `issues.json`。行号指发现时隔离快照，修复后行号会变化。

## 可回放证据

生产回归用例见 [v2 CPU 测试](../../../../../skill-libs/graph-base/1.3.1/runtime/tests/test_action_decision_v2.py)。它们使用 FakeRunner 合成计时，不代表设备性能。本次审阅先在修改前模块确认缺陷存在，再以 `fix-verification.json` 记录四个正确拒绝和一个合法部分测量接受。原缺陷模块 hash 保存在报告末尾，维护工作区的临时探针不是最终包的运行依赖。

从包根运行：

```bash
python -m pytest -q runtime/tests/test_action_decision_v2.py
```

## 范围与判断

审阅了 action_decision.py 的显式 v1/v2 分派、action_decision_v2.py、v2 schema、新增测试、主 workflow、action-selection 及 C1/C2/C3/C5 contract 文本。保留 v5→v1、v6→v2 显式映射与冻结知识策略；没有自动把新约束写回旧图。新比较要求实际工作/覆盖/代价项引用，单机会允许合理说明，同 Action 不要求轮换，性能 unknown 与实施安全仍分开。未注册意图能参与比较但不能直接进入正式实施。

复现使用冻结 v5 fixture 包，仅将测试期 required_decision_version 替换为 v2 以独立验证新语义；v6 正式图发布、全包原有测试及旧快照 hash 审计由主任务负责。本审阅没有运行设备、训练或网络操作，没有证明实际加速，也不把 JSON 字段完整当作自然语言理由正确。

最终增量：新增 measured_case_ids 精确对应真实计时case；measured_domain_ids 仅表示相交的语义域，既不扩大局部测量覆盖，也不要求事后修改冻结R1。最后正例的原域含 case 1/2，真实测量仅 case 1；校验应接受该局部反馈。公共v2契约还应同步新增字段与attempt_identity回执，已提醒实现agent。

发现时模块 SHA256：`0344413c669d6624bc63b50c58f47218604404c884dd2aff634898f580278d7c`。
修复复核模块 SHA256：`801e20eabde9f3a9dbc91cf13ad69a4d512ea1c9d9e36e7da448b6f60de2d398`。
