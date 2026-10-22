# PR #555：40 条评审意见逐项核对

核对日期：2026-10-23。结论：当前版本尚未满足全部要求。

核对对象：GitCode head `be463915a6667f0bbe7d9b1f6706562f73bacc76`；来自 GitHub `refactor/skill-libs-scaffolding` 的 `1b783b05c460f51688f77ee8661963545cad2dfa`，仅 `skill-libs/graph-base/1.3.0`。包内证据路径相对该目录；GitCode 导入时根映射为 `skills/tool-ops-optimize`。

“满足”仅表示找到了对应静态实现/文档证据，不表示评审已接受、真实设备已验证或历史归档原文已改写。outdated 不作 resolved；范围移除不作功能修复。未修改平台评论状态。

计数：满足 21；本轮移除 3；待环境验证 1；部分满足 12；未满足 3。

证据引文对应上述 GitCode 导入 head，而非本报告所在的后续 GitHub 提交。`IMPORT.md`、顶层 `SKILL.md` 和插件网址等包含 GitCode 接入适配，不能在未适配的来源目录逐字寻找；JSON 保留其当时路径、行号和引文。

## 优先未闭合项

1. #23/#24：BT/FP buffer 与频率域定义。
2. #34/#38：过开核/入口退出路径及逐族门禁、身份迁移。
3. #33：算法注入评测并未随新结构补齐。
4. #11：独立 reviewer 的角色/注册与调用。
5. 全量回归结果见同目录的回归报告；不能把包内失败归给 GitCode 配置。

## 01. 插件元数据中的项目网址无法访问

**结论：满足**。插件网址已改为真实 GitHub 来源和 asc-tools 目标仓库。

原评论：YANXI_ZHAO，ID `192837470`。

> 这个网址无法访问，请确认。

当前证据：

- `.claude-plugin/plugin.json:8`：  "homepage": "https://github.com/jieran-zhang/Aprof/tree/refactor/skill-libs-scaffolding/skill-libs/graph-base/1.3.0",

## 02. 安装与调用方式不应限定 Cursor

**结论：满足**。安装器支持显式宿主目录，提供 Claude/Codex/AGENTS 入口，不限定 Cursor。

原评论：YANXI_ZHAO，ID `192838002`。

> 没有cursor怎么办？只能限定cursor？

当前证据：

- `tools/install.py:54`：        "--skills-dir", type=Path, help="explicit host skills directory"
- `IMPORT.md:55`：保留完整包即可，不依赖 Aprof 原工作树，也不限定 Cursor。

## 03. 中文版注入说明的正文却是英文

**结论：本轮移除**。旧中文注入说明及其英文正文未作为活跃注入技能导入。属于范围删除，不能证明注入功能已修复。

原评论：YANXI_ZHAO，ID `192838346`。

> 这是中文版的？为什么只有英文？

当前证据：

- `IMPORT.md:5`：`1b783b05c460f51688f77ee8661963545cad2dfa`，仅导入

## 04. 确认 kernel 编译命令和工具链参数

**结论：待环境验证**。编译脚本仍使用 --asc-aicore-lang、--aicore-only 和 ld.lld -m aicorelinux；有参数及工具存在性检查，但本机无 CANN/NPU，不能确认真实目标编译通过。

原评论：YANXI_ZHAO，ID `192842414`。

> 请确认编译命令。

当前证据：

- `skills/ascendc-kernel-direct-invoke/references/build_kernel_o.sh:51`：    --asc-aicore-lang -c "$KERNEL_SRC" \

## 05. 确认 DAV_3510 / 950 离散计算使用 SIMT 的适用性

**结论：满足**。新增 3510/SIMT 说明：非规则索引/控制可比较 SIMT，但必须匹配 ISA、SDK、线程、寄存器、访存和同步条件。是适用性回答，不是该离散算子的实测结论。

原评论：YANXI_ZHAO，ID `192843756`。

> 这种离散型计算是否可以使用simt，如果是dav 3510或者950。

当前证据：

- `skills/npu-arch/references/regbase-simt.md:7`：SIMT 适用于非规则索引/控制与受支持 Scalar 操作，不自动替代批量 SIMD。lane 分组应合并 GM 访问并减少分歧；编译期 launch bound 与实际线程一致，检查寄存器/栈。混合 SIMD/SIMT 显式同步，并核算共享 UB 所有权。

## 06. 英文文件名对应的正文仍是中文

**结论：满足**。旧 api-algorithm-diagnosis-metrics_en.md 假英文副本未导入；本轮明确只保留中文，不伪造翻译。

原评论：YANXI_ZHAO，ID `192844250`。

> 这个应该是英文的文档。

当前证据：

- `IMPORT.md:12`：不声明已完成 NPU 功能或硬件性能收益验收。中文文档不生成英文副本。

## 07. 规范确认：skills 目录无需中英双份 Markdown

**结论：满足**。遵循评审确认的 skills 无需中英双份，不再生成重复 _en 文档。

原评论：yaoguangxiu，ID `192871312`。

> skills目录不需要md文档中英文

当前证据：

- `IMPORT.md:12`：不声明已完成 NPU 功能或硬件性能收益验收。中文文档不生成英文副本。

## 08. 安装命令及路径与 asc-tools 目录布局不一致

**结论：满足**。包安装根及来源映射明确，完整包安装器按 registry 的包内路径建立链接。

原评论：yaoguangxiu，ID `192876096`。

> 路径和当前asc-tools目录不一致

当前证据：

- `IMPORT.md:9`：`skills/tool-ops-optimize/`，包内相对路径保持。
- `tools/install.py:35`：        source = (root / entry["source"]).resolve()

## 09. 工作流依赖的 CANNBot skill 无法直接获取

**结论：满足**。workflow 依赖列表为空，所需支持技能及固定 CANNBot 来源随包提供，不要求获取私有 cannBot skill。

原评论：yaoguangxiu，ID `192876765`。

> cannbot skill无法直接获取

当前证据：

- `skills/registry.json:12`：    "dependencies": [],
- `skills/ascendc-aprof-diagnosis/graph/FORMAT.md:9`：slots逐项定义name、kind、description、required；对象槽位按实例绑定，不把一个tensor的证据用于另一个。sources保存包内完整文件路径、original_path、固定revision、1-based闭区间lines、文件sha256和excerpt_sha256。正文应独立可用，来源用于追溯。

## 10. 安装注册的 diagnosis skill 名称与实际名称不一致

**结论：满足**。注册名和真实 SKILL 的 name 均为 ascendc-aprof-diagnosis。

原评论：yaoguangxiu，ID `192877557`。

> 应该是ascendc-aprof-diagnosis？

当前证据：

- `skills/registry.json:58`：        "name": "ascendc-aprof-diagnosis",
- `skills/ascendc-aprof-diagnosis/SKILL.md:2`：name: ascendc-aprof-diagnosis

## 11. 要求独立 reviewer，但没有对应 agent 文件

**结论：部分满足**。已有 ascendc-code-review 技能与优化角色调用链接；插件 agents 仍只有六个阶段角色，没有独立 reviewer agent/注册。因此不能说独立 reviewer 要求已满足。

