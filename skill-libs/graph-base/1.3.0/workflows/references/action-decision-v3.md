# 完整方案的决策与交接格式

runtime 0.8.1 新任务使用 `aprof.action-decision/v3` 和 `aprof.handoff/v4`。行为规则见[完整方案](optimization-schemes.md)，严格字段见包内 [decision schema](../../schemas/action-decision-v3.schema.json) 和 [handoff schema](../../schemas/knowledge-handoff-v4.schema.json)。旧 v1/v2 决策和 v2/v3 交接按原协议回放，不向旧文件添加新字段。

## 完整 workload 的测前映射

D v0007 及其后继的新方案在首次正式实施前冻结 `cases[{case_id,workload}]`，每个 workload 是采集器将写入 capture 的完整 payload，包括相关 shape、dtype、属性、范围、oracle 身份等。沿用现有 `path_overview.workload_ref` 引用该文件，reasoning scope、完整 case 清单与后继反馈绑定同一身份；原始矩阵和生成/转换规则保留在已有来源引用中。不增加 schema 或必跑脚本。

首轮与有效反馈共用完整映射解析；case ID 必须唯一且完整覆盖，完整 payload 与实际 capture 精确一致。只含 case ID 或原始矩阵行仍可用于理解和条件分析，但不是完整测前映射，不能让正式实施先通过、到后继才暴露缺口。不要靠忽略额外字段或只比较 shape/dtype 来修复不一致。

D v0006 历史首轮接受的原矩阵保持原义；其原反馈缺口不会被事后投影追认为测前冻结。历史对应关系可以独立审查并用于有范围的后续推理，必须标明形成时间与归属限制，不覆盖旧决定或升级其准入状态。新任务从首次决定使用完整映射，旧协议明确按冻结版本回放。

## C1：从机会比较到一个方案

`opportunities` 继续保存各机制、注册 Action 实例、源码依据、性能假设和实施条件；没有注册意图的机会可以参加分析。`schemes` 组织准备共同实施的成员，`selection.scheme_id` 指向所选方案。

| 部分 | 内容与边界 |
| --- | --- |
| 身份 | 同一 task、Context、父实现、完整 workload、冻结 routing 与 condition policy；不能以摘要替代引用。 |
| `members` | `opportunity_id`、`action_instance_id`、角色和组合理由；同一 Action 的不同实例不合并，多个 recipe 也不自动产生多个 Action。 |
| `steps` | 成员、依赖和保证条件；依赖须有向无环。保证写明确谓词、期望 bool、目标实例和依据，不注入原始 facts。 |
| `analysis` | 联合 `work_delta`、全域 `coverage`、`tradeoffs`、`residuals`、`work_accounting`、`resource_lifetimes`。共享物理工作只算一次，各项数量带单位、符号和源码依据。 |
| `predictions` | 整体方案的源码工作预测与性能预测；成员保留自身假设。未做消融时可以评价整个候选，不能自动分配成员收益。 |
| 选择依据 | 绑定联合比较项及最强可行替代，说明理由和什么条件会改变选择。没有合理替代时解释，不凑数量。 |

联合工作变化可以是 `reduced`、`added`、`retained` 或 `rescheduled`。`rescheduled` 表达调用数或字节数不变、发射和消费顺序改变等调度机会；它不是实际重叠或收益的证明。将原样保留的工作标成 `retained`，不能把它当作减少工作或调度收益。

已知实施反证不能由一个计划保证覆盖。未知性能允许有依据的试验；未知合法性可以进入条件规划，最终实施须核实。计划保证与原始事实的状态分别保存。

## C2/C3：共同计划和逐实例实际选择

C1 的 `decision_ref`、`scheme_id`、`scheme_hash` 绑定精确方案。C2 的 `selection` 使用 `aprof.scheme-selection/v1`，保存共同计划、父计划、许可自由度，以及逐成员真实 P route、选择和兼容依据；此时不锁定 O。

C3 针对同一共同计划逐成员运行 O router，并记录实际参数、recipe、变更、候选源码及 dispatch。共同资源按互斥 workload group 内的完整生命周期核峰值；同次执行的多个阶段不能拆成 group 来规避共同容量。兼容性同时绑定计划、实例、实际参数和源码，参数在许可域内变化也要重新确认相应组合。

保证核实绑定产生步骤、目标实例、模板、作用范围、期望/实际 bool、参数、共同计划、候选源码及有效定位；`configuration_hash` 覆盖包括生产步骤在内的全体成员实际参数。机器检查这些声明和身份；源码是否真的兑现自然语言保证仍需语义审阅，不要求额外的日常脚本或逐步编译。

P_KEEP 复用完整有效计划；成员 O_KEEP 不追加局部方法。P 改变仍须实现共同计划。全 KEEP 的 NOOP 不能伪装成新候选并关联收益。

## 后继与结果关联

`previous_feedback` 引用前轮不可变决策及实际尝试。`prediction_updates` 评价前轮所选方案的预测，`same_scheme_reason` 解释继续路线的依据，`reassessment.next_step.scheme_ids` 指向重新比较的方案。R3 及以后沿用同一规则，轮次上限来自外部任务。

当前父本通常选前轮父本或候选。需要回到更早保留的父本时，`previous_feedback.parent_history_ref` 显式指向同任务 v3 线性祖先链中的决策，当前父本必须与该祖先已绑定的 parent 一致。逐条核验引用及 task、知识、workload 等身份；摘要和同任务旁支文件不能授权任意回退，旧计划及就绪证据还须核对当前适用性。旧协议任务继续按冻结版本执行，不原地改包或把 v1/v2 反馈混入新链。

协调者先读[跨轮摘要](optimization-history.md)，再按需展开原始记录。有效整体结果、单项归因、结构实现、正确性及计时有效性分别讨论；未测和无效计时不变成机制反证。

沿用以下入口，按需使用，不增加必跑命令：

```bash
"$APROF_PACKAGE/tools/aprofctl" diagnosis verify-decision --root "$APROF_PACKAGE" --task-root "$APROF_TASK" --input "$APROF_TASK/decision.json"
"$APROF_PACKAGE/tools/aprofctl" knowledge validate-chain --root "$APROF_PACKAGE" --task-root "$APROF_TASK" --c1 "$APROF_TASK/C1.json" --c2 "$APROF_TASK/C2.json" --c3 "$APROF_TASK/C3.json"
"$APROF_PACKAGE/tools/aprofctl" knowledge link-result --root "$APROF_PACKAGE" --task-root "$APROF_TASK" --c1 "$APROF_TASK/C1.json" --c2 "$APROF_TASK/C2.json" --c3 "$APROF_TASK/C3.json" --timing-ref "$APROF_TASK/timing-ref.json"
```

`timing-ref.json` 仍含 `path`、`sha256`、`candidate_id`、`protocol`；相对路径以引用文件所在目录解释。`--task-root` 可省略，结果关联默认使用 C1 文件所在目录。关联核对实际源码、父本及候选，保存成员和实际 P/O 正文快照，不重复已经完成的 timing finalize，不产生旧 episode、训练奖励或机制因果结论。
