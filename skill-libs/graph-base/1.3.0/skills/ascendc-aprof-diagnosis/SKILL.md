---
name: ascendc-aprof-diagnosis
description: 从源码、workload和观测检索Ascend C机制知识，比较支持、反证和未知项，形成Action实例及条件化P/O请求；允许任务内临时机制，不自动认定因果。
---

# AProf 机制诊断

职责见[诊断角色](../../workflows/agents/diagnosis.md)，输入输出见[C1 contract](../../workflows/contracts/diagnosis.md)。使用[机制与交接规则](../../workflows/references/diagnosis-v4.md)和[模板规范](graph/FORMAT.md)。

先运行 `diagnosis retrieve --root <完整包> --context <evidence.json>`，获得Symptom邻接线索及全部Problem轻量目录。邻接不是候选边界，旧权重只辅助阅读。由Agent按适用域、机制差异和未解释观测选择正文，用 `diagnosis expand --root <完整包> --context <同一evidence.json> --request <阅读请求.json> --output <新展开.json>` 记录理由并取得完整正文、机制分析及来源；字段和回放命令见[C1 contract](../../workflows/contracts/diagnosis.md#problem-正文按需展开)。

目录只用于找候选。形成机制比较、排除结论或据此实例化Action前，必须阅读判断所依赖的Problem正文，并说明正文如何影响判断。遇到正文指出的替代机制、反证或未解释观测，回到完整目录继续按需展开；不设固定候选数或top-k，不预先枚举本轮必须选择的Problem或Action，也不默认加载全部正文。容量不足首先是Action／计划门禁，不能自动认定容量压力机制。临时机制没有注册正文，单列其假设、依据和与已读模板的差异。

分别记录观察和解释。原始值／源码事实附对象、阶段、实现、workload、单位、比较基准和原始引用；派生值保存依赖，同一事实不能重复作为独立支持。proxy和未实现extractor不变成真实profile。复合观察按成员核验，旧Symptom名称不证明机制。

使用数值观测前，按[观测自洽检查](../../workflows/references/observation-checks.md)核对窗口、单位、时间分解与计数层级；可调用 `aprof_runtime.observation_checks.validate_and_derive` 保留派生依赖。缺数据保持 unknown，明确矛盾先修正为新证据快照；逻辑 GM 请求不能与 HBM 字节混算，派生副本不能脱离原始值和时间单独沿用。

候选卡记录支持、反证、unknown、替代解释、判别检查、状态与理由。反证不自动排除；排除必须说明依据。模板不足时可提出任务内临时Problem，明确差异和预测；不得自动写回模板图。

可实例化已注册Action，保留原前提与不变量，绑定真实目标及当前范围，向P/O给路由提示。临时Problem也可复用注册Action；临时新Action先提案。容量等unknown允许交C2条件分析，C3实施前所有原预期fact/state必须满足。

C1携带推理、证据及Action完整必要快照，下游无需读诊断图目录。新增证据创建后继，不改旧记录。P/O自行选实际模板／recipe；诊断不提前锁组合，不写候选代码或裁决性能。

历史v0003显式用 `graph route --graph <v0003目录> --context <旧evidence.json>` 回放。知识晋升、临时机制边界及四个[纸面案例](examples/README.md)按需阅读。本轮知识仅来源审阅，不声称目标设备瓶颈或收益。
