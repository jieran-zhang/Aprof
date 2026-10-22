# 独立行为评分复核（v2，24/24）

复核结论：**保留24项的 `[2,2,2,2]`（各8/8），未发现足以改变这些事实分的确定错误。**需要修正两处评分说明/分类，并澄清三处可能过强的事实标准。满分只表示这四个静态事实标准得到具体、正确的回答；不表示方案最快、实现正确或B优于A。

本报告与 `behavior-review.json` 为独立建议，不修改原 `grades.json` 或模型答案。

## 范围与身份

- 只用 `evaluation/inputs.json`、六份 `evaluation/sources/*.txt`、冻结 `FACTS.json`、24份v2 `answer.md`/`RUN.json`及`grades.json`。未读此前计划、旧实验报告、旧答案或包正文；先按组核来源/方案，再对照评分。未调用硬件、网络或新被测模型，未另行spawn agent。
- 六份source均匹配inputs中的SHA256；24份RUN均为completed/valid、`tools=[]`、`tool_choice=none`、`tool_calls=0`、attempts=1。这里只核元数据，未扩大到请求底层原文审计。
- 审阅grades SHA256：`ffddb6181dda2859197afdba5743c3eadeeb46dfcd3906a4d3ef2334a95616e8`。
- 收到的GRADES-LOCK文件hash为 `9f8bffeee638c761a2040adc021b5bac663912d1038c48da98ef99b364f130a5`，本地计算一致；仅计算lock文件hash，未借lock正文引入额外评价材料。
- 每项评分均按语义和具体成本论证判断；没有按Action名、正文长度、术语数量或包输入token数加分。

## 逐组来源核算

### s1：值域改变实际软件工作，但不能偷改数值路径

来源Weighted第464–476行在更换nc时全载4096元素通道，并以整个通道运行GridNeedsFma32。a不触发；b未被采样的末元素2^125仍触发全部2048输出，共16384次整数软件FMA；正向命中后负向检查短路。普通路径的分离Mul/Add和软件fused递推不是可互换的表达式。

四答案均抓住此差别，且明确几何已经按NS预计算，不重复认领消除C倍几何。原tile=1920、cb=16640B、显式177920B可复算；有效count≤256但原Gather每片15360槽。四方案压缩物理工作域并比较保留四平面的替代，均保留检测/特殊值/累加顺序。A2的整8平面Mul对短片增加dummy算术，答案明确给出2048J−16384和初始化费用；B两次仅完整片合批Mul，短片保留逐路有效count，不能因这类实现差异加减分。

FACTS第3条若读成“必须提出缩窄检测”则过强。仅把b改为检查Gather值会将外部要求的fused路径变为分离乘加，即使值小也可能舍入不同。四答案有理由拒绝这种变换，并完整比较合法外围工作减少，足以取得成本推理分。

### s2：先修正标准broadcast，再比较合法工作

两例half非同形均进入LastAxisBroadcast，total=30、blockNum=1、row=5。a的stride [0,0,1]与源码一致；b应为floor(l/5)%3，实际每行从B[0]搬5个half，真实B仅3项，六行共12个越界half位置。声明GlobalTensor长度5不会扩分配；前3个有效地址也不组成正确逐行标量广播。

四答案均拒绝把b当快速正确父本，分别核出a合法请求130B、b126B，且不将错误180B请求中的非法部分全部计作可删流量。a保留B、多行padded UB方案为416B、3次DMA、6次Max；b可合法选择axis1展开整模式/逐通道组，或B1的2016B元素槽、30次Max方案。B1未用新Broadcast可避免未闭合scratch，但它也明确16倍槽膨胀和低粒度比较，不能因DMA少就判更快。所有答案都给了真实stride解码、每输出两次2B搬入+一次2B搬出+count1 Vector Max的拟建通用fallback，并把它与原错误类区分。

API重载、Broadcast实际scratch/ND物理布局仍是条件；本复核只确认其条件被明确列出、未写成既成事实，不独立认证未读取包中的SDK正文。

