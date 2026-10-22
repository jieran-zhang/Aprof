# 阶段交接公共契约

新任务必须按 [soft_targets_local_v1](../references/execution-policy.md) 执行：耗时仅为软目标，baseline 默认 assumed，新候选完整验证一次，按全输出内容复用；所有运行产物留在 /dev/shm。

主流程见 [角色与 contract 连线](../aprof-performance-workflow.md)。本目录规定 Agent 间交换什么；专业方法由 skills 提供，JSON 的格式和原始来源校验仍由 [runtime 契约](../references/runtime-contracts.md)负责。

## 一次调用，一份阶段文档

协调者创建阶段文档的请求部分，指定接收角色、输入引用、目标、执行范围、原任务连续起点/软目标和完成条件；接收角色填写结果后返回同一路径。跨角色需求交回协调者，角色可以直接使用本职责所需的 skill 和工具。

交接单位是阶段实例，不是固定数量的 Agent。一个 Agent 可承担多个角色；委派时也使用相同契约。C0 preparation 后、C1 diagnosis 前先完成或复用 [code-understanding](code-understanding.md)；一次有效理解、已完成诊断或有效计划可供多个候选及后续轮次引用，不为补齐目录重复执行。

阶段文档存于任务私有工作区，例如 `scratch/stages/c001.candidate.01.md`。源码、JSON、日志和采集放在任务产物目录；不要写回技能包。调用时显式传递同一个任务根目录，以下外层引用均相对于该根目录。被引用 JSON 内部仍遵守其原有路径基准，不改写为本契约的基准。

## 固定头部

所有阶段文档使用 YAML 头部加中文 Markdown 正文。下面是待填写模板，尖括号必须替换为实际内容：

```yaml
---
contract_version: 1
task_id: <任务ID>
stage_id: <本任务内唯一阶段实例ID>
candidate_id: null
stage: preparation
role: coordinator
status: pending
context_ref: null
inputs: {}
outputs: {}
---
```

| 字段 | 约束 |
| --- | --- |
| `contract_version` | 当前为整数 1；这是阶段文档版本，不替代既有 JSON schema_version |
| `task_id`、`stage_id` | 非空，stage_id 对每次调用/重试唯一；重试不覆盖旧实例 |
| `candidate_id` | 候选专属阶段填实际候选 ID；原始基线或公共准备填 null |
| `stage` | `preparation`、`code-understanding`、`diagnosis`、`planning`、`candidate`、`profiling`、`decision` |
| `role` | 对应 `coordinator`、`code-understanding`、`diagnosis`、`parallel-planning`、`optimization`、`profiling` |
| `status` | `pending`、`completed`、`needs_input`、`failed` |
| `context_ref` | 本次 Context JSON 的文件引用；仅初始 preparation 请求允许 null，交付准备结果前补齐 |
| `inputs`、`outputs` | 具名引用映射；每个值只有 `path`、`sha256`，多个产物用有意义的不同名称或引用已有索引文件 |

文件引用格式为 `{path: scratch/artifacts/context-01.json, sha256: 'sha256:<64位小写十六进制>'}`。相对路径必须位于任务根内，接收者核对实际文件摘要。这里 sha256 是文件字节摘要；JSON 内的 `content_hash`、source 清单 hash 等继续保持原定义，不能互换。不要把这个 YAML 外壳塞进严格的 Context 或 timing JSON。

Context 按现有 schema 表达 workload、设备、预算和 evidence。补充证据时创建新 Context 快照并显式引用，不覆盖被引用版本；新快照不能重置原任务连续起点/软目标、授权范围或预声明 case 集。源码、二进制、输入及工具身份以引用的机器产物为准，不在多份文档手抄一套 hash。

## 固定正文

每份阶段文档都包含以下四部分；各阶段文件规定其中的具体字段。

```markdown
## 请求
- 目标与本次工作范围：
- 上游输入及拟复用内容：
- 原任务剩余预算与执行限制：
- 必须交付的产物及完成条件：

## 结果
- 实际完成的工作与主要结论：
- 输出引用及校验结果：
- 实际成本或成本回执引用：

## 缺项与失败
- 缺失证据、失败命令/退出码、未完成范围；没有时明确写“无”：

## 交接建议
- 建议下一阶段/停止原因、接收角色和需要传入的引用：
```

