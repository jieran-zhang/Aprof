# v0004：机制、证据与条件化干预

本页保留 v0004 诊断和交接的语义；v0005 起的条件分类、知识采用、机会比较及 R2 反馈以[新选择规则](action-selection.md)为准。机器格式由包内新 schema 校验。模板知识、任务推理、案例与提案各有身份。旧图 v0003 只是本次迁移种子，历史边及先验不证明机制。

## 知识如何使用

Symptom 定义观察：对象、位置、字段或源码条件、值和单位、比较基准、复合条件和未知条件。ID 为兼容身份，名称里的“策略不匹配”“开销主导”不是机制判断。复合规则的成员全部成立才为 true，任一明确不成立才为 false，其余为 unknown。源码、profile、workload、derived 和 proxy 保留来源差异；未实现 extractor 不因有人工审读而改成 implemented。

Problem 是核心知识单元。正文说明成本形成链、涉及对象和阶段、可解释观测、额外预测、支持与反证、替代机制与区分检查、可考虑的变换及代价、平台和 workload 边界。每条声明单列来源陈述、源码事实、机制推导或案例支持；继承的旧标签单列 legacy_seed。审阅过源码不等于在当前任务确认瓶颈。

Action 模板定义变换意图、原有前提和不变量；实例绑定当前对象、父实现、workload、证据和参数。不得用相近 Action 的前提代替本 Action，原 expected false 也必须满足。一个机制可以没有可行 Action。

关系的对象绑定、联合条件、例外和依据由边记录维护，正文解释原因。支持／反驳不是充分因果条件；多个联合要求不能各自单独推出 Problem。替代、共存和可能因果关系可共用关系 contract。来源可信程度、机制判别力和出现频率分别记录，没有数据时为 unknown。旧权重只作历史排序先验，不是概率、收益或因果置信度。

## 从检索到任务推理

