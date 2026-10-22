# AProf 证据契约与历史接口

新任务必须按 [soft_targets_local_v1](execution-policy.md) 执行：耗时仅为软目标，baseline 默认 assumed，新候选完整验证一次，按全输出内容复用；所有运行产物留在 /dev/shm。

Agent 阶段交接见 [公共契约](../contracts/common.md) 和 [主流程](../aprof-performance-workflow.md)。本页只说明机器接口与历史兼容，不代替 runtime 实现。机器字段名、命令和协议 ID 保持英文；说明使用中文。schema 校验只检查结构，原始来源回放才核验证据。

## 当前统一计时接口

本版新测量统一使用 `single_role_l2_clean_task_v1`。逐 case 采集记录不带永久 baseline/candidate 角色；comparison 指定 A/B 和各自源码身份，因此合格 B 可作为下一轮父版本证据。

完整请求、采集与复用要求见 [统一计时](../../skills/ascendc-aprof-profiling/references/unified-timing.md)。正式性能收尾入口为：

```bash
tools/aprofctl timing finalize --request <comparison.json> --output <new-result.json>
# 按需审计，不默认追加一次回放
tools/aprofctl timing verify --result <result.json>
```

finalize 一次完成完整 timing/correctness 集覆盖、来源、输出和 Task 回放，输出中位数比的工程验收结果。verify 重放已有结果时不重新采集 NPU。执行命令帮助以该包版本为准。

新结果没有旧 paired count 或 95% LCB 承诺，不自动成为 `candidate_episode`、策略奖励、`production_safe_gain` 或生产 best。语义、范围、可移植性及图路由是独立要求。不要将新结果填入旧 `baseline_samples_ns` / `candidate_samples_ns` 数组伪装配对样本。

## 架构、路由与机制证据

版本化 JSON schemas 位于 schemas/，runtime 同时核验跨字段关系。常用结构：

| 类型 | 用途 |
| --- | --- |
| context | workload、硬件、预算与证据视图 |
| architecture_profile | 已验证平台能力与容量 |
| parallel_plan、dispatch_plan | 算法/任务、分组/key/entry、fallback 与源身份 |
| knowledge-handoff / knowledge-route | 历史v0003/v2交接与P/O树内路由，保持原义 |
| candidate_draft | 仅历史图的合法集合、行为概率与变换参数 |
| capture_manifest、normalized_profile | 独立机制 capture 与原始 CSV/JSONL 来源 |
| mechanism_report | 同源绑定的基线/候选指标和预期方向 |

```bash
tools/aprofctl contract validate --kind <kind> --input <artifact.json>
```

保持精确字段，不向严格对象加未经定义的字段。Agent 不填写机器判决、terminal utility 或 selected_as_best。未知谓词保留未知，知识案例不能替代证据。

机制报告必须关联两侧 profile hash、真实源码、相同指标/单位和比较策略。source-bound 1.1 机制 profile 仍要求 10 次记录预热、5 次独立 capture 和 CV≤0.05；这不等于性能计时采样要求。实际字段与来源通过 [collector](../../skills/ascendc-aprof-profiling/references/collector-interface.md)生成。

<a id="task-local-gates"></a>
## 本地证据与旧 gate 边界

当前性能收尾使用上述 timing finalize；没有需要再串行运行旧 candidate gate 和 episode finalize 的步骤。新入口与原 episode schema 分开，避免改写冻结历史的统计含义。

旧命令 `candidate gate`、`exploration gate/verify`、`episode finalize/verify` 保留各自契约，用于兼容场景或历史回放；旧 measured admission 不能作为本版新测量的入口。重现历史请求时使用其冻结包、协议和证据。新 20 轮不能冒充旧 30 对。

旧 local-index 接口要求所有引用文件可访问；`--local-index` 与 `--store` 互斥，输出索引必须新建。本地操作不归档；CAS 和 append-only episode 只属于独立后续归档任务，并保留原始判决。

## 历史文档映射