### s3：完整输入转换和阶段交接决定收支

cp=64。全输入有效读8257536B；paired pack写/容量16777728B，包括补通道、z配对顶层零值及哨兵。几何64S，采样邻域2048S；最终输出252S；b的padded输出容量4032B不代表sample写4032B（有效仅2016B）。由源码Init可算pack p=224/147tile、174080B，sample batch=48/gTile64、163840B。a有683tile尾32，b仅1tile8点。

四答案均计入完整pack成本且解释I/S变化。A1/A2/B2在a保留paired pack并把几何/输出本地化，删除20709376B逻辑中间请求；B1只删Compact，删除16515072B，另保留几何是合理范围差异。b均取消全输入pack；保留GM几何的B1有效请求19264B，本地几何的其余三项18240B。它们都把每点1次packed API换成4次跨通道8B行搬运，区分API数/descriptor block数、32B UB行pitch、Gather/初始化/发布/容量等新增代价。B2尤明确保留整个8点raw的统一数值判断，避免按点改触发域。均保存现有预权重路径与k次序，未直接替换成舍入组织不同的原Scalar公式。

因此a/b选择不同有事实依据，但不要求所有答案在a选同一融合范围或同一个Action，也不由payload差直接推断时延。

### s4：派生记录可以有多种合法表示；64B不是标准答案

原FP32 Scalar的gridBase=(batch*S+p)*3与c无关；几何原构造CS次，C128为524288次，可在全通道同owner下减少至S=4096次；输入X/每输出24乘8加和最终写回仍保留。C1没有跨通道复用，四答案均选有成本账的连续输出暂存试验。

| 答案 | 具体派生状态 | 真实含义及新增成本 |
|---|---|---|
| A1 | 3个int64下界+6个float轴系数，48B/点 | 上界由+1恢复；St16为768B，表写48S/读48CS。不是8个预乘权重。 |
| A2 | 单点固定几何状态即产即用 | 未冒称零成本；保留private状态/spill，St16×128输出UB8192B、32768次64B输出DMA。 |
| B1 | 8个int32有效空间偏移/−1哨兵+6float轴系数，56B/点 | 合法偏移0..32767，先判合法才窄化；St16为896B，读56CS=29360128B UB payload。 |
| B2 | 6个int64上下坐标+6float轴系数，72B值载荷 | 固定标量，非实际寄存器/栈大小；无显式UB表，明确长存活、p-major跨平面局部性，并比较St16/GM表。 |

四项均明确保留 `((X*wx)*wy)*wz` 和原k=0..7累加，不以 `X*(wx*wy*wz)` 替代。保存6轴系数允许重用几何且保留原舍入；仅保存8个合成权重不能自动提供这个证明。A正确报告其输入版本的注册意图缺口，同时给出具体条件化提案；B有对应注册Action，但名称本身不加分。

**FACTS第2条需要澄清**：8uint32+8float=64B只是某布局示例，并非原Scalar路径默认合法的预计算记录；若要把它作为最终消费表示须另证舍入或保存足够原状态。48/56/72B及单点状态均应按实际布局与生命周期评。四答案还共同指出“grid有限”不足以保证Unnormalize不溢出或reflection int64转换安全，这是来源自身的数值合同缺口，不能硬要求它们证明未定义行为。它们没有据此假装已完成实现。

### s5：管理、必要数学、cache轨迹和计划范围分别核算

原float同形已Vector Max。每tile三条queue各Alloc/EnQue/DeQue/Free，共12个源码管理调用；3×4096×4=49152B；有效GM请求12MiB、数学N次元素Max。原queue负责编排四类ready/free完成边，有单槽不等于整个kernel完全串行。

四项均区分a仅D2H与b后继设备读，分别分析输入一次性流和输出cache，未统一关闭b的输出cache，也不将NORMAL当命中保证。A1/B2主方案是同owner合并两个4096搬运tile、Max仍两子片，容量98304B，调用3K→3M而必要字节及Max调用K不变；A2主方案是2+2+1输入前瞻、81920B，调用/字节不变、增加序言及排空；B1只输入DISABLE/输出NORMAL，新增初始化hint不删字节，不增加UB，比较以上竞争路线。

