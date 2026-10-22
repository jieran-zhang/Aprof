# candidate：候选实现与完整正确性

新任务必须按 [soft_targets_local_v1](../references/execution-policy.md) 执行：耗时仅为软目标，baseline 默认 assumed，新候选完整验证一次，按全输出内容复用；所有运行产物留在 /dev/shm。

生产者：[优化角色](../agents/optimization.md)。消费者：协调者和采集。使用 [公共契约](common.md)，`stage=candidate`、`role=optimization`，candidate_id 必须为本次候选。

## 输入

后继先读[跨轮摘要](../references/optimization-history.md)，按需展开相关记录。引用 preparation、[code-understanding 报告](code-understanding.md)、方案及成员的 diagnosis、有效共同 planning、逐成员合法路由/变换和实际父版本。复用当前算法、分派、数据所有权和依赖解释，按实际改动核对受影响源码，不重做全量理解；相关条件改变时使用局部更新后的理解后继。明确授权的图外实验改为引用该授权与无路由原因，按下述独立记录规则执行。重试或修复额外引用前次失败。协调者明确修改范围、预算与完成条件。

## 必需结果

| 字段 | 内容 |
| --- | --- |
| 完整方案 | 关联方案/成员实例、共同目标、参数、步骤与依赖、预期工作变化和验证预测；必要的 Host/Kernel、搬运、转换、计算、尾块、同步共同实施 |
| 组合实现 | 各成员实际方法/参数/源码变化、保证条件如何由最终源码兑现、共同存活资源与组合兼容依据；不能把独立命中并集当成可执行方案 |
| 实际改动 | 隔离工程、父子关系、修改文件与关键差异，是否触及计划边界 |
| 源码与实现 | 冻结 source、binary、构建来源、候选 dispatch 的实际实现身份 |
| 静态检查 | API、容量、越界/尾块、同步、可移植性和语义范围的结果及依据 |
| 构建 | argv/cwd、工具、退出码与日志引用 |
| 完整正确性 | 原 oracle、完整 correctness case、输出与同源回执引用；不能只测代表集 |
| 采集准备 | 统一采集配置、完整 kernel 序列、native adapter、已准备输入及对应 correctness 引用 |

历史图回放有合法路由时，`outputs` 引用 candidate_draft、源码/补丁、binary/构建回执、重新绑定的 dispatch、完整 correctness 和采集配置。新方案使用下述 v4 handoff 与 action-decision/v3；旧 v0006/v2 决策及 v3 handoff 仍按历史原义回放，构建/正确性/计时模型保持现有 schema；旧 `candidate_plan.json` 若含有有用实现细节可引用，不再另写同义计划报告。

明确授权的图外实验在本文结果中记录 `unadmitted`、授权来源、实际意图和缺少图路由的原因；不生成伪造的 candidate_draft/图边。其余源码、计划、构建、完整正确性和采集条件仍须满足。若允许性能测量，可继续同一 C4/C5 工程计时，decision 必须保留图未准入标记；性能 accepted 不改变该标记或产生旧 episode/奖励。任务内临时Problem复用注册Action属于当前支持路径，保留假设身份；临时新Action仍先提案，不利用图外实验说明绕过前提。

## 完成与退回

只有审查、构建和完整正确性均通过且计时必需资料齐备，才 completed 并建议 `timing_candidate`。正确性证据使用 [统一计时协议](../../skills/ascendc-aprof-profiling/references/unified-timing.md) 的支持格式。

首次强制检查失败返回 failed，保留部分产物，不进入性能计时。缺工具、adapter、输入，或没有合法路由且不满足上述图外授权条件时，返回 needs_input。发现要改变算法/所有权等计划边界，先返回重规划需求，再由协调者分派 planning，不能私自沿旧计划继续。

修复是新尝试；原失败保持。性能比较和最终接纳由协调者调用采集及 runtime 完成，优化角色不写生产 best 或奖励。

## 正文填写模板

```markdown
## 请求
候选 ID、父版本、诊断/计划/路由引用、修改目标、范围与预算：

## 结果
完整方案、成员/依赖、参数、改动范围、实际工作变化及预期机制：
源码/二进制/dispatch 身份和构建引用：
审查与完整正确性覆盖/回执：
计时 adapter/config、输入与 kernel 序列引用：
实际成本：

## 缺项与失败
首个失败、命令/退出码、未验证范围或重规划原因：

## 交接建议
可进入候选采集，或需补项/修复/重规划；附必需引用：
```

## 当前交接 C3（handoff v4）

C3 对每个方案成员自行调用优化 router，在已确认P计划与自由度内选择实际recipe、有序配套方法和参数；不把全部命中条目当执行结果。逐条核验精确模板版本的实施fact/state、目标范围及方法条件。v0005 的性能假设不作为实施安全门禁；地址、依赖、精度、API、容量等具体合法性缺项仍须补齐。新增 action-decision/v3 必须选定覆盖这些成员实例的方案试验，实施前必要请求已完成；见[选择规则](../references/action-selection.md)。

绑定 C2 的共同 P 计划，以及每个 Action instance ID/hash、目标、参数与计划身份，记录实际源码、dispatch 及变更。逐成员 O_KEEP 仅不追加对应局部优化；P_CHANGE 时仍须实现新计划。P_KEEP 且所有成员 O_KEEP 才为 NOOP，空命中或缺证据不能转换为 KEEP。实际组合在选择后形成结果快照，不是C1/C2预先白名单。

`knowledge validate-chain`可在没有timing时检查身份、声明与边界；通过不等于构建、正确性、性能或因果通过。真实实现后仍遵守原同源构建／correctness／timing契约。新证据创建后继交接，发现越界返回C2。历史 v2/v3 单独回放，不混装。多成员规则见[完整方案](../references/optimization-schemes.md)。

## 实现与工作预测核对

C3 对照当前决策中减少、新增、保留的工作和适用域，说明实际 patch 是否实现；必要初始化、转换、同步与临时存储同样计入代价。阅读 recipe 不表示已采用，部分原理参考不能记成完整方法。发现计划外访问顺序、owner、通路或同步拓扑变化返回 C2；仅在许可自由度内调整参数。新增保护、扫描、软件算术或整域回退使关键成本/覆盖改变时，依照[选前比较与修复重比](../references/action-selection.md#工作量覆盖与代价怎样影响选择)回传 C1，形成同轮决策/交接后继；即使没有规划越界，也不能只因正确性修好继续沿用原收益理由。

正确性修复独立记录为新尝试。它可以维持原 Action，不算另一种性能机制；未测计时不填性能支持。新方案采用 action-decision/v3 和 handoff/v4，历史 v0006/v0005 保留 v2/v1 决策；实施前提按精确模板版本校验。联合候选整体结果可评价，缺少消融仅限制单项归因；不要求单因素、按 Action 数分轮或先测中间候选。
