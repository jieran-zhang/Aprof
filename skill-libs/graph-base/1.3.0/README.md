# APROF graph-base 1.3.0 技能库草稿

新任务必须按 [soft_targets_local_v1](workflows/references/execution-policy.md) 执行：耗时仅为软目标，baseline 默认 assumed，新候选完整验证一次，按全输出内容复用；所有运行产物留在 /dev/shm。

本版以六个角色和三个版本化知识区组织；完整流程、角色与 contracts 统一由 [workflow](workflows/aprof-performance-workflow.md) 管理。新说明为中文，字段、ID、API 保留英文。当前未发布，不切换默认版本。

| 目录/入口 | 作用与阶段 |
| --- | --- |
| [skills/ascendc-aprof-coordinator](skills/ascendc-aprof-coordinator/SKILL.md) | C0 准备、角色分派、C5 收尾与交付 |
| [ascendc-code-understanding](skills/ascendc-code-understanding/SKILL.md) | C0 与 C1 之间；理解整体算法、实际实现策略及 910C 硬件行为，交付可复用的中文阶段说明 |
| [diagnosis/graph](skills/ascendc-aprof-diagnosis/graph/README.md) | C1；独立 symptom/problem/action/edge Markdown，v0007机制模板、任务推理与条件关系 |
| [parallel-planning/knowledge](skills/ascendc-aprof-parallel-planning/knowledge/ROUTER.md) | C2；算子族/模式策略与模板、容量和成本比较 |
| [optimization/knowledge](skills/ascendc-aprof-optimization/knowledge/ROUTER.md) | C3；执行方法、代码片段、约束、验证和失败特征 |
| [profiling](skills/ascendc-aprof-profiling/SKILL.md) | C4；统一计时、按需机制采集与原始解析 |
| [skills/registry.json](skills/registry.json) | 6 个角色入口、12 个辅助能力及其触发阶段；插件/安装清单 |
| [workflows](workflows/aprof-performance-workflow.md) | agents、contracts、流程和运行生命周期；migration 隔离冻结来源与逐项去向 |
| [schemas](schemas/README.md)、runtime、tools | 数据格式、构建/路由/回放和完整包安装验证；不承担另一份知识 router |

旧顶层 skillgraph/wiki/experience 已归并。旧图 v0001/v0002 的字节与回放语义保留在 diagnosis/graph/history。迁移清单与处置理由见 [迁移报告](workflows/migration/README.md)，完整节点/边初值见 [图初始化报告](skills/ascendc-aprof-diagnosis/graph/INITIALIZATION.md)。

1.2.0 继承的结构、路由、五类交接、历史回放与独立安装检查记录见 [治理验收记录](workflows/migration/VALIDATION.md)。

准备后先按 [代码理解阶段](workflows/contracts/code-understanding.md) 还原算法、当前策略和硬件数据流，再交 diagnosis；理解结果由 P/O 与 R2 复用，相关源码或条件变化时局部更新。该阶段只有中文 Markdown，不增加 JSON、runtime 门禁或必跑工具。

C1 交 action 内容快照；C2 交模板快照、方案比较、参数和自由度；C3 交执行条目版本、实际调整和符合性。C4/C5 关联“推荐/选择/执行”与统一计时，不自动产生训练奖励。两棵知识树的模板是方案骨架、公式、伪代码和 Ascend C 关键片段；不是五套完整工程。

## 1.3.0 中文知识扩充

当前 C2 知识为 v0004，C3 知识为 v0007；历史快照和交接保留。诊断为 v0007，runtime 为 0.8.2。新任务按[Action 选择与反馈](workflows/references/action-selection.md)区分实施条件与性能假设，有来源且适用的知识可用于未测收益的假设试验；[v0004 机制与交接基础规则](workflows/references/diagnosis-v4.md)继续沿用，旧版 Action 前提仅按冻结身份回放。使用方式与分类见[知识扩充说明](workflows/references/knowledge-expansion-1.3.0.md)，输入复用增量见[补齐与回归说明](workflows/references/input-reuse-1.3.0.md)，来源版本见[固定来源清单](workflows/references/knowledge-sources-1.3.0.json)。条目包含中文原理、选择条件、公式及必要代码；sources 仅作审计，不是使用说明的替代品。

此前缓存组合过滤、Problem 按需展开、观测自洽校验和自主阅读结果见[修复与自主回放](workflows/references/autonomous-diagnosis-1.3.0.md)。

本轮 Action 条件迁移、15 算子两轮自主源码分析、实际知识采用及检查结果见[源码回归报告](workflows/references/source-regression-15/README.md)。没有预设 Problem/Action，也没有动作多样性配额。

本版未经新硬件收益验证、未封版，也未切换任何默认入口。