四者均拒绝由p_same原3槽合同直接授权5槽、更大tile或显式event，也未给broadcast/int64冒充完整验证。A两项未比较静态TBuf/event方法，B两项有比较但未选；应作为版本方法覆盖差异保留。若事实标准第3条被理解为每答必须命名新静态管理方法，会将方法可用性混入事实分。按完整合法方案的资源/生命周期/缓存比较解释，A两项2分有依据；不要将其写成A已经讨论该方法。

### s6：完整输出、完整计时窗口和改名不变性

L1步长2只写1024输出，未写位置保留0，reference1导致1024错；T1=0.4不能作正确收益。L2内容同L0而identity独立，T2=0.2只到enqueue不含同步，不能与T0=1.0完整窗口比较，更不能宣称5倍加速。来源允许选L0或内容等价L2作源父本；不能强制“最新标签必选”，也不能让L2自动成为接受的性能父本。

四答案均选L0/Pine、保留L2/Oak独立身份、拒绝L1/Fir收益和T2无效窗口；未来要求全输出oracle+统一完整完成窗。A1段首解码/地址递推把4E源码除模改4R，保留owner和数值；A2单槽U64批量输出保留所有2048采样，新增UB写/DMA/完成边；B两项Ct2/St16将全快路几何2048→1024、grid6144→3072float，X/Y不减、64task，并具体计保护失败的额外读/重算和访问顺序代价。它们在子例b逐一重新绑定Pine/Fir/Oak，而保持成本/方案一致。

## 24项逐项评分裁定与证据

下表四位分数按冻结FACTS顺序；每项均保留8/8。行定位用于定位已作的语义核查，不是关键词自动评分。

