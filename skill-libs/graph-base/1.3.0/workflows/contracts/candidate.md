# candidate：候选实现与完整正确性

新任务必须按 [soft_targets_local_v1](../references/execution-policy.md) 执行：耗时仅为软目标，baseline 默认 assumed，新候选完整验证一次，按全输出内容复用；所有运行产物留在 /dev/shm。

生产者：[优化角色](../agents/optimization.md)。消费者：协调者和采集。使用 [公共契约](common.md)，`stage=candidate`、`role=optimization`，candidate_id 必须为本次候选。

## 输入

引用 preparation、主假设的 diagnosis、有效 planning、准确的图路由/变换和实际父版本。明确授权的图外实验改为引用该授权与无路由原因，按下述独立记录规则执行。重试或修复额外引用前次失败。协调者明确修改范围、预算与完成条件。

## 必需结果

| 字段 | 内容 |
| --- | --- |
| 实现意图 | 关联假设、参数、预期作用、反证/停止条件；一个意图可包含配套 Host/Kernel 修改 |
| 实际改动 | 隔离工程、父子关系、修改文件与关键差异，是否触及计划边界 |
| 源码与实现 | 冻结 source、binary、构建来源、候选 dispatch 的实际实现身份 |
| 静态检查 | API、容量、越界/尾块、同步、可移植性和语义范围的结果及依据 |
| 构建 | argv/cwd、工具、退出码与日志引用 |
| 完整正确性 | 原 oracle、完整 correctness case、输出与同源回执引用；不能只测代表集 |
| 采集准备 | 统一采集配置、完整 kernel 序列、native adapter、已准备输入及对应 correctness 引用 |

历史图回放有合法路由时，`outputs` 引用 candidate_draft、源码/补丁、binary/构建回执、重新绑定的 dispatch、完整 correctness 和采集配置。当前v0004使用下述v3 handoff，构建/正确性/计时模型保持现有 schema；旧 `candidate_plan.json` 若含有有用实现细节可引用，不再另写同义计划报告。

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
意图、参数、改动范围及预期机制：
源码/二进制/dispatch 身份和构建引用：
审查与完整正确性覆盖/回执：
计时 adapter/config、输入与 kernel 序列引用：
实际成本：

## 缺项与失败
首个失败、命令/退出码、未验证范围或重规划原因：

## 交接建议
可进入候选采集，或需补项/修复/重规划；附必需引用：
```

## 当前交接 C3（handoff v3）

C3自行调用优化router，在已确认P计划与自由度内选择实际recipe、有序配套方法和参数；不把全部命中条目当执行结果。逐条核验注册Action原fact/state、目标范围及方法条件，unknown/proxy不能授权实施。

绑定C2的P选择、Action instance ID/hash、目标、参数与计划身份，记录实际源码、dispatch及变更。O_KEEP仅不追加局部优化；P_CHANGE时仍需实现新计划，允许源码变化。双KEEP为NOOP。实际组合在选择后形成结果快照，不是C1/C2预先白名单。

`knowledge validate-chain`可在没有timing时检查身份、声明与边界；通过不等于构建、正确性、性能或因果通过。真实实现后仍遵守原同源构建／correctness／timing契约。新证据创建后继交接，发现越界返回C2。历史v2单独回放，不混装。