- diagnosis_hypotheses：拆为 source/workload/profile 证据、非互斥 facets、反例与缺项；不从排序推断行为概率。
- profiling_plan / profiling_results：命令和人工摘要，不证明已执行或来源有效。
- single_case_diagnosis / final_diagnosis：区分小 workload、测量限制和可操作瓶颈，不把假设写成判决。
- optimization_plan：映射到版本化 transformation、参数和适用条件，不绕过图 mask。
- handler_attempt：仅结构校验的探索侧记，包含 handler/参数/父尝试/失败/下一步理由，不自动进入 episode 或训练。
- legacy JSONL：未验证历史资料，不授予 reward。

旧 SQLite 与相邻 .objects 应一起保留。不能修改旧 producer manifest 或把旧采集重新标注为新协议。新版工程结果若要进入训练系统，需另行定义兼容契约，不能为填满 schema 伪造字段。

## 知识构建、路由与结果关联

```bash
tools/aprofctl knowledge build --root . --owner parallel-planning
tools/aprofctl knowledge validate --root . --owner parallel-planning
tools/aprofctl knowledge route --root . --owner optimization --context evidence.json
tools/aprofctl contract validate --root . --kind knowledge-handoff-v4 --input C3.json
```

P/O 的 owner 分别为 parallel-planning、optimization，继续使用 knowledge 命令；当前 diagnosis 使用下节独立命令。树 route 支持 --override，严格绑定知识版本/hash，旧 policy 不跨版本套用。新 JSON 格式与边界见 [图规范](../../skills/ascendc-aprof-diagnosis/graph/FORMAT.md) 和两棵树本地 FORMAT。构建使用安全 YAML，依赖由 runtime/pyproject.toml 显式声明。

旧快照位置为 skills/ascendc-aprof-diagnosis/graph/history/versions/v0001 或 v0002；load_snapshot 与旧 fixed_supports_refutes_tri_state_v1 路由保持语义。v0003 默认确定性整数专家排序，没有 softmax 概率。


## 机制诊断v0004与Action实例

runtime 0.4.0新增严格诊断record/region/graph、retrieval、reasoning、case、proposal及action-routing、handoff/v3契约，详见[机制与交接](diagnosis-v4.md)。旧JSON schema不修改；外层阶段文档仍contract_version=1。

runtime 0.5.0增加 `diagnosis expand`／`diagnosis verify-expansion` 及独立 `aprof.diagnosis-problem-expansion-request/v1`、`aprof.diagnosis-problem-expansion/v1`，由 Agent 按需指定正文，不自动选机制或动作。另提供[观测自洽校验](observation-checks.md)，只推导同范围、同计数层级的数值。旧诊断、检索和交接保持原义。

```bash
tools/aprofctl diagnosis build --root . --parent-snapshot skills/ascendc-aprof-diagnosis/graph/versions/v0003
tools/aprofctl diagnosis verify --root .
tools/aprofctl diagnosis retrieve --root . --context /task/evidence.json
tools/aprofctl contract validate --kind diagnosis-reasoning --root . --input /task/reasoning.json
tools/aprofctl contract validate --kind diagnosis-case --root . --task-root /task --input /task/case.json
tools/aprofctl contract validate --kind diagnosis-proposal --root . --task-root /task --input /task/proposal.json
tools/aprofctl knowledge coverage --root .
tools/aprofctl knowledge validate-chain --root . --task-root /task --c1 /task/C1.json --c2 /task/C2.json
tools/aprofctl knowledge validate-chain --root . --task-root /task --c1 /task/C1.json --c2 /task/C2.json --c3 /task/C3.json
```

诊断build用于新快照注册，不覆盖已经冻结版本。检索返回全部Problem轻目录和观察邻接，不自动判断机制或选择动作。reasoning是Agent当前判断；graph只是条件化模板知识。所有reference按声明基准解析：sources.path相对完整包，任务产物引用相对task-root；文件SHA256不同于规范JSON内容hash。

`aprof_runtime.bindings.default_hint/route_parallel/route_optimization`分别生成请求范围并调用真实树router。先冻结C2 P选择，再由C3记录O选择。提示不填造facts或attributes；每个Action实例核对模板hash、scope、参数和父计划。validate-chain无需timing，通过只表示结构、身份和声明边界符合，不授予编译、正确性、性能、因果或训练资格。

历史v0003仍用`graph route --graph <v0003目录> --context <旧evidence>`，不依赖当前迁移MD。P/O继续`knowledge build/validate/route`。旧knowledge diagnosis源码入口遇新格式明确拒绝，不能偷偷改成新检索或旧快照-only校验。