| run（均-v2） | 复核分数 | 关键证据/具体差别 |
|---|---|---|
| s1-value-domain-A-1 | 2/2/2/2 | 207行整通道未采样极值触发；315行42240B、scratch租约；动态R只Gather有效对齐域。 |
| s1-value-domain-A-2 | 2/2/2/2 | 208行软件16384FMA保留；177行dummy乘法、权重初始化计费；8邻居helper不改顺序。 |
| s1-value-domain-B-1 | 2/2/2/2 | 240行全plane触发；192行物理工作变化；短片不合批Mul、软件acc反馈减少。 |
| s1-value-domain-B-2 | 2/2/2/2 | 131行细算检测；214行软件触发/16384FMA；完整片Mul合批、原必要字节保留。 |
| s2-correctness-work-A-1 | 2/2/2/2 | 121行正确索引/12越界half；b一次[3,1]→[3,5]，192B+scratch；368行通用fallback。 |
| s2-correctness-work-A-2 | 2/2/2/2 | 161行映射错误；b按c分组，GM间隙20B、9DMA/3Broadcast/6Max；332行fallback。 |
| s2-correctness-work-B-1 | 2/2/2/2 | 218行2016B元素槽/30Max/63descriptor blocks；明确16倍膨胀及合法Broadcast替代，366行通用路径。 |
| s2-correctness-work-B-2 | 2/2/2/2 | 187行floor(l/5)%3与越界；一次MH模式、5DMA/1Broadcast/2Max，343行fallback。 |
| s3-pack-total-cost-A-1 | 2/2/2/2 | 64行完整阶段表；a融合删除20.709MB，175行b按需18240B且独立区112640B。 |
| s3-pack-total-cost-A-2 | 2/2/2/2 | 179行direct/单份pack竞争；236行b32Copy+32Gather，consumer按规范k同步修改。 |
| s3-pack-total-cost-B-1 | 2/2/2/2 | a只删Compact16.515MB；162行单份pack多32768API比较；237行b保留几何19264B。 |
| s3-pack-total-cost-B-2 | 2/2/2/2 | 159行单份pack8.389MB与发射交换；209行b统一8点raw保护，staging复用且新增代价齐。 |
| s4-derived-reuse-A-1 | 2/2/2/2 | 233行48B轴状态、48S写/48CS读，St16 768B；准确区分缺注册意图与事实分析。 |
| s4-derived-reuse-A-2 | 2/2/2/2 | 247行单点即用全部通道；8192B输出UB/32768短DMA，297行超大有限域策略。 |
| s4-derived-reuse-B-1 | 2/2/2/2 | 56B=8int32偏移+6float轴，258行St16 896B；先合法后窄化、不预乘3D权重。 |
| s4-derived-reuse-B-2 | 2/2/2/2 | 254行72B固定标量值载荷，338行空间owner映射；GM表38.044MB和局部性均比较。 |
| s5-maximum-plan-cache-A-1 | 2/2/2/2 | 124行合批调用/96KiB主方案，80KiB前瞻为替代；301行p_same不授权新租约。评分说明须改。 |
| s5-maximum-plan-cache-A-2 | 2/2/2/2 | 113行2+2+1/80KiB，309行ready/free闭环，depth1单待DeQue调度，cache按对象比较。 |
| s5-maximum-plan-cache-B-1 | 2/2/2/2 | 输入DISABLE/输出NORMAL，3C hint、12MiB不变；242行静态管理仅竞争，274行计划范围。 |
| s5-maximum-plan-cache-B-2 | 2/2/2/2 | 131行K次Max保留、96KiB合批；290行静态event成本；80KiB竞争及cache轨迹。 |
| s6-history-parent-rename-A-1 | 2/2/2/2 | 82行历史/父本；141行4R除模；343行改名绑定同方案/成本，未冒称派生复用已注册。 |
| s6-history-parent-rename-A-2 | 2/2/2/2 | 78行历史，U64写回含新增UB与完成边；306行改名同成本。intent分类须改为writeback。 |
| s6-history-parent-rename-B-1 | 2/2/2/2 | 88行历史，136行[-1,1]逐点组guard及fallback额外读；341行改名不变。 |
| s6-history-parent-rename-B-2 | 2/2/2/2 | 69行历史，150行有限位/转换安全guard，f=0读9216float；332行改名同Ct2成本。 |

## 建议修订，原文件未动

1. `s5-maximum-plan-cache-A-1-v2.criteria_review[2]`被复用了A2说明：它写“主选2+2+1输入前瞻…全部必要流量/调用不变”。实际A1主选8192搬运合批、98304B，输入前瞻81920B是替代；合批减少调用，必要payload和K次Max不变。应重写说明，分数不变。
2. `s6-history-parent-rename-A-2-v2.intent_coverage.kind`写“existing control intent selected”，但答案和selected_actions选择batch_writeback。应改为existing writeback intent selected；派生复用注册缺口单列，分数不变。
3. FACTS s4第2条加入“64B为布局假设，不能无证改变原乘法结合；接受按实际表示计费”。FACTS s1第3条接受保留数值语义的拒绝缩窄检测。FACTS s5第3条区分正确成本推理与静态管理方法覆盖。

## 对比较结论的约束

A和B本轮事实评分均为96/96，差值0。这个评分存在天花板；支持“双方都能识别这些事实与成本陷阱”，不能支持“B事实推理更强”或“B新Action带来更快代码”。s4及s6的B能将派生复用作为已注册候选，A明确报告意图缺口；s5的B讨论静态管理而A没有，这是可报告的能力/方法覆盖观察，不能用新名字替代方案质量证据。B在s5也没有选择静态管理为主方案。

每版本每组仅2次、题设合成/静态，不能推断真实硬件速度、最优选择、广泛稳定性或统计显著性。未执行SDK构建、oracle、硬件计时；具体API资格、编译后重排/CSE/spill和别名均依答案声明保持条件。没有检查未获准读取的完整Action/SDK包正文，因而不独立认证其注册与接口陈述，只核其没有越过这些条件宣称已完成。
