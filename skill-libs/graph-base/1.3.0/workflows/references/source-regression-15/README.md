# 1.3.0：Action 选择修复与 15 算子源码回归

本轮使用 15 个算子的原始 host、tiling、kernel、数学定义/原 oracle 以及各自全部 20 case，由三个独立 Agent 每组五项执行两轮源码分析。未提供期望 Problem、Action、recipe 或 Action 数量；没有运行算子、编译目标工程、采集性能、收集 memory 或训练。

**结果是可审阅的条件方案和知识采用记录，不是 30 个已实现候选。** C1、检索、Problem 展开、Action 选择记录和内部路由均有机器产物。尚未形成具备完整架构资源与实现绑定的正式 C2/C3；O 在此阶段为内部咨询。当前数据不能说明真实瓶颈、加速比或硬件正确性。

## 修复了什么

- 对全部 28 个 Action 的 115 条旧前提逐项审查：14 条转入性能假设，保留 101 条实施/结构条件，再补 2 条精确定义的合法性条件。原 true/false 要求和迁移理由完整保存；不是把旧 unknown 改成 true。
- 已有来源且与当前源码形态相符的方法，可支持优化试验。主瓶颈、当前占比、收益、是否被编译器消除等未知，不再默认要求先有 PMU 或严格实验才允许提出变换。地址、依赖、数值、API 与容量的真实缺项仍须在实施前闭合。
- `aprof.action-decision/v1` 保存主机会、最强替代、成本/适用 case、预测、补证据、知识正文采用和 R2 反馈。找到一个 ready Action 或修改容易证明等价，都不能单独作为停止比较的理由。
- 新增 D5 的 C1 sidecar 校验：区分结构判断、性能假设和本轮试验选择。源事实/性能预测类型、实例/hash、条件去向和前轮身份分别检查。不自动打分，不强制换 Action。
- 目标平台与实测设备能力拆开。任务指定 910C/A3，并有包内映射依据时，可以检索 dav-2201 文档；实际核数、可用 UB、安装 SDK 的能力另行核验。无设备探测不意味着目标型号未知。
- R2 逐项评价前轮预测。未测性能保持 `not_tested`；新源码/整数分析可以支持或削弱静态预测。有独立依据且任务允许时，也可选择新试验，不要求必须先测完前轮。不能伪称前轮已晋升、实施或获得收益。

当前身份为 diagnosis **v0005**、P **v0002**、O **v0005**、routing **v0004**、runtime **0.6.0**，包仍是未封版 **1.3.0**。旧 schema、D4/O4 及更早快照、`knowledge.py` 保留字节；没有切换默认版本。新 family/branch 不自动新增 Action；新意图通过提案、明确条件策略和来源审查登记，无需改 Action 枚举。

实施标准见[Action 选择与反馈](../action-selection.md)，逐条迁移见[条件审查](../action-condition-review.md)。

## 怎样执行本次回归

执行 Agent 只获得各自原始源码与 20 case、任务目标、技能包正常入口和产物格式。其上下文不包含历史优化结果、历史 patch、预期答案或其他组判断；明确禁止读取测试 fixtures 和维护验收报告获得答案。全部源码来源及 hash 在 [provenance](provenance/SOURCE-FILES.json)。

每项从源码成本概览出发，读取完整 28 项 Problem 轻目录，再自行展开正文、比较机制与干预。后续实际调用 P/O 内部 router，区分全树咨询、Action 绑定候选、条件采用和正式交接。`knowledge_use` 记录正文路径/hash/行号及具体判断变化；不能仅靠“读过路径”证明采用知识。

R1 是源码支持的首个条件方案。R2 保留原父本，补充地址、容量、生命周期或边界分析，不假设 R1 已实施。每项全部 20 case 进入分析与后继验证范围；分组决定快路径/fallback，不删原 case。合计为 300 个原始 case 元数据，**不是 600 次硬件执行或正确性测试**。

主 Agent 的中途澄清只涉及目标平台输入语义、真实正文定位、路由阶段和证据准确性，没有指定某个 Problem/Action 或要求动作多样性。独立复核后修正了性能预测类型校验及三项 C 组证据表述；这些审阅修正保留在检查记录中。最后的离线检查发现回放索引误将 C 组两轮指向历史共用回执，已改为各轮真实 Context 对应的现有回执；10 组重新 retrieve/expand 的结果与原 R1/R2 文件逐字节一致，没有因此改写推理或选择。

## 15 项实际采用的知识与后继判断

表中 P/O 为实际阅读并用于条件方案的文档简称。点击算子名查看逐项分析；[30 份选择记录索引](results.json)集中列出所比较的 Problem、Action、正文采用与 decision/C1 引用。完整路径、精确版本/hash、行号、其他候选及拒绝理由保存在各任务的 decision、reading-record 和路由文件中；下表不把路由命中的所有叶当作已阅读或已选中。