v0004 的逐步产物、迁移边界、路由审查及遗留缺口见[实施说明](workflows/references/diagnosis-v0004-implementation.md)；CPU、来源、保护和独立目录结果见[检查报告](workflows/references/knowledge-validation-1.3.0.json)。

## 统一计时

反馈与收尾均用 [single_role_l2_clean_task_v1](skills/ascendc-aprof-profiling/references/unified-timing.md)：每 case/实现一个新进程，5 次预热、20 次逐轮清 L2、按完整调用全部目标 Task 求和后取中位数。有效 A 复用，只采 B；全量收尾补缺项，不因“正式”重复采集。合格 B 可作下轮 A。

`timing finalize` 使用点估计工程判定，不把新数据冒充旧配对/95% 下界。现有实验和约 66 秒估算的适用范围仍有限，10 分钟是待验证目标。新权重未校准，模板只完成来源审读。

runtime 0.2.5 增加 [original_python_v1](skills/ascendc-aprof-profiling/references/original-oracle.md)，live 与离线回放执行冻结原程序，保留 BF16、自定义误差和特殊值规则。先对完整配置执行能力预检，再验证实际算子链路；归档完成、能力支持和性能验收是独立状态。旧轮次冻结副本不被本次开发包修复覆盖。

runtime 0.2.6 增加预声明的 `bounded_outlier_v1`：20 次完整调用中最多剔除 2 个对称异常，保留样本仍须通过 5% CV；原始值、异常索引与原始 CV 一并输出。未启用的新字段不会改变旧记录判定。具体规则与 A/B 连续采集安排见[统一计时](skills/ascendc-aprof-profiling/references/unified-timing.md)。

## 独立安装和维护

保留完整包，安装器给宿主创建符号链接。来源原文和许可证随包携带，运行不依赖上游五个源码仓库、原工作树或临时下载目录。不要只拷贝单个 skill。

```bash
APROF_PACKAGE=/absolute/retained/graph-base/1.3.0
APROF_HOST_SKILLS=/absolute/host/skills
python3 "$APROF_PACKAGE/tools/install.py" --allow-unsealed --runtime --skills-dir "$APROF_HOST_SKILLS"
python3 "$APROF_PACKAGE/tools/release.py" --allow-unsealed
"$APROF_PACKAGE/tools/aprofctl" diagnosis verify --root "$APROF_PACKAGE"
# 以下仅检查历史 v0003 快照的兼容回放。
"$APROF_PACKAGE/tools/aprofctl" graph validate --graph "$APROF_PACKAGE/skills/ascendc-aprof-diagnosis/graph/versions/v0003"
```

诊断源码用 `diagnosis build --root <包> --parent-snapshot <显式较低父版本目录>` 构建，用 `diagnosis verify` 校验；已冻结快照不覆盖。P/O继续用 `knowledge build/validate --root <包> --owner parallel-planning|optimization`。未封版检查覆盖来源 hash、图和知识树、插件/角色入口，不授予发布或性能资格。完整机器接口见 [runtime 契约](workflows/references/runtime-contracts.md)。

任务数据留在任务私有 scratch/final，预算与清理见 [生命周期](workflows/references/workflow-details.md)。交付需要的源码和证据保持可访问；旧发布包和默认版本不修改。

本次机会比较与 R2 复盘维护见 [实施与知识变化](workflows/references/selection-reassessment-1.3.0/README.md)。D6 使用 decision v2；D5/v1 与旧知识正文按冻结身份继续回放。

910C 代码理解阶段的来源、独立复核与开发 A/B 评测见 [维护记录](workflows/references/code-understanding-1.3.0/README.md)。质量检查只用于开发验收，不成为每次任务的必跑步骤。

当前完整优化方案采用 `aprof.action-decision/v3` 和 `aprof.handoff/v4`，可组合必要的多个 Action 并共享计划。跨轮维护任务内 `optimization-history.md`；轮数、达标停止条件与重试范围由用户或外层任务提供。详见[完整方案与交接](workflows/references/optimization-schemes.md)、[跨轮摘要](workflows/references/optimization-history.md)及[本次验收](workflows/references/optimization-schemes-1.3.0/REPORT.md)。历史交接继续按原版本回放；当前未封版，不切换默认版本。

## 执行事实、完整代价与正式交接修复

本轮修复的数据相关路径、准备工作收支、修复后重比、通用 Action 与无硬件验收见[开发交付报告](workflows/references/execution-cost-1.3.0/REPORT.md)。新任务仍用 action-decision/v3 和 handoff/v4，历史快照及准入结论不追认。

当前探索计时使用[中位数稳定性v2](skills/ascendc-aprof-profiling/references/median-stability-v2.md)：4/20、CV≤10%是试用轮内标准，跨窗口漂移、剔除敏感性及收益分别报告。来源数据的[离线比较及限制](workflows/references/median-timing-1.3.0/REPORT.md)不追认历史候选；HAP、完整交接和工程收益门槛保持。
