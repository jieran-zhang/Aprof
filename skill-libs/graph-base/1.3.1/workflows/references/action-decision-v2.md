# Action decision v2 实施接口

适用：诊断 v0006、runtime 0.7.0。此 contract 约束选择记录和轮次反馈，不证明性能或自然语言判断。

## 兼容与入口

- `action_decision.validate_decision(...)` 原接口不变，输入原对象按 schema 分派；没有投影成 v1 再遗漏新字段。
- `required_decision_version(artifact)`：D4 及之前无必需 sidecar，D5 要求 v1，D6+ 要求 v2。新图不能用 v1 绕过完整比较。
- `validate_handoff_decision` 识别 v1/v2，严格要求唯一 sidecar、正确图版本及实例。
- v1 schema 原字节不改。旧前提 true/false、冻结 policy、完整身份、知识正文定位、Action readiness、性能 unknown 处理共用原 validator。
- v2 后继只引用 v2 前轮；不自动改写历史 v1。需要新图开始一轮时形成新的首轮选择记录，保留历史作为来源，不冒充同轮次后继。

## v2 必需增量

`path_overview`：

- `workload_ref` 必须等于 reasoning.current.workload_ref。
- `case_ids` 来自真实引用的 workload JSON：支持 `{case_ids:[...]}`、`{cases:[{case_id|id:...},...]}`、顶层 case 数组。单 workload 无 case_id 使用 `singleton`；不按位置臆造身份。case 名称只做成员身份，不能生产分派。
- `domains`：id、case_ids、predicate、supported_scope、fact_ids。成员穷尽且无重叠，条件/支持范围需独立语义复核。
- `stages`：id、domain_ids、fact_ids、behavior。覆盖所有域。
- `baseline_work`：每阶段至少一项。每项含 id、stage_id、domain_ids、change=baseline、quantity、explanation。

每个 opportunity 新增 `analysis`：

- `intent_gap`：仅未注册意图填写；此时 action_id=null、action_instance_id=null、performance_hypotheses=[]。可以比较或选 collect_evidence，不可进入正式 C2/C3。
- `work_delta` 与 baseline_work 结构相同，change 为 reduced/added/retained。
- `coverage`：id、domain_id、status、region、fact_ids；每域恰一项。状态 affected/partial/unchanged/inapplicable/unknown。
- 原 `case_ids` 精确对应 affected/partial/unknown 域的 case；全不适用或未变的比较机会可为空，但不能选为 experiment/conditional_plan。
- `tradeoffs`：id、domain_ids、dimension、change（quantity）、consequence。无额外代价可以写有依据的 qualitative，不强制虚构数值。
- `residuals`：id、domain_ids、remaining_work、next_step、fact_ids。未完全覆盖域必有残余记录。
- `no_alternative_reason`：没有合理最强替代时说明路径审查结论，不凑数量。

`quantity`：mode=exact/range/symbolic/qualitative；expression、unit、symbols[{name,meaning,unit}]、basis=source_logical/compiled/measured/inference、fact_ids。exact 额外必须 value（有限数）；range 必须 bounds={lower,upper}（有限且有序）；symbolic 必须解释符号；qualitative 无需编造量。测量量必须有 profiling 事实。所有 fact 必须已知并与当前实现、workload、目标、阶段完整 scope 一致。 已在正文给出可数公式时，使用 symbolic 并逐项说明符号和物理单位；不能把公式塞入 qualitative 或用“work”之类通用标签代替字节、次数、元素等单位。流水可能缩短等待是机制推导，不能改标为实测时长或已经发生的工作减少。

`selection.comparison_basis`：每项 opportunity_id、item_ids、role、decision_effect、reversal_condition。item_ids 引用实际 analysis 条目，必须同时说明所选 benefit（只能 reduced 工作项）、cost、coverage；有残余则 residual；有最强替代则 alternative。不能借其他机会凑比较项。语义仍需独立复核，程序不从运算/字节/同步相加推出性能总分，也不强制最大覆盖获胜。

`previous_feedback.reassessment`：