`outputs` 引用的 JSON 是可计算数据的唯一来源；正文解释决策及限制。code-understanding 的唯一新增产物就是本阶段中文 Markdown，`outputs` 可为空，不另建 JSON 或辅助报告；已有适用报告可按其 contract 直接复用，不为补齐外壳再造一份。C0—C5 编号和外层 contract_version=1 保持不变。runtime 0.8.1 的完整方案使用 aprof.handoff/v4 与 action-decision/v3；历史 v2/v3 及原 schema 保持原义，交接链不混装版本。机制补采的用途等解释按阶段模板写在正文，不能伪装成机器通过记录。现有 `diagnosis_hypotheses.json`、`candidate_plan.json`、`profiling_plan/results.json` 若已由工具产生，可作为补充引用，不要求重复生成同义文件。

## 状态与接收规则

- `pending`：协调者已发起请求，尚无完成结论，不能作为后续阶段完成证据。
- `completed`：请求范围已完成且必需产物齐全。是否允许进入下一阶段，还要满足该阶段的前置条件；代表集采集 completed 不等于全量覆盖。
- `needs_input`：缺输入、合法路由、工具、native adapter 或授权，返回具体缺项与建议角色。
- `failed`：实际检查、构建、执行或来源核验失败，保留原命令、退出和部分产物。

性能 `accepted/rejected/inconclusive` 只来自 `timing finalize` 的结果；性能被拒绝的 decision 阶段仍可 completed。诊断给出未证实假设、仅诊断/仅规划任务完成，也不等于候选已可计时。

协调者接收时核对：角色/阶段、任务与候选身份、上下文版本、输入/输出存在且摘要匹配、必需字段/产物、完成条件、剩余预算。来源、数值、case 覆盖和计划约束交现有 runtime 校验；本契约是 Agent 交接规范，目前没有自动执行整条流程的调度器或通用 Markdown 验收命令。不要把格式检查当作语义证明。

结果写完后冻结整个文档，下游引用其最终字节摘要。失败、缺项或补采都生成新实例，引用原请求和已获得证据，不把失败改写为成功。只有 pending 请求可在执行者填写结果时完成更新；若目标/范围改变，另开实例。

## 恢复、复用与交付

下游只需当前请求、Context、相关上游阶段文档和其产物即可继续，不依赖聊天历史。最终决定由协调者记录，角色给出的下一步仅是建议。

复用已有理解/计划/正确性/测量时引用原记录，写明身份、范围和时限匹配依据；声明复用不代替实际回放。理解报告供诊断、P/O 与 R2 共同使用，源码或相关条件变化只更新受影响部分并保存后继，纯新增 profiling 不重做理解。完整性、预算、清理和交接见 [生命周期](../references/workflow-details.md)。交付前确认报告依赖的代码与证据仍可访问；需要继续回放的 scratch 或原始证据不能先删除。需要永久归档时按既有 collector 契约交接。

## 新知识记录与历史兼容

外层文档保持 contract_version=1。历史v0003的C1/C2/C3继续引用[旧knowledge-handoff schema](../../schemas/knowledge-handoff.schema.json)，v0004 起采用[机制与交接规则](../references/diagnosis-v4.md)及独立 v3 schema，v0005 再绑定选择 sidecar。runtime 0.8.1 在后继知识快照上使用[完整方案](../references/optimization-schemes.md)的 v4 交接与 v3 决策，显式按协议分派，不用图版本替代交接版本。parent_hash 为规范 JSON 内容 hash，和 outputs 中的文件字节摘要不同。旧 candidate_draft/episode 保持原字段与评分语义；不得将 v0003 路由包装成旧 episode。知识内容、路由、schema 或训练覆盖变化均记录精确版本/hash。

证据输入 aprof.evidence/v1 必须带 source_context_ref{path,sha256}，关联本次 C0/Context 文件。route.context_snapshot 保留完整 facts、attributes 和原 Context 引用，context_hash 对应该快照的规范 JSON hash；下游据此恢复路由条件，不依赖聊天记录。C1/C2 可用 candidate_id=null 表示任务级共享；C3 必须绑定真实候选 ID。
