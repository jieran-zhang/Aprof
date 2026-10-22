# AProf 证据契约与历史接口

新任务必须按 [soft_targets_local_v1](execution-policy.md) 执行：耗时仅为软目标，baseline 默认 assumed，新候选完整验证一次，按全输出内容复用；所有运行产物留在 /dev/shm。

Agent 阶段交接见 [公共契约](../contracts/common.md) 和 [主流程](../aprof-performance-workflow.md)。本页只说明机器接口与历史兼容，不代替 runtime 实现。机器字段名、命令和协议 ID 保持英文；说明使用中文。schema 校验只检查结构，原始来源回放才核验证据。

## 当前统一计时接口

1.2.0 新测量统一使用 `single_role_l2_clean_task_v1`。逐 case 采集记录不带永久 baseline/candidate 角色；comparison 指定 A/B 和各自源码身份，因此合格 B 可作为下一轮父版本证据。

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
| knowledge-handoff / knowledge-route | 当前 v0003 与知识树的证据、排序、内容快照和选择/执行 |
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

旧命令 `candidate gate`、`exploration gate/verify`、`episode finalize/verify` 保留各自契约，用于兼容场景或历史回放；旧 measured admission 不能作为 1.2.0 新测量的入口。重现历史请求时使用其冻结包、协议和证据。新 20 轮不能冒充旧 30 对。

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
tools/aprofctl knowledge build --root . --owner diagnosis
tools/aprofctl knowledge validate --root . --owner parallel-planning
tools/aprofctl knowledge route --root . --owner optimization --context evidence.json
tools/aprofctl contract validate --root . --kind knowledge-handoff --input C3.json
```

三个 owner 分别为 diagnosis、parallel-planning、optimization。route 支持 --override，严格绑定知识版本/hash，旧 policy 不跨版本套用。新 JSON 格式与边界见 [图规范](../../skills/ascendc-aprof-diagnosis/graph/FORMAT.md) 和两棵树本地 FORMAT。构建使用安全 YAML，依赖由 runtime/pyproject.toml 显式声明。

旧快照位置为 skills/ascendc-aprof-diagnosis/graph/history/versions/v0001 或 v0002；load_snapshot 与旧 fixed_supports_refutes_tri_state_v1 路由保持语义。v0003 默认确定性整数专家排序，没有 softmax 概率。
