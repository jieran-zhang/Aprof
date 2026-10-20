# diagnosis：诊断与补证据请求

新任务必须按 [soft_targets_local_v1](../references/execution-policy.md) 执行：耗时仅为软目标，baseline 默认 assumed，新候选完整验证一次，按全输出内容复用；所有运行产物留在 /dev/shm。

生产者：[诊断角色](../agents/diagnosis.md)。消费者：协调者、规划和采集。外层使用 [公共契约](common.md)，`stage=diagnosis`、`role=diagnosis`。

## 输入

引用 preparation、实际分析父版本源码、workload、架构和已有计时/机制证据。补证据后重新诊断时，再引用上一次 diagnosis 与新的 profiling 文档。完整优化会话的基线准备不能被诊断阶段重新生成。

## 必需结果

每个假设使用稳定的本任务内 ID，并填写：

| 字段 | 内容 |
| --- | --- |
| 源码与观测 | 源码位置、实际 workload、原始字段/单位或 trace 引用；区分事实、派生值与推测 |
| 假设 | 可能机制、预期影响、适用 case；按证据比较保留、排除或继续判别，不固定候选数 |
| 支持与反证 | 支持证据、替代解释、什么结果会推翻假设 |
| 未知项 | 缺失视图、未实现 extractor、无法确认的谓词 |
| 补采需求 | 关联假设、指标/单位、case 与实现、所需后端/视图、已有数据是否可复用 |
| 下一步 | 推荐进入规划、沿现有计划优化、先补证据或停止；明确Action实例前提与P/O请求状态 |

历史机器结构保持原义；当前图使用下述版本化知识交接。需要 profile 谓词的动作必须先补足证据；未实现 extractor 保持未知。当前诊断不能凭“预期会更快”认定机制成立。

## 完成与交接

分析请求完成但仍有不影响下一步的未知项，可以 completed，并明确允许的下一步。必须补证据才能选择合法动作时用 needs_input，协调者调用 profiling 的 `mechanism` 请求，再把采集结果交回诊断的新实例。

仅诊断任务可在交付诊断后结束。已有证据支持明确意图时，不因存在“采集角色”就强制采 PMU。

## 正文填写模板

```markdown
## 请求
分析对象/父版本、输入证据、目标与预算：

## 结果
事实与 workload 边界：
主假设 ID、机制、源码位置和适用 case：
支持证据、替代解释与反证条件：
合法路由状态或 NOOP/needs_evidence 原因：
输出引用与实际成本：

## 缺项与失败
未知谓词/缺失视图：
补采请求（假设、指标、单位、case、实现、后端、决策用途）：

## 交接建议
接收角色、下一步和应传入的引用：
```

## 当前交接 C1（v0004 / handoff v3）

按[机制与证据规则](../references/diagnosis-v4.md)交付检索身份、完整轻目录阅读记录、任务推理和Action实例快照。候选卡包含支持、反证、unknown、替代解释、判别检查及理由；不自动生成机制分数或selected_action。

Action实例绑定注册模板版本/hash、假设来源、目标对象、实现/workload范围、原前提及证据、参数和P/O路由请求。临时Problem可引用已有Action；不产生临时新Action或伪造模板关系。未知可交C2条件化分析，不能宣称ready for implementation。

事实和派生依赖可追溯到原始artifact和范围，不重复当作独立支持。新证据创建后继reasoning/C1；容量补点可复用既有机制判断。历史handoff/v2不改义，回放显式引用v0003快照。

## Problem 正文按需展开

`diagnosis retrieve` 的 v1 原义不变：仅交付完整轻目录和观察邻接，不判断机制或选Action。Agent先据原始观测选择要读的Problem，再调用 `diagnosis expand --root <完整包> --context <evidence.json> --request <阅读请求.json> --output <新展开.json>`。`--output` 可省略；指定时只创建新文件，不覆盖已有记录。

阅读请求使用独立 `aprof.diagnosis-problem-expansion-request/v1`：复制本次retrieve的 `task_id`、`context_hash`、`knowledge_hash`、`graph_version`、`source_context_ref`，填写 `retrieval_hash`（retrieve结果对象的规范JSON content_hash，不能对CLI的ok/result外壳求hash）。`selections` 每项包含：

| 字段 | 含义 |
| --- | --- |
| `problem_id` | 轻目录中的注册Problem；临时机制没有可展开模板 |
| `reason` | 结合当前对象／观测说明为何需要读，不能只写待支持的结论 |
| `trigger` | `observation_match`、`alternative_mechanism`、`unexplained_observation`、`scope_check` 或 `followup_check` |
| `related_problem_ids` | 本次比较关联的注册Problem ID；可为空 |
| `unexplained_observations` | 促成本次阅读的未解释观测／任务内引用；可为空 |

输出使用独立 `aprof.diagnosis-problem-expansion/v1`，保留请求及其hash、检索／Context／知识身份；每项包含完整中文正文、机制分析、声明依据、来源、平台范围、对象槽位、审阅限制、模板hash、正文UTF-8 hash及源路径/hash。只展开显式选择的Problem，不按固定数量补齐，也不自动加载全部正文。正文交付hash只证明内容可回放，不能代替Agent的理解或采用记录。

形成机制比较、排除或Action实例前，先读判断依赖的Problem正文，并记录“正文中的哪项机制／边界影响了哪个判断”。若正文提出尚未比较的替代解释，或仍有未解释观测，回到完整目录继续选择；停止时说明已解释范围、剩余unknown及下一步判别检查。容量不合法等Action失败不直接反证Problem，也不能自动支持另一个Problem。临时候选单列其机制、依据、预测和与已读模板的差异，不伪造正文阅读记录。

用 `diagnosis verify-expansion --root <同身份完整包> --context <同一evidence.json> --input <展开.json>` 精确回放，检查身份、正文、来源和阅读理由；只有schema校验不能替代回放。C1通过已有 `artifacts` 文件引用携带展开记录和阅读判断说明，不向旧reasoning／handoff schema加入字段。新Context或新知识身份需要新展开记录，不回填历史文件。