数值观测先做[自洽与分层检查](observation-checks.md)。检索后按 Agent 当前阅读理由调用 `diagnosis expand`，交付完整 Problem 正文、分析、来源及身份，并用 `diagnosis verify-expansion` 精确回放；输入字段见[C1 contract](../contracts/diagnosis.md#problem-正文按需展开)。展开记录通过现有 C1 artifacts 传递，不修改旧推理或交接 schema。

1. 用 `diagnosis retrieve` 取得匹配观察的邻接线索和完整 Problem 轻量目录；当前28项，今后随知识版本增长，不固定top-k。
2. 比较适用域、机制差异和未解释观测，按需读必要正文。没有边不表示没有候选；不加载全部正文，不按分数自动选 Action。
3. 每张候选卡说明支持、反证、unknown、替代解释、判别检查、当前状态及理由。反证会改变判断，但排除必须有明确证据。数据缺失、低排序、其他机制更像都不足以排除。
4. 现有机制不足时建立任务内临时 Problem，并说明和现有模板的差异。可以复用已注册 Action，不允许临时新 Action 直接进入P/O，也不伪造模板边。

原始事实身份至少包含实现、workload、目标／阶段、artifact hash、locator／指标和范围。派生事实保存 derived_from。换 evidence_id、套多个 Symptom 或同时引用原值与其比值，不能增加独立支持。不同指标共享一个文件也不能简单合并。运行时核对可计算结构和显式依赖，Agent负责开放机制判断，不声称从任意C++证明等价或因果。

## C1 → C2 → C3

C1交完整Action模板快照、当前实例、推理与证据身份和路由请求。中央 action-routing 配置只缩小候选范围，不提前锁定P/O完整组合。提示独立存储，不能覆盖facts或platform/family/dtype/features；这些属性来自同范围已校验证据及已确认计划。

C2调用规划内部router，选实际P或复用完整有效计划。输出任务所有权、归约／同步、数据通路、workspace和资源预算、参数单位、允许的实现自由度、替代方案和进入条件。O在这里仍是请求与边界，具体recipe由C3决定。

C3调用优化内部router，在确认计划内选实际recipe及有序配套步骤。顺序描述实现依赖，不强制kernel排程串行。记录实际参数、兼容理由、源实现和计划身份，最终关联Action实例→P选择→O选择。匹配条目不等于已执行；正文、约束和实际变化都要检查。

- P_KEEP：复用完整有效的architecture/parallel/dispatch计划及其范围和自由度。缺计划不是KEEP。
- O_KEEP：不追加局部优化。P_CHANGE时C3仍实现新计划，源码可以改变。
- 双KEEP：整体NOOP，不伪造已执行缓解动作。
- fallback、空交集、unsupported和needs_evidence分别保留，不转换成KEEP。

容量、所有权等unknown允许C2做条件化分析，不能授权C3。C3实施前重新检查注册Action全部原fact/state、实例范围及所选方法的条件。某个动作不合法只阻塞该动作，不自动反证Problem。交接按instance_id、模板hash、目标范围、参数及计划绑定校验，同一Action的两个tensor实例不能串用证据。

超出C2明确许可自由度的算法、task→owner、归并结构／数值次序、同步拓扑、workspace所有权、融合边界、数据通路或dispatch域变化，返回C2。普通局部参数变化可复用有效计划，不机械重启算法搜索。

## 新证据和知识晋升

新证据建立新Context／证据快照、新reasoning和后继C1/C2，引用旧实例，不回填已冻结记录。只补容量时可以复用机制判断并更新readiness，不强制重调一遍诊断Agent。

临时候选→任务分析／验证→知识提案→去重与语义审查→contract及来源校验→独立复核→新知识版本。提案说明旧模板不足、差异、机制链、预测、反证、判别、关系和适用范围。成功优化只触发提案；检查变更混杂、预测符合程度及归因限制后才能纳入。没有可行Action也允许提Problem。

本轮案例是paper/source_review，不是实测案例，不产生case_support、性能接纳或训练奖励。实际案例将来引用真实变更、验证与计时记录；不能把CPU合成测试数据写成设备观测。

## 扩展与版本

新family/branch不自动生成Action；同意图的新方法通过路由范围或选择记录扩展。新叶正常进入检索，采用前仍审查当前Action、对象与计划的兼容。独立意图或不同硬前提进入提案，不放宽旧Action。移动条目保留稳定ID，分类／token变化显式迁移并输出覆盖差异；历史交接继续绑定原版本和hash。

本页所述历史1.3.0草稿身份：诊断v0004、P v0002、O v0004、runtime0.5.0。O v0003补齐输入片保留，v0004增加同目标的L2缓存兼容门禁；历史P/O及其路由配置保留。旧schema和诊断v0003回放保持原义。新格式不接旧policy／episode训练。来源仅旧图及五个固定仓库修订，必要原文和许可在包内；知识正文不能要求访问上游或临时目录。

当C2确认的新方案需要尚未在权威Context声明的技术域features时，生成有计划依据的新Context及后继reasoning/C1/C2，可以复用未变判断和计划内容，不强制重新调用完整诊断。O不从hint或任意计划文本偷偷补features，空路由保留缺项。

晋升与案例复核文件须结构化绑定proposal/case内容hash、原知识hash、目标版本及审阅结论，不能仅自报independent或引用一个任意JSON。目标知识版本必须前进。案例引用原知识与路由bundle快照及真实C1/C2/C3，重放原始计时和正确性来源；文件hash不是机制因果或审阅者身份真实性证明。

原始 profiling 事实必须显式声明 `time_range`：`interval` 给出有限数值 start/end、unit 与 origin（时间零点/采集轮次），或 `full_artifact` 明确以整份原始采集的 all_recorded_samples 聚合。源码、workload 的时间不适用；profile 缺时间口径时须保留 unknown。校验不修改已冻结记录；补充时间口径需新推理快照。不同时间窗口不自动成为独立证据，仍追溯原始 artifact hash 与 locator。