| 算子 | 主要机制假设 → Action | P / O 正文及其作用 | R2 的实质新增信息 |
| --- | --- | --- | --- |
| [Exp](cases/case-01/R2-analysis.md) | 流水串行化 → `software_pipeline_stages` | P continuous 保持输出独占；O pipeline 区分物理槽与队列深度，numeric 保持原 Exp/乘加/Cast | 双输入/输出槽的三种 dtype 显式数据区均为 `16T`；T=4096 为 65536B，单 tile 保留原路径。 |
| [Mish](cases/case-02/R2-analysis.md) | 片上分配机会 → `reuse_disjoint_onchip_buffers` | P continuous；O reuse 按最后消费者复用，numeric 要求保留 ±0 等语义 | 仅 FP32 的 fi=in、fo=out；保留两次 +0。`12×3392+512=41216B` 与原显式预算相同，低精度保持原路径。 |
| [MaskedScale](cases/case-03/R2-analysis.md) | 片上分配机会 → `reuse_disjoint_onchip_buffers` | P continuous；O reuse/numeric；vector fallback 明确尚缺目标 API 依据 | of=xf 可减少 `4T`，T=4096 时为 16384B；保持先乘 mask 再乘 scale 及原 Cast，不以 mask=0 消掉特殊值运算。 |
| [SwiGLU](cases/case-04/R2-analysis.md) | 短段搬运发射放大 → `coalesce_contiguous_transfers` | P transpose 提供映射/owner 原则；O coalesce/numeric 约束 packed 读取与原数学链，vector fallback 保留 shuffle 缺项 | 对 S=1/7/50 等短段分组；S=1 代表 case 原逻辑 DMA 调用达 3000009 次（不计核切分）。验证 packed 索引恒等；数学整段 owner 不代替物理写边界。 |
| [AdamW](cases/case-05/R2-analysis.md) | 流水串行化 → `software_pipeline_stages` | P continuous；O pipeline/reuse/numeric | 四输入双槽、一输出槽的新系数为 FP32 `36T`、低精度 `38T`，另计 mask/保留区；不能直接将旧 ubFormer 配置翻倍。 |
| [Gather](cases/case-06/结果.md) | 地址解码成本 → `hoist_invariant_control` | P gather_output_owned 明确输出 owner；O hot-loop-address 指导 mixed-radix 递推 | 按非 gather 轴的真实 source stride 递推，保留 rank1、非法索引、越界零填充分支；物理写粒度另核验。 |
| [StridedSlice](cases/case-07/结果.md) | 非连续地址中的连续 run → `reorder_contiguous_access` | P transpose 只借用映射/所有权原则；O coalesce，补读 valid-length 限定有效尾长 | 11 case 可使用连续尾维 run，9 case fallback；run 与原 owner 求交，run=127 不被说成整输出连续，不引入无必要的转置。 |
| [GridSampler3D](cases/case-08/结果.md) | 重复坐标几何控制 → `hoist_invariant_control` | P gather_output_owned；O hot-loop-address/numeric | 奇数空间平面使跨 channel 的逻辑分组可能共享物理写块；削弱 R1 全覆盖预测，收窄到原 64B owner 内完整平面共享，头尾 fallback。这里 64B 来自原实现分区规则，不泛化为所有 API。 |
| [GELU](cases/case-09/结果.md) | mode 与资源配置不匹配 → `dispatch_by_workload` | P continuous；O dispatch/reuse/numeric | tanh 不使用 erfTmp/mask，可省 `20×1024+256=20736B` 显式分配；none 路径与 tanh 的 2^-23 RINT 保持，容量节约不等于已加速。 |
| [Sigmoid](cases/case-10/结果.md) | 流水串行化 → `software_pipeline_stages` | P continuous；O pipeline | 区分 num=2 物理槽与 depth=1；DeQue 后再预取，最多一个未消费项。T=4096 数据区 65536B，不把原注释 192KiB 当设备证明。 |
| [ForeachAddcdiv](cases/case-11/RESULT.zh.md) | 流水串行化 → `software_pipeline_stages` | P continuous；O pipeline，比较 scratch 复用替代 | 双槽 `8Us+16U·I16`，U=2048 为 65536B；host chunk 不等于每核一定有多 tile，实际核数影响重叠机会。 |
| [Maximum](cases/case-12/RESULT.zh.md) | 广播地址/执行形态 → `restructure_broadcast` | P broadcast；O coalesce/batch/input-tile-residency | 区分广播连续内轴、same-shape 与 int64 路径。case18 的 16386B 源行不是 32B 倍数；UB padding 不能代替源步长证明。保留比较/NaN/±0 约束。 |
| [RoPE](cases/case-13/RESULT.zh.md) | 数据运算标量化 → `vectorize_scalar_loop` | P continuous；O batch/pipeline，input-tile-residency 限定 trig 复用域 | 验证 half-mode partner 和 row 范围；不混入 interleaved，不跨 seq 盲目复用。地址/表达式映射已知，完整精度等价仍待目标 API/编译语义核验。 |
| [Transpose](cases/case-14/RESULT.zh.md) | 逐元素非连续访问 → `reorder_contiguous_access` | P transpose；O coalesce/batch/hot-loop-address | suffix 仅 case1/14，其余区分可合轴二维与 fallback；保持 int64/NaN 原始位。矩形逻辑无交不证明真实 DMA 写块独占，需按真实粒度 A 分配/裁切。 |
| [ResizeBilinear](cases/case-15/RESULT.zh.md) | 数据运算标量化 → `vectorize_scalar_loop` | P gather_output_owned；O batch/hot-loop-address，input-tile-residency 比较读取复用 | 2倍下采样与8倍上采样的源覆盖不同；边界坐标重合只允许复用读取，不能擅删四项运算。完整 FP/half 特殊值等价仍需核验。 |

