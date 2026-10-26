# 1.3.0 v0004 实施与迁移说明

本文记录诊断迁移阶段及当时的 P/O v0002 身份。后续输入复用增量已将 O 更新为 v0003，参见[增量说明](input-reuse-1.3.0.md)和[检查记录](input-reuse-validation.json)；本页的“本轮”与受保护范围均指诊断迁移阶段。

本轮将诊断改为机制检索、证据比较和条件化干预，runtime 升至 0.4.0。1.3.0 保持未封版，不切换默认版本；P/O v0002 的知识正文与 index 保持原字节。结构和来源检查不证明真实瓶颈、硬件收益或因果正确性。

## 五步产物

| 步骤 | 包内产物 | 当前结果 |
| --- | --- | --- |
| 冻结与 contract | [基线保护清单](v0004-baseline-preservation.json)、[机制与交接](diagnosis-v4.md)、[schemas](../../schemas/README.md) | 冻结 v0003 种子与历史参数，新增严格的 v1 诊断系列和 v3 交接；旧 schema 不改义 |
| 逐项迁移 | [195 项迁移台账](../../skills/ascendc-aprof-diagnosis/migration-ledger.json)、[来源审阅](../../skills/ascendc-aprof-diagnosis/source-review.json)、[Problem 目录](../../skills/ascendc-aprof-diagnosis/graph/PROBLEMS.md) | 55 S、28 P、28 A、84 旧边逐项保留身份；另加 5 条 Problem 条件关系 |
| 检索与推理 | [诊断 skill](../../skills/ascendc-aprof-diagnosis/SKILL.md)、diagnosis retrieve、diagnosis-reasoning contract | 始终提供完整 28 项轻目录及观察邻接；不固定 top-k、不计算机制总分、不自动选择 A |
| 两阶段交接 | [中央路由](action-routing.json)、[28 A 路由审阅](action-routing-review-1.3.0.json)、knowledge validate-chain | C2 实际选 P，C3 在确认计划内实际选 O；实例/模板/参数/证据/计划绑定校验；KEEP 与重规划边界明确 |
| 提案与独立验收 | [四个纸面案例](../../skills/ascendc-aprof-diagnosis/examples/README.md)、[两个待审意图](../../skills/ascendc-aprof-diagnosis/proposals/README.md)、[检查报告](knowledge-validation-1.3.0.json) | 案例与晋升凭据严格绑定、来源和 contract 校验、独立复核与离线回放；本轮不晋升新 A |

## 模板迁移

Problem 正文补充机制链、对象和阶段、预测、支持/反证、替代解释及判别、干预前提与代价。Symptom 的名称和 ID 保留，观察定义与解释分开；55 个复合观察以当前观察/口径/必要比较的 all-of 表达。独立复核后，移除了要求“先做优化且见效”才成立的循环观察前提，变更记录见[观察修订清单](../../skills/ascendc-aprof-diagnosis/observation-review-changes.json)。

200 项记录共有 1,726 项声明：195 项旧种子、538 项来源陈述、87 项源码事实和 906 项机制推导。旧种子不自动升级成已验证机制；源码事实不证明 profiling 关联。多处正文引用同一个来源事实也不产生多份独立支持。本版没有 case_support 声明或设备案例。

新编译器显式绑定 v0003 父图的文件 hash 和 schema/generator 身份；当前注册 v0004。旧 knowledge.py 不改动，显式 v0003 回放继续用旧路由语义。旧 diagnosis 源码命令遇到新 REGION 会提示新命令，不能静默改读历史快照；新格式拒绝进入旧 policy/episode 路径。

## 从解释到实际变换

临时 Problem 可以复用注册 A，但须保留假设身份和判别检查；临时新 A 无法交接。模板机制判断与 Action readiness 分开。容量不足可以阻塞动作，不自动反证机制；unknown 可进入 C2 条件分析，但不能授权 C3。

路由请求只给子树范围和条件，不填造事实或覆盖 platform/family/dtype/features。C2/C3 各自调用真实内部 router，检查实际选中项与当前实例/目标/计划的兼容，并保留正文快照。空候选、fallback 和 unsupported 不表示 KEEP。新叶可正常检索，实际采用仍要给出兼容依据。

P_KEEP 引用完整有效计划和自由度；O_KEEP 不增加局部优化，P_CHANGE 时仍要实现新计划；双 KEEP 是 NOOP。超出许可自由度的算法、owner、归并、同步拓扑、workspace 所有权、融合边界、通路或 dispatch 域变化须返回 C2。

12 项旧变体均转为机制/范围审查，不预锁笛卡尔积、不复制成 12 个 A。Cube 配置与输出最终化保留为两个独立意图提案，尚缺最小前提、判别证据及独立审阅，不能借用相近 A 的不适用前提直接实施。

## 证据与历史

原始事实绑定父实现、workload、目标/阶段、artifact SHA256 和 locator；profiling 另有明确时间区间或整份采集聚合口径。缺时间口径保持 unknown。派生事实记录依赖；改名、包装、原值与比值、同来源重切窗口均不自动成为独立支持。

新增证据创建不可变后继推理/交接，可以引用未变结论与计划，不回填旧记录。案例回放绑定原知识与路由 bundle，不按最新配置重解释历史。晋升须有结构化独立 review 和 validation，绑定提案/案例内容 hash、知识身份和目标新版本；成功优化只触发提案，不自动证明机制。CPU synthetic 记录不得作为 case_support。

## 检查范围与遗留缺口

[最终机器报告](knowledge-validation-1.3.0.json)记录 CPU 用例、来源 hash、本地引用、包身份、受保护文件及隔离目录结果；[知识](v0004-reviews/knowledge.json)、[运行时](v0004-reviews/runtime.json)、[实际使用](v0004-reviews/forward-use.json)和[时间口径增量](v0004-reviews/temporal-evidence.json)复核分别说明检查范围。先前 P/O 的审查结果保留在[历史报告](v0004-reviews/pre-diagnosis-validation.json)，其 runtime 0.3.0 和旧诊断保护结论仅属于当时阶段。

[知识缺口台账](../../skills/ascendc-aprof-diagnosis/knowledge-gaps.json)保留目标型号 Vector–MTE 计数器、并发时间线、workspace 库 ABI 与生命周期及阈值迁移限制；8 项相关记录保持 gap。profiling extractor 未实现，指标关联仍待实际任务补证据。继承的 P/O 缺口包括 Scan/Prefix、卷积各方向及窗口/池化。

新 family/branch 不自动生成 A；符合既有意图时扩展路由或实例选择说明。独立意图/不同硬前提走提案，新 Problem 解释旧模板不足并提供预测、反证和判别；允许没有 Action。修改知识后递增版本、明确父版本并重新冻结 bundle，不覆盖已引用快照。