## runtime 0.6.0：Action 决策

诊断 v0005、新条件策略及 action-decision/v1 共同区分实施合法性与性能假设。`diagnosis verify-decision --root <包> --task-root <任务根> --input <decision.json>` 校验身份、引用、比较、补证据状态和前轮反馈；`knowledge validate-chain` 对新图要求 C1 引用唯一 decision，实施 C3 还要求它选择当前实例且实施前必要条件满足。旧 D4 路由 bundle 和交接不增加该要求。自然语言的分析质量由独立审阅核对，不从形式通过推导收益或因果。

## runtime 0.7.0：可核查比较与分层复盘

本节描述 runtime 0.7.0 的冻结行为；0.8.0 新方案按下一节的显式 schema 分派。0.7.0 的诊断 v0006 要求独立的 `aprof.action-decision/v2`，具体字段见 [v2 contract](action-decision-v2.md)。新增完整 workload 分域、阶段工作、减少/增加/保留工作、代价与残余；所选理由引用实际比较项。R2 绑定前轮父本、候选、workload 与实际测量 case，区分结构、正确性、机制和归因；未测可以继续条件分析，不制造收益或强制换 Action。`verify-decision` 和 handoff/v3 入口不变，显式按图版本分派。v0005 仍要求 v1，v0004 仍按原规则回放；旧正文通过冻结 hash 对应的原字节档案读取，不将当前文档回填历史记录。


## runtime 0.8.0：完整方案与共同交接

新增 `aprof.action-decision/v3`、`aprof.handoff/v4`；知识仍为 D v0006、P v0003、O v0006、routing v0005，不重编冻结快照。新旧入口按显式 schema 分派，不能仅按相同 graph 版本将 v3 决策降为单机会 v2，或混装 v3 决策与 v3 handoff。历史 schema、交接、前轮链和来源身份保留原义，`knowledge.py` 不变。

v3 在机会比较之上组织方案：共同目标、成员机会/Action实例、步骤依赖、联合工作/覆盖/代价及整体预测，选择绑定 scheme_id。后继反馈评价前轮所选方案的整体预测，允许补充成员归因限制，不要求单因素或默认消融。

v4 C1 绑定 reasoning、decision 与所选方案身份；C2 对成员分别调用原 P router，记录共同计划及联合兼容/生命周期；C3 在同一确认计划下逐成员调用 O router，记录实际方法、参数、保证条件如何在最终源码兑现、变更与统一候选身份。成员目标/参数/模板身份、条件证据不能串用；组合不是独立命中的简单并集。P_KEEP 要求共同计划完整有效，P_KEEP 且全部成员 O_KEEP 才为 NOOP。

继续使用 `diagnosis verify-decision`、`knowledge validate-chain`、`knowledge link-result`，不增加日常必跑工具。结果关联保留实际成员、共同方案、交接 hash 和候选身份；有效性能结果评价整个候选，不自动证明某个成员的收益或机制。严格字段以本包新 schema 为准，流程与纸面例见[完整方案](optimization-schemes.md)。

协调者在任务根维护[optimization-history.md](optimization-history.md)三部分 Markdown，所有后继先读再按需展开历史；它不是机器证据或授权，不新增 schema 或 memory 流程。轮数、达标停止和重试范围引用 C0 的外部约定；既有正确性、计时与工程判定不变，accepted 不自动等于停止。

## runtime 0.8.1：测前映射与完整方案身份修复

当前知识为 D v0007、P v0004、O v0007、routing v0006、条件策略 v0002；新输入继续使用 action-decision/v3 和 handoff/v4，旧 schema/快照不变。新图首次正式实施前与有效反馈共用完整 workload 映射解析；缺映射可以继续分析，但不能把仅有 case 身份的任务报成实施 ready。格式和历史边界见[方案决策格式](action-decision-v3.md#完整-workload-的测前映射)。

完整链与独立交接决策校验都核对实际非空方案身份；局部成员就绪不能代替完整链。机器校验只能检查声明、引用和状态，不能证明自然语言成本理由成立。数据相关覆盖、准备工作收支与修复后的重比由[选择规则](action-selection.md)指导，并在开发自主行为验收中检验，不增加日常必跑工具。