同一 Action 的保留有新信息依据，没有设置换动作配额。Gather/GridSampler 仍选择标量控制类，是因为原始源码中存在具体重复解码/几何工作；没有因“最容易证明等价”统一选择字段缓存。

## 如何理解这些结果

本轮证据支持“知识参与了方案、参数、代价和边界判断”：有对应源码、可定位正文、阅读前后说明和独立复核。例如流水文档使物理槽与队列深度分开，生命周期文档形成具体字节公式，数值边界文档阻止删除 +0 或四项特殊值运算，规划文档促成物理 owner 的修正。

这不是严格的知识贡献消融实验，也没有证明模型今后不会再次集中选简单改动。正式 C2 选择、C3 实现、编译器实际指令、完整原 oracle、不同 case 的真实收益，以及实测反馈驱动的 R2 行为，仍应在后继硬件批次检查。本轮不把条件方案或引用次数当作这些证据。

仍需补强的知识主要是：

1. Gather/Slice 的目标 API 批量搬运、对齐/有效尾写和所有权实例；通用 layout/indexing 原则不能替代全部算子专门模板。
2. SwiGLU 短段 packed shuffle、RoPE 两种布局、Resize/GridSampler 插值的目标 Vector API 与精度边界实例；目前可提出具体方案，尚不能仅凭通用 batch recipe 承诺全部 dtype 的实现。
3. 安装 SDK 的 alias、队列/事件、物理搬出粒度与资源能力应以精确版本解析；包内平台映射提供适用域，不等于当前设备/SDK 全部能力。
4. 编译器是否已消除字段/地址运算、加槽是否真正重叠、复用是否位于关键路径等，需要编译/硬件反馈。本轮将其保留为预测，未再用作采用知识的统一前置否决。
5. 这 15 项主要覆盖 Vector/搬运/布局场景，不覆盖 Cube、Attention、MoE 与跨 kernel 融合的实际选择行为。

## 检查结果

CPU contract 与兼容检查共覆盖 201 项，分批通过；最初的旧版本 fixture 失败与随后修复回执一并保留，没有宣称一次全套运行通过。30 份决策/C1 与按轮次 Context 身份检查通过；独立复核发现的问题已闭合。独立目录中通过完整包未封版校验，并回放 Exp、GridSampler3D、Transpose 共 6 轮；网络、原工作树及临时来源访问由审计钩子限制，具体范围与局限见[离线报告](checks/offline/REPORT.md)。284 个受保护旧文件、1.2.0 与默认版本保持不变。详细检查记录见[checks.json](checks.json)。

## 自包含回放

全部当前任务输入、源码、判断、引用与回执均在 [cases](cases)。[inventory.json](inventory.json) 固定每个文件的 hash；[检查结果](checks.json) 区分 CPU contract、独立复核及隔离目录检查。原回执中的 `/tmp` 或工作树路径仅是历史命令/来源定位，当前重放不使用它们。

```bash
APROF_PACKAGE=/absolute/graph-base/1.3.0
python3 "$APROF_PACKAGE/tools/replay_source_regression.py" --root "$APROF_PACKAGE"
# 也可按需重放一项；不会运行原算子或重新生成 Agent 判断。
python3 "$APROF_PACKAGE/tools/replay_source_regression.py" --root "$APROF_PACKAGE" --case case-08
```

该命令校验任务文件、C1/decision、完整目录与正文展开身份，并按实际实例回放 P 候选和 O 内部咨询；不将空候选/fallback 转为 KEEP，不伪造 confirmed_plan。自然语言是否合理仍依赖审阅。
