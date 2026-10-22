# graph-base/1.3.0 / runtime 0.8.2（未封版）

本版完整包位于 `skill-libs/graph-base/1.3.0`，实验必须显式指定此路径及其任务内冻结副本。现有默认版本、1.2.0、旧 schema 和冻结快照保留；本次维护不代表封版、发布或硬件性能验收。

- 诊断知识 v0007：机制检索、证据比较、Problem 正文按需展开与精确回放；新任务通过 `aprof.action-decision/v3` 选择完整方案，以 `aprof.handoff/v4` 请求各成员 P/O 及共同计划。历史交接保持原义。
- 规划知识 v0004、优化知识 v0007，路由配置 v0006、条件策略 v0002；L2 组合门禁、输入驻留的作用域与生命周期分别判断。KEEP 必须有有效计划，实施安全未知不授权 C3；收益未知可进入有依据的假设试验。
- runtime 0.8.0 在机会比较之上支持单/多 Action 完整方案、共享计划、联合资源与依赖检查；协调者维护三部分跨轮摘要，后继重新比较残余工作。轮数、达标停止与重试范围由外部指定。`knowledge.py` 和历史快照、旧 schema 保留原字节。
- 中文知识与必要来源、修订、许可随完整包保存，使用不依赖上游仓库或下载目录。
- C0后、diagnosis前有正式code-understanding阶段，使用[910C代码理解skill](skill-libs/graph-base/1.3.0/skills/ascendc-code-understanding/SKILL.md)解释整体算法、当前实现策略和硬件数据流；只有一份中文阶段说明，由P/O及后继轮次复用。开发评测工具不进入日常workflow。

上轮 runtime 0.5.0 的 CPU 回归为 261 通过、1 跳过；7 个合成原始输入由 3 个独立 Agent 自主回放，3 个交接在合成合同内 ready、4 个 conditional。完整包独立目录检查通过，未生成实施 C3，未证明硬件收益。范围及遗留缺口见[逐例报告](skill-libs/graph-base/1.3.0/workflows/references/autonomous-diagnosis-1.3.0.md)与[检查记录](skill-libs/graph-base/1.3.0/workflows/references/autonomous-diagnosis-validation.json)。

前一轮 runtime 0.6.0 维护拆清条件、性能假设和 Action 选择，加入补证据与 R2 反馈；不改变计时、预算或正确性规则。15 个算子原始源码及各 20 case 由三个独立 Agent 完成两轮自主分析，完整条件方案、实际知识采用、独立复核与检查结果见[源码回归报告](skill-libs/graph-base/1.3.0/workflows/references/source-regression-15/README.md)。没有预设 Problem/Action，不用强制换动作验收。选择流程见 [Action 选择与反馈](skill-libs/graph-base/1.3.0/workflows/references/action-selection.md)。结构检查使用：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B skill-libs/graph-base/1.3.0/tools/release.py --allow-unsealed
```

后续硬件批次使用独立任务副本，保留完整原始 20 cases、统一 5/20 与逐轮清 L2、原 oracle 和有效性门禁。批量 prompt 的编写或校验不启动硬件；本轮已完成的两轮分析没有运行硬件，也不包含 memory recorder、知识提案晋升、边权或模型训练。优化结果与技能库维护分开，不在实验期间修改本包。

本轮 0.7.0 的具体变化、独立复核与检查记录见[机会比较与复盘维护](skill-libs/graph-base/1.3.0/workflows/references/selection-reassessment-1.3.0/README.md)。新增来源严格限于五个既定修订；不把 Tiling Key 或动作多样性作为优化目标。

910C代码理解正式阶段的来源、两份贯通示例与独立审阅见[维护记录](skill-libs/graph-base/1.3.0/workflows/references/code-understanding-1.3.0/README.md)。首轮工具/SDK开放条件A/B均357/360；最新[无工具24次对照](skill-libs/graph-base/1.3.0/workflows/references/code-understanding-1.3.0/no-tools/README.md)为A351/360、B354.5/360，3对提高、9对持平。平均输入约1.19万→2.73万token，收益局部、基线接近满分；两种条件分别保留，不把跨轮分差解释为工具收益，日常workflow不增加工具门槛。

本轮完整方案、多 Action 交接、跨轮摘要、无工具自主回放和独立检查见[0.8.0维护报告](skill-libs/graph-base/1.3.0/workflows/references/optimization-schemes-1.3.0/REPORT.md)。不要求严格单因素或每轮更换Action，不把新增Tiling Key作为目标；不新增日常必跑工具，不收集memory，不开展硬件实验。

本轮 runtime 0.8.1 修复数据相关触发、准备工作收支、正确性修复后的重比和完整方案交接：新增派生结果复用、buffer/事件管理简化两项通用Action，测前冻结完整workload并保留历史映射限制。原因、正式交接纸面例、独立复核和无硬件A/B见[执行事实与完整代价维护报告](skill-libs/graph-base/1.3.0/workflows/references/execution-cost-1.3.0/REPORT.md)。历史实验准入状态不追认。

本轮开发验收为155项回归通过、30组事件CPU模型、三份完整P/O交接纸面例及独立目录检查。24次无工具A/B事实分均96/96，未证明准确率提升；新版的派生复用交接和静态管理备选覆盖有所改善，平均输入增加约3.42%。原始答案、失败preflight成本及独立评分复核随包保存，不据此宣称性能或HAP提升。

当前 runtime 0.8.2 加入[中位数探索稳定性v2](skill-libs/graph-base/1.3.0/skills/ascendc-aprof-profiling/references/median-stability-v2.md)：一次对称最多4/20、处理后CV≤10%，完整保留原始统计；双方原始中位数漂移、剔除敏感性和工程收益分开。采集5/20、原oracle、HAP、Action—P/O准入和工程门槛保持。既有30轮的[离线比较](skill-libs/graph-base/1.3.0/workflows/references/median-timing-1.3.0/REPORT.md)不是新协议独立验证，不追认历史候选。本轮未启动硬件。