- `attempt`={parent_ref,implementation_ref|null,change_ref|null,workload_ref}。父本/workload 绑定前轮；候选与变更引用同时存在。真实结构/正确性判断不能没有候选。有效测量时还绑定 timing request 的 candidate_source_sha256。
- `structure`={state:realized/partial/not_realized/not_implemented/unknown,evidence_refs,finding}。
- `correctness`={state:passed/failed/not_tested/unknown,evidence_refs,finding}。
- `measured_case_ids`：精确等于真实有效 result.cases，不能超出前轮完整case清单。`measured_domain_ids` 表示相交域（不是整个域都已测）；可保留前轮不可变域而报告域内部分测量。未测两者均为空，有效测量非空。
- `mechanisms`：hypothesis_id、judgement:supported/weakened/undetermined、basis:static/performance/mixed、evidence_refs、finding。机制判断与 Action readiness 分开；无有效性能证据不能改标为性能支持/削弱。
- `attribution`={kind:single_change/compound/unmeasured,limits}；未测只允许 unmeasured；复合变化的归因限制需独立审阅。
- `next_step`={kind:repair/continue/retune/replan/change_mechanism/collect_evidence/stop,return_to:C1/C2/C3/none,retained,reopened,opportunity_ids,discriminating_prediction_ids,reason}。

R2 不强制换 Action。continue/retune 需要判别预测，允许新预测、独立新增静态依据，或在正确性失败/无效测量后继续此前未测试的预测；不要求改写句子制造新意。repair 无需新增性能预测。replan 返回 C2，change_mechanism 返回 C1。有效/无效/未测及原 prediction_updates 继续由旧逻辑核验，正确性失败和结构未实现不能确认或削弱性能预测。collect_evidence 不能同时选 experiment；repair 需真实结构/正确性缺陷，所选机会必须进入后继复盘。

反馈证据回执除实际源引用外，须含 `attempt_identity={parent_implementation_hash,implementation_hash,workload_hash}`，与上述 attempt 一致。结构、正确性、机制不能串用同task另一候选结果。`source_refs`（可选）保存原日志/原结果引用并校验hash；不修改原始回执。结构可直接引用 attempt 中候选源码或patch；正确性不能只引用源码证明。无实际候选时 implementation_hash=null，新增静态分析也需此scope。

`discriminating_prediction_ids` 只在当前所选机会内解析，不受替代机会的同名 prediction 影响。旧 prediction 未测试时可保留原文；正确性修复、恢复无效测量或新增静态依据可以合法继续。没有新信息则不能把 continue 改名 collect_evidence 后实施。

### 有效计时与前轮 workload 内容绑定

v2 的 `measurement=valid` 还要求前轮 `path_overview.workload_ref` 指向明确的逐 case 完整 payload 清单：

```json
{"cases":[{"case_id":1,"workload":{"shape":[2],"oracle_limits":{"atol":0,"rtol":0,"equal_nan":false}}}]}
```

清单唯一覆盖前轮全部 case；每项 `workload` 是该 case 交给计时收集器的完整对象，实际任务的 dtype、布局、属性和原精度限制也须完整保留。校验沿已验证的 candidate capture 引用读取 workload 快照，将其与前轮同 case payload 作规范 JSON 全等比较。文件引用仍核对字节 hash；不把规范 JSON 内容 hash 当作文件 hash，不通过忽略字段或仅比较 shape 接受差异。A/B 与正确性间的 workload 身份继续由原统一计时链验证。

完整清单及 payload 必须在原 workload 和 R1 决策冻结时保存。`measured_case_ids` 可仅包含其中部分 case，未测 case 和相交域不冒充已测范围。只有 case ID 或无法无歧义转换的原始矩阵仍可用于未测分析，但缺少上述映射时，已有 timing 不能标为本决策的 valid 反馈，也不能支持或削弱它的性能预测。该拒绝不改变原计时结果自身的有效性，不允许回填 R1，也不要求机械重跑硬件；保留原结果及缺失的归属关系，若另行形成后继任务则先显式冻结完整映射。v1、旧 schema 和计时结果含义不变。

## 装配帮助

维护工具 `tools/assemble_action_decision_v2.py` 仅装配 Agent 自主形成的 path_overview、analyses、comparison_basis、reassessment；不会补默认 Problem/Action、工作量或预期答案。产物仍须 runtime 校验。`runtime/tests/test_action_decision_v2.py::v2_fields` 只是合成单阶段合同夹具，不能用于自主回放生成结论。

## 可核查范围与限制

校验能识别遗漏/重叠、跨 scope、错误引用、角色错配、残余消失、未注册实施、假实测、错误 R2 状态和历史格式绕过。程序无法证明自然语言 predicate 穷尽源码、估算真实或所选方向最优；`semantic_review_required=true` 保留。独立审阅必须对照源码和知识正文，不以结构检查通过作为行为正确证明。