原评论：yaoguangxiu，ID `192878042`。

> 独立 sub-agent reviewer，没有对应文件

当前证据：

- `skills/ascendc-code-review/SKILL.md:2`：name: ascendc-code-review
- `workflows/agents/optimization.md:33`：- [ascendc-code-review](../../skills/ascendc-code-review/SKILL.md)：C3；候选构建与完整正确性验证前。
- `.claude-plugin/plugin.json:11`：  "agents": [

## 12. 建议遵循仓库的 SKILL + references 组织方式

**结论：部分满足**。已提供顶层/各技能 SKILL 及 references 出链；完整 skill-graph 另有 workflows、graph、knowledge 和 runtime，不是所有正文都放 references。组织方式是否接受需评审确认。

原评论：yaoguangxiu，ID `192900103`。

> asc-tools仓使用skill+reference的结构，建议保持一致

当前证据：

- `SKILL.md:1`：---
- `skills/ascendc-aprof-diagnosis/SKILL.md:12`：职责见[诊断角色](../../workflows/agents/diagnosis.md)，输入输出见[C1 contract](../../workflows/contracts/diagnosis.md)。使用[机制与交接规则](../../workflows/references/diagnosis-v4.md)和[模板规范](graph/FORMAT.md)。

## 13. 解释 hypotheses / metrics 最多三条的依据

**结论：满足**。不再强制最多三条 hypotheses/metrics，也没有固定 top-k；要求按事实和未解释观测展开必要候选。

原评论：yaoguangxiu，ID `192921720`。

> 为什么这里强制最多3条？出于tokens的考虑吗

当前证据：

- `skills/ascendc-aprof-diagnosis/SKILL.md:18`：目录只用于找候选。形成机制比较、排除结论或据此实例化Action前，必须阅读判断所依赖的Problem正文，并说明正文如何影响判断。遇到正文指出的替代机制、反证或未解释观测，回到完整目录继续按需展开；不设固定候选数或top-k，不预先枚举本轮必须选择的Problem或Action，也不默认加载全部正文。容量不足首先是Action／计划门禁，不能自动认定容量压力机制。临时机制没有注册正文，单列其假设、依据和与已读模板的差异。
- `workflows/contracts/diagnosis.md:18`：| 假设 | 可能机制、预期影响、适用 case；按证据比较保留、排除或继续判别，不固定候选数 |

## 14. 触发条件应覆盖输入源码，不限于仅有 kernel 源码

**结论：满足**。诊断输入包含当前父版本源码、host/tiling/kernel 理解、workload 和已有证据，不要求只有裸 kernel。

原评论：yaoguangxiu，ID `192998308`。

> 触发条件应该是输入是源码，不是“只有kernel源码”。

当前证据：

- `workflows/contracts/diagnosis.md:9`：引用 preparation、[code-understanding 报告](code-understanding.md)、实际分析父版本源码、workload、架构和已有计时/机制证据。先消费理解报告中的整体算法、实际分派和数据依赖，按当前诊断需要核对受影响源码，不重复从头理解实现。补证据后重新诊断或任意后继轮次时，先读任务根的[跨轮摘要](../references/optimization-history.md)，按需展开原决策、变更和结果；再引用上一次 diagnosis、新的 profiling 与同一适用理解报告；源码或相关条件改变时使用仅更新受影响部分的理解后继。纯新增 profiling 不重做理解。完整优化会话的基线准备不能被诊断阶段重新生成。

## 15. 源码路由文档不应混入 profiling 阶段描述

**结论：部分满足**。源码观察与 profile 观察已分开为独立 Symptom，且明确 source 不推出 profile；但源码 Symptom 正文仍包含后续 profiling 判别提示，尚不等于严格删除所有 profiling 描述。

原评论：yaoguangxiu，ID `193004610`。

> 这里不应该涉及profiling的描述

当前证据：

- `skills/ascendc-aprof-diagnosis/graph/symptoms/symptom.source.scalar_element_loop.md:196`：  text: 本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。

## 16. 删除路由文档中无关的 CANNBot 加载说明

**结论：满足**。当前入口使用本地已固定来源和真实技能路径；旧 source-hypothesis-routing 中无关的外部 CANNBot 加载要求不再是当前路由入口。

原评论：yaoguangxiu，ID `193006349`。

> 关于cannbot skill的描述和本reference没有关联，建议删除

当前证据：

- `skills/ascendc-aprof-diagnosis/SKILL.md:16`：先运行 `diagnosis retrieve --root <完整包> --context <evidence.json>`，获得Symptom邻接线索及全部Problem轻量目录。邻接不是候选边界，旧权重只辅助阅读。由Agent按适用域、机制差异和未解释观测选择正文，用 `diagnosis expand --root <完整包> --context <同一evidence.json> --request <阅读请求.json> --output <新展开.json>` 记录理由并取得完整正文、机制分析及来源；字段和回放命令见[C1 contract](../../workflows/contracts/diagnosis.md#problem-正文按需展开)。
- `skills/ascendc-aprof-diagnosis/graph/FORMAT.md:9`：slots逐项定义name、kind、description、required；对象槽位按实例绑定，不把一个tensor的证据用于另一个。sources保存包内完整文件路径、original_path、固定revision、1-based闭区间lines、文件sha256和excerpt_sha256。正文应独立可用，来源用于追溯。

## 17. Scalar 现象的源码判定条件不清晰

**结论：满足**。Scalar 源码现象已分解为逐元素 Scalar 循环、有效域/API/地址依赖和 dtype/分支/别名条件；不把源码观察直接认定为热点。extractor 仍明确未实现。

原评论：yaoguangxiu，ID `193008544`。

> 源码呈现Scalar现象是如何判定的？
> 在路由原则中这样描述，user/agent可能都会比较难以理解其含义

当前证据：

- `skills/ascendc-aprof-diagnosis/graph/symptoms/symptom.source.scalar_element_loop.md:154`：  text: 当前逐元素循环调用Scalar读写或算术
- `skills/ascendc-aprof-diagnosis/graph/symptoms/symptom.source.scalar_element_loop.md:166`：  - 当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

## 18. 算子专属规则与通用路由规则混用

**结论：满足**。通用诊断记录事实/机制；具体算法方案进入 P 的 family 路由及模板，并要求核对平台/workload。模板可检索不代表对所有算子适用。

原评论：yaoguangxiu，ID `193018097`。

> 算子专属规则不建议和其他通用规则混用，

当前证据：

- `skills/ascendc-aprof-parallel-planning/knowledge/families/sort-topk/ROUTER.md:56`：按 family 与 workload 选择任务划分、所有权和组合方案；可同时进入多个分支。比较适用主方案与保守回退，C2 输出必要内容快照、参数和实现自由度。
- `workflows/contracts/planning.md:15`：- 各 workload group 的算法、独立任务、所有权、归约/同步、workspace 与容量模型。

## 19. 输出要求与 diagnosis_hypotheses JSON 契约不一致

**结论：部分满足**。旧 diagnosis_hypotheses 输出已被版本化 C1/reasoning/action-decision 替代，有稳定假设 ID 和支持/反证/unknown；是契约替换，不是继续满足旧 JSON 字段。完整交接兼容性另受回归失败影响。

原评论：yaoguangxiu，ID `193021320`。

> 输出检查内容和diagnosis-hypotheses.json的要求不一致
>
> hypotheses.id/summary/confidence等

当前证据：

- `workflows/contracts/diagnosis.md:13`：每个假设使用稳定的本任务内 ID，并填写：
- `workflows/contracts/diagnosis.md:55`：## 当前交接 C1（handoff v4）

## 20. 增加到 diagnosis_hypotheses 契约定义的链接

**结论：满足**。诊断 SKILL 直接链接现行 C1 contract、选择规则和图格式，不再要求读者自行寻找输出契约。

原评论：yaoguangxiu，ID `193022841`。

> diagnosis_hypotheses.json的要求定义在contract.md文件中，建议增加一个指向它的链接

当前证据：

- `skills/ascendc-aprof-diagnosis/SKILL.md:12`：职责见[诊断角色](../../workflows/agents/diagnosis.md)，输入输出见[C1 contract](../../workflows/contracts/diagnosis.md)。使用[机制与交接规则](../../workflows/references/diagnosis-v4.md)和[模板规范](graph/FORMAT.md)。

## 21. 统一各文档使用的证据等级定义与枚举

**结论：满足**。当前声明依据统一为 source_statement/code_fact/mechanism_inference/case_support/legacy_seed，schema 明确定义；旧直接/派生/Trace 等历史措辞不再冒充同一现行枚举。

原评论：yaoguangxiu，ID `193026597`。

> 各个reference中描述的证据等级不一致，需要统一描述
>
> 直接 / 派生 / Trace / 对比 / source-hypothesis / source+trace+tiling 等等

当前证据：

- `skills/ascendc-aprof-diagnosis/graph/FORMAT.md:11`：claims逐项包含id、text、basis、source_indexes、review_status和limitations。basis区分source_statement、code_fact、mechanism_inference、case_support和legacy_seed。来源审阅、模板active状态和任务判断分别维护；旧内容不直接升级为已验证机制。review分别说明source_credibility、discriminating_power、observed_frequency及gaps，不混成单一权重。
- `schemas/diagnosis-record.schema.json:339`：              "source_statement",

## 22. 明确证据等级由谁使用、如何影响后续判断

**结论：满足**。C1 的协调者/规划/采集和 C2/C3 消费证据；证据影响实施条件、性能假设和未知状态。派生事实不能算独立支持，合成输入不升级为硬件证据。

原评论：yaoguangxiu，ID `193033885`。

> 证据等级没有使用者？

当前证据：

- `workflows/contracts/diagnosis.md:5`：生产者：[诊断角色](../agents/diagnosis.md)。消费者：协调者、规划和采集。外层使用 [公共契约](common.md)，`stage=diagnosis`、`role=diagnosis`。
- `workflows/references/observation-checks.md:63`：输入和依赖值 hash 使用 runtime 的规范 JSON hash；它与原始文件按字节计算的 artifact hash 用途不同。派生项的 `independent_support=false`：原值、包装后的原值和由其计算的比例仍属于同一依赖链，不能重复当作独立支持。`usable_as_evidence` 只表示局部算术没有冲突，不能绕过 scope、来源或交接前提检查。

## 23. 区分 bias table buffer 与 Fixpipe buffer，并说明 BT 容量用途

**结论：未满足**。未在活跃架构/诊断/实现说明中找到 BT 与 Fixpipe/FP buffer 的完整区别及 BT 容量用途。Fixpipe 通路说明不等于 buffer 容量定义；历史来源原文仍保留。

原评论：yaoguangxiu，ID `193068124`。

> 这里混用了bias table buffer和fixpipe buffer，需要增加FP Buffer的说明
> 另外，文档中没有看到使用 BT 容量的地方

当前证据：

- `skills/npu-arch/SKILL.md:14`：从 `PlatformAscendC` 获取可见 AIC/AIV 和可用 UB/L1/L0/L2，记录每个值的来源。未知值为 null，不可用作分母或授权容量相关特化。ISA 特性还需匹配 SDK API 和编译选项；产品族不隐含固定核数、带宽或峰值 FLOPS。

## 24. 明确 Current Freq / Rated Freq 对应的频率域

**结论：未满足**。平台说明有 Cube 频率示例，观测要求 cycle 换算绑定频率来源；仍未定义旧 Current Freq / Rated Freq 对应何频率域及可比条件。不能用“有频率来源”代替该问题。

原评论：yaoguangxiu，ID `193070959`。

> current freq / rated freq分别是指的什么频率？

当前证据：

- `skills/npu-arch/references/platform-evidence.md:23`：| INI | AIC/AIV | UB/L0C KiB | Cube 频率 MHz |

## 25. 明确 GM / L2 / L1 带宽以及读写方向

**结论：满足**。观测 contract 要求计数 layer、同窗口和 read/write 方向；logical_gm 与 hbm 不可混算，带宽参照须同层级同口径，缺实际层级不能称饱和。

原评论：yaoguangxiu，ID `193072153`。

> 这里的带宽指的是GM带宽、L2带宽还是L1带宽？读和写也是不一样的

当前证据：

- `workflows/references/observation-checks.md:45`：每个计数必须声明 `layer`。例如 `logical_gm` 表示程序发出的逻辑请求字节，`hbm` 表示 HBM 事务字节；二者不能相加，也不能用其中一层的写量补齐另一层缺失的读写总量。同窗口、同层级、同方向的重复计数不会被自动累加。缺少调用次数时，平均请求大小保持 unknown。
- `skills/ascendc-aprof-diagnosis/graph/symptoms/symptom.profile.memory_bandwidth_saturation.md:108`：    mechanism_metric: 实际读写B/同窗口s=B/s；read、write、混合方向分别对应同平台持续带宽分母。

## 26. Compute 主导判定需覆盖 Cube，或明确 Vector 范围

**结论：部分满足**。workflow 入口明确当前主要 910C/A3 Vector；Cube/3510 仍作为带适用域的来源知识保留，不提供通用 Vector-only compute 判定。若要求删除全部 Cube reference，该字面要求尚未满足。

原评论：yaoguangxiu，ID `193078447`。

> compute是否为主导，应该算上cube计算率，如果当前阶段只针对vector算子做优化，建议在入口处明确说明，同时删除reference中关于cube的描述，否则整体文档的正确性有偏差（MTE conflict描述同样如此）

当前证据：

- `workflows/aprof-performance-workflow.md:65`：先读取用户已有信息，冻结原始源码、完整 workload、输入/oracle、实际设备/工具链、执行范围和预算，传递用户/外层驱动给定的轮数、达标停止条件与重试范围。skill 不自设轮数或连续无收益停止规则；未指定多轮时只执行当前明确请求的方案并报告状态。当前主要覆盖 910C/A3 Vector 场景；实际架构不能只由 DAV_2201 推断。
- `skills/npu-arch/references/regbase-simt.md:3`：只有架构档案确认支持且已安装 SDK 兼容时启用。NpuArch 3510 表示 ISA；产品名或另一 SDK 的头文件不证明当前二进制支持该 API。

## 27. workspace 属于 GM，不应作为片上内存指标混写

**结论：满足**。当前 P/O 模板将 GM workspace 与 UB/L1/L0 容量分别记账；如 split reduction 的 GM partial 写读和 epilogue 的 GM 槽位均明确。

原评论：yaoguangxiu，ID `193086875`。

> workspace占用的是global memory，不是片上内存。
> 跟文档主题有偏差

当前证据：

- `skills/ascendc-aprof-parallel-planning/knowledge/families/reduction/templates/split.md:212`：令 G 为独立输出组数、R 为每组输入数、S 为分片数、b 为每个 partial 状态的字节数。单状态 sum 的 b 是累加 dtype 宽；Welford 是 count/mean/M2 完整状态及实际对齐，不能仅计一个 float。分核方案产生 GS 份 partial，GM workspace 的逻辑写读至少 `2GSb` 字节，另有每组 S−1 次状态合并、两阶段调度及槽位对齐开销。提高 S 可能增加可并行任务，但不会减少输入总读取和必须的归约工作。
- `skills/ascendc-aprof-parallel-planning/knowledge/families/under-fusion/templates/epilogue.md:71`：GM 槽位最低用户容量为 `W_slots=q*A(m*n*b_c)` 乘以同时存活逻辑生产者数，另加系统 API workspace 与对齐；q 由生产消费流水和合法同步决定。若真实直连且无 spill，才可能消除该中间写读流量。比较完整成本：MatMul 周期、Fixpipe/中转搬运、Vector 激活、启动与等待、UB 预留导致的 base 块变化，以及生产者快于消费者时的背压。独立 epilogue 是合法候选，不能只按 kernel 数选优。

## 28. API/Scalar 规范内容与算法选择主题不匹配

**结论：满足**。当前规划材料已有真正的算法/数值结构：静态 Split-K、StreamK、attention partial 合并、统计归约；API/Scalar 实现材料另有自己的技能/branch。此结论不包含算法注入评测。

原评论：yaoguangxiu，ID `193100101`。

> 这篇文档好像和“算法”没啥关联，主题是scalar控制开销和api的使用规范

当前证据：

- `skills/ascendc-aprof-parallel-planning/knowledge/families/matmul/templates/splitk.md:7`：title: 静态 Split-K：固定 K 分段与部分和归并
- `skills/ascendc-aprof-parallel-planning/knowledge/families/flash-attention/templates/splitkv.md:86`：## 局部状态表示与合并公式

## 29. 区分 npu-arch 技能入口与实际硬件数据来源

**结论：满足**。npu-arch 明确为技能入口；实际值来自 PlatformAscendC、设备探测或有来源的 SDK 配置，保留原始值和 provenance，不把 /npu-arch 本身当硬件测量。

原评论：yaoguangxiu，ID `193103990`。

> 这里的npu-arch是独立的skill？不适合放到数据来源

当前证据：

- `skills/npu-arch/SKILL.md:14`：从 `PlatformAscendC` 获取可见 AIC/AIV 和可用 UB/L1/L0/L2，记录每个值的来源。未知值为 null，不可用作分母或授权容量相关特化。ISA 特性还需匹配 SDK API 和编译选项；产品族不隐含固定核数、带宽或峰值 FLOPS。
- `skills/npu-arch/references/platform-evidence.md:11`：## 获取实际值

## 30. 核利用率 metric 的定义重复，需要统一维护位置

**结论：部分满足**。核相关观察有独立模板并要求同类核、窗口及分母；但公式/核数说明仍分布在各模板，未建立统一 metric 定义与引用索引。不能证明重复定义已全部消除。

原评论：yaoguangxiu，ID `193105855`。

> 核利用率的metric定义，多处重复定义

当前证据：

- `skills/ascendc-aprof-diagnosis/graph/symptoms/symptom.profile.tasks_below_available_cores.md:121`：    counts: 指令/任务/repeat/槽位是计数；比值保留明确分子分母和窗口，不能混用AIC/AIV或单核/全调用

## 31. 注入工具文档中 22 处命令和引用缺少 tool-ops-optimize 路径层

**结论：本轮移除**。旧 ascendc-aprof-inject-problems 命令未进入本轮活跃技能，错误的 22 处命令不再是可执行入口；未把注入工具迁移后逐条验证，不能声称其功能修好。

原评论：yaoguangxiu，ID `193109211`。

> **问题 1：文档内 22 处命令/引用路径少了一层 `tool-ops-optimize`，按文档执行必然 file not found**
>
> 本文件 `:34`、`:63`、`:66`、`:70`（四条可执行命令）与 `:80-83`（四条 Related Skills），以及 `ascendc-kernel-direct-invoke/SKILL.md:28`，全部写成 `skills/aprof/...`；但本 PR 的实际落地路径是 `skills/tool-ops-optimize/aprof/...`。
>
> 验证（在本 PR head `5d37afb` 的文件树上）：
>
> ```bash
> grep -rn "skills/aprof/" skills/tool-ops-optimize/aprof/benchmark/ | wc -l                      # → 22
> grep -rn "skills/tool-ops-optimize/aprof/benchmark" skills/tool-ops-optimize/aprof/benchmark/ | wc -l   # → 0
> ```
>
> 即：错误写法 22 处，正确写法 0 处。
>
> 建议：
>
> ```diff
> - python skills/aprof/benchmark/ascendc-aprof-inject-problems/tools/inject_case.py \
> + python skills/tool-ops-optimize/aprof/benchmark/ascendc-aprof-inject-problems/tools/inject_case.py \
> ```
>
> 22 处一并替换。另外建议在 check_pr 里加一条门禁：skill 文档中出现的 `skills/...` 相对路径必须能在 PR 文件清单里命中，否则报错——这类路径漂移在后续目录调整时还会复发。

当前证据：

- `IMPORT.md:5`：`1b783b05c460f51688f77ee8661963545cad2dfa`，仅导入

## 32. 六篇 tiling 注入文档没有被索引登记，成为孤儿文档

**结论：本轮移除**。旧六篇 tiling 注入孤儿文档未作为活跃技能导入；当前 P family 索引不是这些注入 recipe 的补登记。

原评论：yaoguangxiu，ID `193109221`。

> **问题 2：`tiling` 族有 6 篇 inject reference 是孤儿文档，索引未登记，agent 永远读不到**
>
> 本表 `:9` 的 `tiling` 行只登记了 `tiling-inject.md` 一篇，`SKILL.md:19-24` 的加载清单也是六族各一篇。但 `references/` 下同时存在：
>
> `blockdim-inject.md`、`tail-inject.md`、`tilelen-small-inject.md`、`tilelen-large-inject.md`、`tilenum-inject.md`、`dynshape-inject.md`
>
> 逐个验证全仓引用数为 0（`grep -rl <name> skills/` 只命中文件自身），含 `_en` 镜像共 **12 个文件**。它们对应的是 `:46-53` legacy alias 时代的按 recipe 拆分文档；现在 recipe 已统一走 `tiling-inject.md` + `--problem-id`，这 6 篇成了死文档。
>
> 建议二选一：
>
> 1. 直接删除这 12 个文件；或
> 2. 把内容合并进 `tiling-inject.md`，并在本表补登记行。
>
> 保持现状最差：`SKILL.md:18` 的“Load the relevant family reference”只指向一篇，这 6 篇既不进 agent 上下文、又要跟着中英文双语一起维护，后续任何 tiling recipe 改动都会出现“改了文档但没人读”的静默失效。

当前证据：

- `skills/ascendc-aprof-parallel-planning/knowledge/families/sort-topk/ROUTER.md:58`：- [Sort/TopK 分块与层次归并](templates/merge.md)

## 33. api_algorithm 评测仅覆盖 API/Scalar，缺少算法选择 recipe

**结论：未满足**。旧注入评测未导入，因而也没有新增 full_sort_for_topk/two_pass_softmax 等 behavior-preserving 注入 recipe。真实算法规划资料存在，但不能代替这条算法评测覆盖要求。

原评论：yaoguangxiu，ID `193109227`。

> **问题 3：`api_algorithm` 族 3 个 recipe 全是 API/Scalar 形态，0 个考察算法选择**
>
> `:38-40` 三个 recipe：`scalar_loop_redundant`（标量循环）、`small_vector_api_chunks`（Vector API 粒度）、`redundant_cast_or_vector_copy`（Cast 冗余），都不是算法层问题。
>
> 这与诊断侧现状是一致的：`diagnosis/references/api-algorithm-diagnosis-metrics.md` 的 17 行 metric 中 **0 行是算法级**（全文 `grep "计算量|复杂度|O(N|迭代次数"` 0 命中），14 行问题矩阵中只有 `:67` Reduce「按 AR/ARA/Group Reduce 选择算法」一行涉及算法选择；全文唯一真正的算法判据 `:93`「若 TopK 小而 N 大，检查是否仍做了全量排序或过多归并」埋在“按算子族诊断重点”的散文里，没进问题矩阵、没有 metric、没有证据等级。
>
> 结果是评测集与诊断矩阵双向都不覆盖算法维度：族名叫 `api_algorithm`（`references/contracts.md:69` 的枚举值），但注入端造不出算法题、诊断端也没有算法判据，`label_alignment_report.json` 在这一族上实际只考了 API 使用规范。
>
> 建议至少补 1-2 个真算法 recipe（都满足 `AGENTS.md:80` 的 behavior-preserving 约束，只改算法选择不改数学结果）：
>
> - `api_algorithm/full_sort_for_topk`：K≪N 时仍走全量排序 + 多轮归并；
> - `api_algorithm/two_pass_softmax`：online softmax 退化为两遍扫描，多一次 reduce 与一次 UB/GM 往返。
>
> 同时需在 `api-algorithm-diagnosis-metrics.md` 补对应判据行（如“计算量放大率 = `aiv_vec_fops + aic_cube_fops` / 算法最小必要运算量(shape,dtype)”），否则注入了也诊断不出来，该 recipe 的 alignment 会恒为 miss，反而拉低准确率统计。

当前证据：

- `skills/ascendc-aprof-parallel-planning/knowledge/families/sort-topk/ROUTER.md:58`：- [Sort/TopK 分块与层次归并](templates/merge.md)
- `skills/ascendc-aprof-parallel-planning/knowledge/families/flash-attention/templates/splitkv.md:86`：## 局部状态表示与合并公式

## 34. [P0] 核并行策略缺少减核和空闲核早返回方向

**结论：部分满足**。连续 elementwise 模板明确 C≤min(Q,可用核) 和比较较少 C；但没有通用 overlaunch 判别、usedCoreNum 入口早返回的闭环指引。含同步的空闲参与者还不能任意 return。

原评论：yaoguangxiu，ID `193126982`。

> **问题 1（P0）：本文档只有“增核”方向，没有“减核 / 空闲核早返回”方向，与 benchmark 注入的 case 对不上**
>
> 本行把目标定义为“增加有效并行任务、平衡核间负载”，Deep Routing `:10-17` 的 8 行 patch shape 也全是增加并行度（split / StreamK / split-KV / Group Reduce / 两级归并），**没有一行是“动态减少 usedCoreNum / 空闲核入口早返回”**。
>
> 根因在 `:21` 的容量模型少了一项：
>
> ```text
> activeCores           = min(totalTasks, availableCores)                          # 本文档 :21
> active_cores_attainable = min(block_dim, total_tasks_or_tiles, available_cores)  # workload-aware-diagnosis.md:30
> ```
>
> 漏掉 `block_dim` 后，模型在数学上无法表达“过开核”（`blockDim > totalTasks`），减核策略自然生成不出来。
>
> 诊断侧有 3 行正是这个方向：
> - `skills/tool-ops-optimize/aprof/diagnosis/references/ai-core-utilization-diagnosis-metrics.md:71` 过开核导致有效利用低 → 小 shape 动态减少 usedCoreNum
> - `:72` 部分 core 空闲 → 空闲核入口直接返回
> - `:80` 动态 shape 下策略不适配 → Host Tiling 按 shape 重算 usedCoreNum
>
> benchmark 侧也已经注入了这个 case：`benchmark/ascendc-aprof-inject-problems/tools/inject_case.py:33-44` 的 `overlaunched_empty_cores`（`default_blockdim=32, default_output_elements=128`，`expected_diagnosis_family="ai_core_utilization"`），`references/ai-core-utilization-inject.md:10` 同样列出。
>
> 验证（PR head `5d37afb`）：
>
> ```bash
> grep -rn "减核\|减少 usedCoreNum\|早返回\|early return\|减小 blockDim" \
>   skills/tool-ops-optimize/aprof/optimization/ | grep -v _en     # → 0 命中
> ```
>
> 后果：`ai_core_utilization` 族 3 个 recipe 中有 1 个在优化侧无对应 patch shape，candidate 只会往 split/增核方向改 → 该 case 的 label alignment 恒为 miss（与 `api_algorithm` 族的缺陷同型）。
>
> 建议：
>
> ```diff
> -- `totalTasks = product(split_dims)`，`activeCores = min(totalTasks, availableCores)`。
> +- `totalTasks = product(split_dims)`，`activeCores = min(blockDim, totalTasks, availableCores)`；
> +  `blockDim > totalTasks` 属于过开核，优先减核而不是 split。
> ```
>
> 并在 Deep Routing 补 2 行：
>
> ```diff
> +| 过开核 | `blockDim > totalTasks` 且头开销占比高 | Host Tiling 动态 `usedCoreNum = min(coreNum, totalTasks)`，按 shape 重算 |
> +| 空闲核未早返回 | 部分 block `ai*_time` 极低或无有效 pipe 时间 | kernel 入口对 `block_idx >= usedCoreNum` 直接 return |
> ```

当前证据：

- `skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md:94`：令 g 为满足实际搬运接口及输出独占写要求的元素粒度，Q=ceil(N/g) 为逻辑块数。选择 1≤C≤min(Q,C_available)，定义 q=Q//C、r=Q%C。核 c 的起始块 b_c=cq+min(c,r)，块数 n_c=q+[c<r]，其有效元素区间为 `[b_c*g, min((b_c+n_c)*g,N))`。所有区间并集恰为 `[0,N)`，交集为空；尾部不足 g 的部分由唯一末核处理，绝不通过重叠搬出尾块补齐。
- `skills/ascendc-aprof-parallel-planning/knowledge/families/matmul/templates/streamk.md:97`：partial 完成依赖同时包含“计算结束”和“数据对消费者可见”；950 样例由 Cube 发跨核 flag，Vector 等待并做归并，空闲参与者也经过所需同步。移植或改变 blockDim 时必须重新列出全部参与者和退出路径，不可仅复制几条 flag。

## 35. [P1] 路由条件重叠，缺优先级、阈值、术语定义和 playbook 链接

**结论：部分满足**。新版通过机制比较、替代解释、具体 family/叶出链替代单一 Deep Routing 表，并要求说明选择理由；但未补成旧要求的完整场景优先级/阈值/术语表，不能因路由重构称全部完成。

原评论：yaoguangxiu，ID `193126988`。

> **问题 2（P1）：Deep Routing 的 decision gate 不互斥、无优先级、无量化阈值；6/8 行的算子族术语在本文档内无定义，且全文 0 出链**
>
> 1. **gate 重叠**：`:12` 的 `mCnt*nCnt 远小于 AIC 数` 与 `:13` 的 `mCnt*nCnt % aicNum 小尾轮`——当 `mCnt*nCnt < aicNum` 时余数等于自身，两行同时成立，文档未给判定顺序。StreamK 与 DP+SK 是代价差别很大的两种改法，路由结果不确定；`:10` 与 `:14` 同样可同时成立。
> 2. **无阈值**：“远小于”“小尾轮”“方差高”“明显更重”全是定性词。诊断侧同一指标是有阈值的（`ai-core-utilization-diagnosis-metrics.md:34`：核间耗时不均衡 >10% 需关注、>30% 通常严重不均），优化侧没有继承 → gate 不可判定。
> 3. **术语悬空**：`fan-in`（`:17`，全仓仅此 1 处、无定义）、`Phase 3/4`（`:17`，定义在 `reduction-sort-optimization-playbook.md:41`）、`DP+SK`（`:13`，展开在 `matmul-optimization-playbook.md:13`）、`S2`（`:10`）、`LSE`（`:15`，在 `softmax-fa-optimization-playbook.md:10-11`）。
> 4. **0 出链**：
>
> ```bash
> grep -c "](" skills/tool-ops-optimize/aprof/optimization/references/ai-core-utilization-optimization-strategies.md   # → 0
> ```
>
> 而 `optimization/SKILL.md:40` 规定默认只加载 routing + candidate-design + 1 个分支文档，`SKILL.md:41-45` 又要求“load exactly one matching operator playbook”——本文档没告诉 agent 哪一行该配哪本 playbook，单独加载时 `:12-17` 这 6 行不可执行。（对比：诊断侧 6 张矩阵有 5 张带“使用时应交叉参考”段；`optimization/references/` 下 13 个文档 links 全为 0。）
>
> 建议：Deep Routing 增加 `Playbook` 列（MatMul 行 → `matmul-optimization-playbook.md`，FA 行 → `softmax-fa-optimization-playbook.md`，Reduction/Sort 行 → `reduction-sort-optimization-playbook.md`），表头上方写明 gate 判定顺序（先 `:10` 任务数不足 → 再 `:12/:13` MatMul 专属 → 最后 `:16/:17` 阶段性），并把两行 MatMul gate 改成互斥条件：`mCnt*nCnt < aicNum`（欠并行）与 `mCnt*nCnt >= aicNum && mCnt*nCnt % aicNum != 0`（末轮碎片）。

当前证据：

- `workflows/references/action-selection.md:38`：## 确定方案与成员 Action 之前
- `skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md:114`：## 参数选择与替代边界

## 36. [P1] 容量模型缺可代入公式，枚举、命名和核数分母不一致

**结论：部分满足**。已给出可代入的任务均衡、UB、Split-K/Split-KV 字节和成本公式，并区分同类核来源；旧 tiny/small/normal/large 契约已改为 workload 域比较，缺少旧到新术语/枚举的明确迁移对照。

原评论：yaoguangxiu，ID `193126995`。

> **问题 3（P1）：Capacity / Work Model 段缺可代入的公式与分母来源，术语/枚举与 contracts、诊断侧漂移**
>
> 1. `:22` “work_per_core 必须高于小块 MTE/launch/Sync 启动成本”：无公式、无阈值。`workload-aware-diagnosis.md:31-32` 已有 `elements_per_core` 与 `useful_bytes_per_core`，本文档既不引用也不复现。
> 2. `:23` split-K 只说“要加 workspace_partial + reduce/cast + sync overhead”，没给公式；同一策略在 `optimization-candidate-design.md:41` 与 `references/contracts.md:490` 给的是 `baseM*baseN*sizeof(float)*kCnt`。`:24` FA split-KV 的公式在 `softmax-fa-optimization-playbook.md:18`（`split_count * Bq * (D + state)`，32B 对齐）。三处描述只有一处可算 → `capacity_model` 字段（`contracts.md:479` 要求）填不出来。对比 `tiling-optimization-strategies.md:26-30`，那段全是可代入不等式。
> 3. `:31` `tiny/small/large` 缺 `normal`，契约枚举是 `tiny/small/normal/large`（`workload-aware-diagnosis.md:14`）。
> 4. `:10` `tiny-limited` 是本文档独有词（全仓仅 1 处），规范值是 `workload_limited`（`bound-deep-routing.md:88`、`workload-aware-diagnosis.md:39`）→ agent 可能写出非枚举值。
> 5. `availableCores`/`activeCores`/`split_dims`/`totalTasks`/`usedCoreNum`（`:10`、`:21`、`:29`）在本文档内首次出现且无定义、无来源；诊断侧对应 `available_cores`/`active_cores_attainable`/`Block Dim`/`GetCoreNumAiv()`，`usedCoreNum` 的关系式在 `ai-core-utilization-diagnosis-metrics.md:107`。同一概念两套命名，跨文档无法对齐。
> 6. **AIC/AIV 分母混用**：`:21` 用不分族的 `availableCores`，`:12` 用“AIC 数”，`:29` 用“AIV/AIC 核数”，未规定按算子类型选分母（纯 Vector→AIV、MatMul→AIC、mix kernel 还要看配比，诊断侧 `:77` 有专行）。
>
> 建议：
>
> ```diff
> -- `totalTasks = product(split_dims)`，`activeCores = min(totalTasks, availableCores)`。
> -- `work_per_core` 必须高于小块 MTE/launch/Sync 启动成本；增核不能把 copy 粒度切碎。
> -- split-K/StreamK：`parallel_tasks = MN_tasks * kCnt`，但要加 `workspace_partial + reduce/cast + sync` overhead。
> -- FA split-KV：`partial_O + partial_lse` workspace 与 combine time 必须小于 KV 并行收益。
> +- `availableCores`：Vector 算子取 `GetCoreNumAiv()`，Cube/MatMul 取 `GetCoreNumAic()`（来源 `/npu-arch` 或 `PlatformAscendC`）。
> +- `activeCores = min(blockDim, totalTasks, availableCores)`；`elements_per_core = ceil(total_elements / max(activeCores,1))`。
> +- 增核门槛：`elements_per_core * dtype_bytes >= useful_bytes_per_core_min`，否则每核 copy 退化为小块 MTE bound。
> +- split-K/StreamK：`parallel_tasks = MN_tasks * kCnt`，`ws_bytes = baseM * baseN * sizeof(float) * kCnt`，另计 reduce/cast + sync。
> +- FA split-KV：`ws_bytes = split_count * Bq * (D + state)`（32B 对齐），combine time 必须小于 KV 并行收益。
> +- workload class 取 `tiny/small/normal/large`；`tiny/small` 且接近 attainable 时输出 `workload_limited`（见 `workload-aware-diagnosis.md`）。
> ```

当前证据：

- `skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md:104`：`B_UB = Σ_j d_j*A_aj(U*s_j) + B_fixed + T_api ≤ B_available`。
- `skills/ascendc-aprof-parallel-planning/knowledge/families/matmul/templates/splitk.md:85`：Wpartial = Σt∈split S_t × AM_t × AN_t × sP
- `skills/npu-arch/SKILL.md:14`：从 `PlatformAscendC` 获取可见 AIC/AIV 和可用 UB/L1/L0/L2，记录每个值的来源。未知值为 null，不可用作分母或授权容量相关特化。ISA 特性还需匹配 SDK API 和编译选项；产品族不隐含固定核数、带宽或峰值 FLOPS。

## 37. [P1] Required Evidence 缺数据来源与证据等级

**结论：部分满足**。来源、原始 ref、单位、派生依赖及证据性质均有约束；不少 Symptom 的 raw 字段仍是来源族/通配符且 extractor 未实现，尚未逐项落成实际后端 CSV 字段映射。

原评论：yaoguangxiu，ID `193127005`。

> **问题 4（P1）：Required Evidence 只有名词，缺“数据来源”与“证据等级”两列**
>
> 诊断侧 6 张矩阵的每张 metric 表都有 `数据来源` + `证据` 两列（`OpBasicInfo.csv` / `PipeUtilization.csv` / `ResourceConflictRatio.csv` / `ArithmeticUtilization.csv` / TilingData / `/npu-arch`；证据分 直接 / 派生 / Trace·对比）。本文档 `:29-32` 只列名词，agent 不知道去哪取：
>
> - `blockDim` → `OpBasicInfo.csv: Block Dim`（直接）
> - `AIV/AIC 核数` → 只能来自 `/npu-arch` 或 `PlatformAscendC`（`ai-core-utilization-inject.md:15` 写明了，本文档没写）
> - `totalTasks`、`usedCoreNum`、`per-core work` → TilingData + shape 推算（派生）
> - `per-core time`、`tail/core imbalance` → `PipeUtilization.csv` 的 `ai*_time`（派生）
> - `attainable utilization` → 公式在 `workload-aware-diagnosis.md:25-35`，本文档未链接
>
> 缺证据等级的直接后果：无法区分“CSV 可直接拿到”与“需 trace / 多 shape 对比”，容易把 cannsim 派生值当直接证据——而 `optimization/SKILL.md:81` 明确规定 simulator 指标只是 proxy，不得当作真实 `Memory.csv` / `PipeUtilization.csv`。
>
> 建议改成表格：
>
> ```diff
> -- totalTasks、blockDim、usedCoreNum、AIV/AIC 核数、per-core work。
> -- active core count、per-core time、tail/core imbalance。
> -- workload model：tiny/small/large 与 attainable utilization。
> -- 算子族阶段模型：MatMul MN/K、FA S2/KV、Reduction R/A、Sort merge phases。
> +| Evidence | 数据来源 | 证据等级 |
> +| --- | --- | --- |
> +| `Block Dim`、`Task Duration` | `OpBasicInfo.csv` | 直接 |
> +| AIV/AIC 核数 | `/npu-arch` 或 `PlatformAscendC` | 直接 |
> +| totalTasks、usedCoreNum、per-core work | TilingData + shape | 派生 |
> +| active core count、per-core time、tail/core imbalance | `PipeUtilization.csv` 的 `ai*_time` | 派生 |
> +| workload class、attainable utilization | `workload-aware-diagnosis.md` 公式 | 派生 |
> +| 阶段模型（MatMul MN/K、FA S2/KV、Reduction R/A、Sort phases） | trace + 多 shape 对比 | Trace/对比 |
> ```

当前证据：

- `skills/ascendc-aprof-diagnosis/graph/symptoms/symptom.profile.tasks_below_available_cores.md:336`：## 人工证据要求
- `skills/ascendc-aprof-diagnosis/graph/symptoms/symptom.profile.memory_bandwidth_saturation.md:102`：    raw: 采用实际后端原单位；字段名为来源族，通配符和视图须映射实际版本字段

## 38. [P0] 缺前后检查、失败交接和固定 strategy_id

**结论：部分满足**。C2/C3 已集中要求静态/容量/构建/完整正确性，失败停止计时，优化角色有精度/runtime/crash 辅助技能；新版以 Action/recipe 身份替代旧 strategy_id。尚缺旧 ai_core_task_parallelism 的明确迁移映射与该族逐场景 pre/post/failure 列表。

原评论：yaoguangxiu，ID `193127012`。

> **问题 5（P0）：缺 `contracts.md` 强制要求的 `pre_patch_checks` / `post_patch_checks` / `failure_handoff` / `strategy_id`**
>
> `references/contracts.md:478` 明确：“每个 strategy 必须包含执行前后门禁：`required_evidence`、`expected_metric_delta`、`pre_patch_checks`、`post_patch_checks`、`failure_handoff`”。本文档只有 Required Evidence / Abort Conditions / Metric Delta 三段：
>
> - **无 pre/post patch checks**：改分核属于结构性改动，`optimization-candidate-design.md:76-77` 要求多 shape 验证（主 shape、tail shape、小 shape、边界对齐 shape）与阶段性语义验证，本文档没落成可执行检查项。
> - **Abort 只说“停”，不说“交给谁”**：`optimization-strategy-routing.md:28` 定义了 5 条 handoff（precision-debug / runtime-debug / crash-debug / ops-profiling / 记录 memory），本文档 0 处 handoff。
> - **缺“根因属于别族 → 转出”规则**：诊断侧 `ai-core-utilization-diagnosis-metrics.md:78`/`:79` 明确把“搬运瓶颈导致计算单元空等”转 data-movement 矩阵、“流水气泡导致利用率低”转 pipeline-parallel 矩阵，`:134` 还把 AIC/AIV 节拍问题转入 `pipeline_parallel`/`api_algorithm`。本文档没有对应转出规则，会把 data_movement / pipeline_parallel 根因的低利用率强行按增核处理。
> - **`strategy_id` 全文 0 处**：本族规范 id 是 `ai_core_task_parallelism`（`contracts.md:490`），而 `optimization_memory.jsonl` 的记录维度必须含 `strategy_id`（`contracts.md:595`）→ id 由 agent 自造会导致经验库碎片化、历史结果无法检索复用。
>
> 建议在 Abort Conditions 之后补：
>
> ```diff
> +## Gate Checks
> +
> +- `pre_patch_checks`：AIV/AIC 分母已确认；`totalTasks`/`blockDim`/per-core work 有来源；split 后 workspace 容量公式成立；语义不变量（输出顺序、tail、动态 shape）已列出。
> +- `post_patch_checks`：build → accuracy → 稳定 repeated profile；主/tail/小/边界对齐 4 类 shape 均验证；split-K/split-KV/Group Reduce 的 combine 结果与 baseline 逐元素比对。
> +
> +## Failure Handoff
> +
> +- 精度失败 → `ascendc-precision-debug`；runtime 非零/错误码 → `ascendc-runtime-debug`；超时/挂死/AIC error → `ascendc-crash-debug`；profile 产物缺失 → `ops-profiling`；metric 回退 → 记入 memory 并进入下一个 candidate。
> +- 根因实为 MTE 主导或流水气泡时，转出到 `data-movement-optimization-strategies.md` / `pipeline-parallel-optimization-strategies.md`，不要在本族继续增核。
> +
> +本族 `strategy_id` 固定为 `ai_core_task_parallelism`。
> ```

当前证据：

- `workflows/contracts/candidate.md:30`：只有审查、构建和完整正确性均通过且计时必需资料齐备，才 completed 并建议 `timing_candidate`。正确性证据使用 [统一计时协议](../../skills/ascendc-aprof-profiling/references/unified-timing.md) 的支持格式。
- `workflows/agents/optimization.md:34`：- [ascendc-precision-debug](../../skills/ascendc-precision-debug/SKILL.md)：C3；完整正确性失败。
- `workflows/contracts/candidate.md:60`：绑定 C2 的共同 P 计划，以及每个 Action instance ID/hash、目标、参数与计划身份，记录实际源码、dispatch 及变更。逐成员 O_KEEP 仅不追加对应局部优化；P_CHANGE 时仍须实现新计划。P_KEEP 且所有成员 O_KEEP 才为 NOOP，空命中或缺证据不能转换为 KEEP。实际组合在选择后形成结果快照，不是C1/C2预先白名单。

## 39. [P1] Metric Delta 缺可判定阈值、容忍度和具体字段

**结论：部分满足**。统一计时已量化为逐 case 中位数、等权 GM≥1.03、任一 case 回归≤3%，并区分稳定性。仍缺旧 AI Core 族各预测 metric 的具体量化目标/字段映射，统一性能门槛不等价于全部 expected_metric_delta。

原评论：yaoguangxiu，ID `193127016`。

> **问题 6（P1）：Metric Delta 4 条全部不可判定，无法落 `expected_metric_delta`**
>
> `:44-47` 的“上升”“下降”“不明显回退”既无目标幅度、无回归容忍度，也无对应 CSV 字段名。`optimization-candidate-design.md:34` 要求 `metric_delta` 写清“期望哪些 metric 怎么动，什么幅度算有效”，并把“性能会提升”列为**不合格示例**——本段 4 条基本停留在该级别。
>
> 诊断侧同一批指标是有字段名和阈值的：核间不均衡 `(max(ai*_time)-min(ai*_time))/max(ai*_time)`，>10% 需关注、>30% 严重（`ai-core-utilization-diagnosis-metrics.md:34`）；核利用率 `Block Dim / GetCoreNumAiv()`（`:24-25`）；空闲核比例（`:27`）；头开销占比（`:57`）。
>
> 建议：
>
> ```diff
> -- active core count 上升且 per-core work 不过小。
> -- per-core time 方差和 tail 拖尾下降。
> -- 大 shape duration 下降，小 shape 不明显回退。
> -- split/reduce 类候选的 workspace overhead 小于并行收益。
> +- `activeCores`（= `min(blockDim,totalTasks,availableCores)`）上升，且 `elements_per_core` 不低于增核前的 1/2。
> +- 核间耗时不均衡 `(max(ai*_time)-min(ai*_time))/max(ai*_time)`（`PipeUtilization.csv`）从 >10% 降到 <=10%。
> +- 主 shape `Task Duration`（`OpBasicInfo.csv`）下降 >=5%；小 shape 回退 <=3%，超出记为 regression。
> +- split/reduce 类候选：新增 GM 写回 bytes（`Memory.csv`）+ combine 阶段耗时 < 并行节省的 duration。
> +- 过开核类候选：头开销占比 `(Task Duration - max(ai*_time))/Task Duration` 下降，空闲核比例降到 0。
> ```

当前证据：

- `skills/ascendc-aprof-profiling/references/median-stability-v2.md:33`：工程要求保持：逐case中位数比的等权GM≥1.03，任一case回归≤3%，正确性及完整调用不放宽。HAP目标、Action—P/O正式交接分别报告；计时协议不自动授予其通过。
- `workflows/references/action-selection.md:46`：每个拟采用方法及完整方案给出可检验预测：准备减少什么工作、增加什么代价、影响哪些 case，以及什么观察会削弱它。例如逻辑地址运算从每输出多次除模变为按连续段一次解码，是源码预测；最终编译指令数和 Task 时间仍待验证。不能直接从逻辑操作数推出固定加速比。

## 40. [P2] _en 文件与中文逐字相同，英文入口链接也不正确

**结论：满足**。未继续提供字节相同的假 _en 文档。当前中文入口引用中文正文，按评审建议采用只维护中文这一选项。

原评论：yaoguangxiu，ID `193127020`。

> **问题 7（P2）：`_en` 是假翻译——与中文版 byte-identical、正文仍是中文；且 `SKILL_en.md` 的链接指向中文文件名**
>
> 本文件 `:3-4` 正文为“本文用于 `problem_family=ai_core_utilization` 的 candidate 设计…”，与 `ai-core-utilization-optimization-strategies.md` 完全相同。
>
> 验证（PR head `5d37afb`）：
>
> ```bash
> cd skills/tool-ops-optimize/aprof/optimization/references
> for f in *.md; do case "$f" in *_en.md) ;; *) diff -q "$f" "${f%.md}_en.md" >/dev/null && echo "IDENTICAL: $f";; esac; done
> # → 13 对全部 IDENTICAL
> diff -q ../SKILL.md ../SKILL_en.md; diff -q ../AGENTS.md ../AGENTS_en.md   # → 同样 identical
> ```
>
> 即“中英文各一份”只在文件名上成立、内容上没有英文。而且 `optimization/SKILL_en.md:60` 链接的是 `references/ai-core-utilization-optimization-strategies.md`（中文文件名）而非 `_en` 版本 → 即使将来补了翻译，英文链路也指不到英文文件。
>
> 建议二选一：
> 1. 真正翻译 `_en` 内容，并把 `SKILL_en.md` / `AGENTS_en.md` 内的 references 链接改为对应 `_en.md`；或
> 2. 若本轮不翻译，就不要生成同名 `_en` 空壳，避免“双语各一份”门禁被形式化通过。
>
> 同时建议 check_pr 增加一条：`*_en.md` 不得与其对应中文文件 byte-identical，且 `_en` 正文不得包含中文字符。

当前证据：

- `IMPORT.md:12`：不声明已完成 NPU 功能或硬件性能收益验收。中文文档不生成英文副本。
