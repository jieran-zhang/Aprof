# Teacher 更新规则

## 按对象分配证据

| 目标 | 有效训练信号 | 不足以支持的材料 |
| --- | --- | --- |
| symptom 内容/predicate | 可重复核验的源码、workload 或 profile 特征，单位/分母/平台明确，含正例与边界反例 | 只有“整体变快”；把 unknown 补成 false；未实现 extractor 冒充自动特征 |
| problem 内容 | 独立机制证据、与替代解释的区分、适用域与反证 | 仅因某 action 排名第一就认定机制成立 |
| action 内容 | 可检验的变换、清楚的硬前提/不变量/预期机制变化 | 把具体 tile 值、完整模板或无效实现失败当成机制 |
| supports/refutes 边 | symptom 已知，problem 有独立核验；关系命题成立/不成立 | 仅凭最终 speedup 给诊断边奖励；缺字段充当反证 |
| mitigated_by 边 | problem 已核验，action 确实执行，比较隔离了该变换，正确性和统一计时完整 | 被推荐但未执行；多 action 联合成功后各加一分；基础设施失败 |
| planning router/模板 | C2 真实选中，C3 遵守方案；同条件、同预算的方案比较，所有权/归约/容量合法 | 只读过模板；实现偏离计划；未实施的备选自动算负例 |
| optimization router/recipe | C3 真实采用，执行条件和源码能核对；隔离执行方法的比较或可复现的实现缺陷 | 编译环境故障归因 recipe；代码未使用该方法；计划变化仍归原执行方法 |

命题状态是 supported/refuted/inconclusive，不等同于最终 admission。一个 memory 可同时支持“容量公式正确”、反驳“此 shape 值得双缓冲”，且无法判断“该 symptom 能区分带宽瓶颈”。分别记录，不合成一个总 reward。

## 内容和结构更新

1. **refine**：补充分母/单位、条件、失败特征、约束或证据；来源与原限制都保留。正文缺陷修复不需要捏造性能收益。
2. **add**：现有节点或知识叶条目无法表达时才新增稳定 ID。一次来源可生成带范围的候选 example；活动通用规则需要跨任务支持及相应验证。
3. **split**：同一条目在可观察条件下出现稳定不同响应，子项分别有支持；不要按算子名字、case ID 或结果标签拆分。
4. **merge**：机制/前提/效果等价且无被抹去的反例，保留旧 ID→新 ID 的 lineage；仅标题相似不够。
5. **deprecate**：证据推翻或被替代，先移出活动路由并保留旧版本，不删除历史记录。

图中新边明确 `supports/refutes/mitigated_by`、适用条件、来源和 seed_reason，按原 1/2/3 专家规则初始化；refutes 的 weight 始终非负。新增结构与参数学习分轮验证，以便定位收益/回退。symptom.gain 初期保持 1、problem/action.bias 保持 0，防止三种参数同时移动而无法解释。

知识树有唯一主归属，父子无环；跨分支用 references。planning 的骨架/容量公式/伪代码/片段与 optimization 的操作步骤/验证/失败特征按各自 FORMAT.md 补全。修改 router 的 match/exclude/required_evidence 属于内容/结构变化；不能用调分绕过硬条件。fallback 保持 0。

候选学习材料先保留在训练 run 的 proposals，不能把 `draft` 填入只接受 active/deprecated 的原记录 schema。通过相应验证后才在候选包中成为 active。新增来源复制到所属知识区 sources，记录固定修订、原路径、行号、文件/片段 hash 与许可证；不能在发布包里引用会消失的本机 memory 绝对路径。

## 初版参数学习

仅更新原生边 weight 与非 fallback router 的 prior_score。原 1/2/3 是起点；学习后允许有限非负实数，仍是排序分数，不是概率或预期加速比。配置值见 [admission-policy.json](admission-policy.json)，属于待校准的初版工程约束。

每个目标先选**可归因且同域**的观察。按 operator/group 归并；同一候选的重测、多个 case、重复 memory revision 只算一次，组内先求均值，算子组等权。留出数据不参与参数计算。

- 诊断边：独立核验的关系成立为 +1，被反例推翻为 -1。对 refutes，“独立证据确实反驳该机制”为 +1，反证关系被推翻为 -1；不能再次把负号放进 weight。
- 动作边：隔离变换、证据完整且 accepted 为 +1；完整正确但稳定无收益/回退为 -1；多动作未隔离、证据不足、执行错误、基础设施失败均不作性能标签。
- 两棵树的路由：比较的两个真实方案/recipe 具有相同任务、父本、资源与预算，胜者 +1、败者 -1；无法区分为 0。只有一个实现成功时可记可行性案例，不足以训练相对排序。

令 n 为有效独立训练算子组数，z 为组信号的等权均值，候选变化为：

```text
delta = clip(update_gain * n / (n + shrinkage) * z, -max_delta, max_delta)
w_candidate = clip(w_base + delta, score_min, score_max)
```

默认 `n>=3`、`update_gain=0.5`、`shrinkage=5`、`max_delta=0.25`、范围 `[0,3]`；不足支持保持原值。该式用于生成候选，不能凭公式通过就晋升。每轮固定 base 和完整数据集合，同一 proposal 重跑得到相同覆盖；跨轮继承 parent 时保存已消费 observation 指纹，不能把相同数据再当新增支持反复加分。若重拟合全部数据，则回到声明的同一 anchor 参数。

目标全正也只表示已观测上下文有正信号；未知上下文没有反事实结论。没有确定的行为概率，禁止声称 IPS/DR 或因果估计。支持相反时先检查适用域，不直接用大权重抹平条件差异。

## 候选交付

`aprof.knowledge-update/v1` 的 changes 逐条填写 target_id、操作、before/after 原字节引用、理由和 memory/attempt/claim 关联。参数提案的 candidate_artifact_ref 指向原生 override；内容/结构提案指向新编译图或树，相关 Markdown 在 changes 中引用。

使用候选包自带工具对三个 owner 构建、校验、路由，保存命令与输出。编译产物、GRAPH/ROUTER 和初始化索引由源 MD 生成。`REGION.json` 与条目版本随内容变化更新，已冻结快照不覆盖。评估失败保存 proposal 与报告，运行入口继续指向 base。
