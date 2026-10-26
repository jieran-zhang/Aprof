# 无工具执行代价开发验收 A/B

正式协议v2完成24/24独立真实请求：六组场景×A/B×两次。冻结事实标准下，**A=96/96，B=96/96**；没有观察到这些来源事实与成本判断维度的准确率提升。观察到的变化是注册意图/方法覆盖：B能具体承载派生几何复用，并将静态buffer/event管理纳入有成本的竞争比较。没有硬件执行或真实性能收益结论。

评分与意图覆盖分开。A正确分析但只能提出未注册缺口仍获事实分；B报出新Action名字不加分，必须给适用范围、工作变化、新增代价和共同计划。本轮所有正式答案均未虚构已编译、已通过正确性或已测加速。满分仅表示四项冻结标准被满足，不等于所有候选同样优良、已经可部署，或所有工程细节均被证明。

## 设计、隔离与证据

先从原始case-08/case-12及研究候选源码独立确定事实，再冻结[FACTS锁](FACTS-LOCK.json)；输入没有旧诊断报告、标准答案、评分或预选Problem/Action。六组源码题及每组两个事实变化小例保留原定位，实际全文在每个prompt/request中。第六题是明确标注的合成原始谱系、正确性结果和计时窗口，不是硬件报告。

A冻结包为before，B为after-evaluation；[A协议](PROTOCOL-A.json)、[B协议](PROTOCOL-B.json)列正文及输入hash。两版题目和源码前缀逐项相同，见[输入一致性](INPUT-PARITY.json)。按相同目录策略预展开全部Problem/Action、O分支及相关P家族，A127文档、B131文档；重复来源frontmatter统一压缩，完整正文及必要实施条件保留。B新增正文自然纳入，不反向塞给A。

所有正式请求同gpt-6.1-sol、reasoning=high、max_output_tokens=20000、tools=[]、tool_choice=none、store=false，无previous_response_id。24个provider终态均completed、incomplete_details=null，请求/响应双向工具禁用、输出类型仅reasoning/message、零工具调用，见[逐次审计](REQUEST-AUDIT.json)。真实request、终态response、SSE、正文和RUN全部保留；没有认证文件、凭据或HTTP headers。完成后按固定规则检查，首次均成功，因此未追加基础设施重试。

人工对照源码和原四项0/1/2标准语义复核，不用关键词/正则过关，也不强制子例不同Action。[逐次评分](grades.json)记录具体事实、所选Action、采用正文和意图覆盖；[评分锁](GRADES-LOCK.json)绑定24正文与审计、协议hash。该评测衡量显式预展开材料中的无工具信息使用和选择，**不评价按需retrieval质量**。

## 独立复核与勘误（分数不变）

[独立语义复核](behavior-review.md)（[JSON](behavior-review.json)）已覆盖24项，维持全部分数及A/B各96/96。原grades、GRADES-LOCK、FACTS和原始答案保持不变；[勘误说明](ERRATA.md)及[结构化勘误](ERRATA.json)补正两处注释：s5-A-1实际主选96KiB搬运合批、80KiB输入前瞻为替代；s6-A-2实际属于batch_writeback。该更正不改变逐组结果或意图覆盖结论。

复核同时澄清：s4不要求唯一64B记录且不能偷换原乘法结合；s1不强制会改变数值路径的缩窄检测；s5新增静态管理方法覆盖不计事实分。原GROUP-SUMMARY已准确表达相关选择，保持不变。

## 六组结果

| 场景 | A事实分 | B事实分 | 已核对的事实与选择 |
|---|---:|---:|---|
| 值域/整域触发 | 16/16 | 16/16 | 两版均识别未采样极值仍使整通道全部输出走软件FMA；保持16384次软件FMA及数值边界。 |
| 正确性修复改变工作量 | 16/16 | 16/16 | 两版均识别[3,1]广播被错误当尾向量、12个越界读取位置，修复后重新核算合法工作，补通用fallback。 |
| API/pack/复用竞争 | 16/16 | 16/16 | 两版均核算全输入pack约25.04MB逻辑读写；S=8优先按需读取，S=32768保留paired通路并删输出/几何中转。 |
| 派生结果复用与重算 | 16/16 | 16/16 | 两版均识别C=1无通道复用、C=128可消除重复几何；均拒绝预乘3D权重偷换原左结合运算。 |
| Maximum管理/cache/共同计划 | 16/16 | 16/16 | 两版均区分已向量化Max、必要12MiB请求和管理/发射，按输出后继消费区别cache，并重建超出p_same的计划。 |
| 无效历史/换父本/改名 | 16/16 | 16/16 | 两版均拒绝漏写实现和enqueue短窗口收益，选择L0/Pine；各自改名后保持相同事实、成本与选择。 |

意图与方法覆盖的具体变化：

- **值域/整域触发**：两版都选择八邻居暂存/合批等合法局部方案，无新增意图名称奖励。 关键正文：`planning.indexing.coordinate_neighborhood`、`implementation.vector-api.batch`、`implementation.precision-boundaries.numeric`。
- **正确性修复改变工作量**：均用既有restructure_broadcast；B一次选每元素对齐槽，明确30次Max与槽膨胀成本，未因API少宣称加速。 关键正文：`planning.elementwise.broadcast`、`implementation.memory-transfer.strided-pad`、`implementation.memory-transfer.input-tile-residency`。
- **API/pack/复用竞争**：选择细节不同但均比较完整准备、descriptor/Gather、布局、容量和同步；未重复认领既有cp通道合批。 关键正文：`planning.layout.transpose`、`planning.indexing.coordinate_neighborhood`、`implementation.memory-transfer.strided-pad`、`implementation.precision-boundaries.numeric`。
- **派生结果复用与重算**：A两次正确指出缺注册派生复用意图，给条件提案；B两次以reuse_derived_results和derived-results形成具体生产/消费/生命周期计划。A缺口不记事实错误。 关键正文：`planning.indexing.coordinate_neighborhood`、`implementation.buffer-lifetime.derived-results`、`implementation.buffer-lifetime.reuse`、`implementation.precision-boundaries.numeric`。
- **Maximum管理/cache/共同计划**：A未独立比较新静态buffer/event方法；B两次将其作为有事件/排空成本的备选，但主选分别为cache试验和搬运合批。没有为采用新Action强行改选。 关键正文：`planning.elementwise.continuous`、`implementation.memory-transfer.cache-hint`、`implementation.pipeline-sync.pipeline`、`implementation.pipeline-sync.vector-static-lease`。
- **无效历史/换父本/改名**：A主选控制外提/批量输出并记录派生意图缺口；B两次主选Ct=2派生索引复用，具体比较复用倍数、任务数、保护与原值缓存/重算。 关键正文：`optimization-history.md`、`planning.indexing.coordinate_neighborhood`、`implementation.buffer-lifetime.derived-results`、`implementation.scalar-control.hot_loop_address`。

派生记录的表示差异有数值原因：原Scalar路径每项为`((x*wx)*wy)*wz`，不能无证明改成先预乘八个3D权重。模型分别用轴系数+偏移、低界坐标或单点私有状态，实际记录为48/56/72B等；按真实表示计容量与消费，不强套一个64B答案。它们仍保留每通道输入读取、乘法结合与k顺序。极大有限grid可能使原unnormalize溢出或float→int64越界，两版均如实保留原契约缺口，没有用优化偷偷改成新反射语义。

## 阅读与输出成本

下表output已包含reasoning，二者不能再相加。input包括cache token；缓存另列。wall为各请求等待时长之和，存在并发且缓存命中不同，不能作为B更快或技能更省时的因果证据。

| 版本 | 正式有效请求 | input tokens | output tokens | 其中reasoning | cached input | wall累计秒 |
|---|---:|---:|---:|---:|---:|---:|
| A | 12 | 2,798,104 | 126,742 | 49,334 | 230,912 | 3683.764 |
| B | 12 | 2,893,672 | 121,519 | 42,604 | 0 | 3263.260 |

B正式输入比A多95,568 tokens（3.42%），每题同样多7,964 tokens；包长不计入得分。A最大实际input=238,897，B=246,861；B最大输入加20k预算为266,861，小于本次使用的272k检查界。见[精确预算核对](B-BUDGET-CHECK.json)、[成本JSON](COSTS.json)和逐次表。

### 失败的v1 preflight单列

最初同输入/模型/high、12k输出预算暴露截断瓶颈。协调者停止未发请求，保留在途终态，再统一改为20k并将两版全部24项重新请求；没有只保留对某版有利的结果，也没有按分数择优。A新旧prompt/doc hash逐项相同。原3份暂存评分已撤回，v1所有答案不进入正式A/B。详见[V2修订](V2-AMENDMENT.json)及[完整协议](PROTOCOL.md)。

v1准备12项、实际发出9项：5 completed、4 max_output_tokens截断、3未发出取消。额外input=2,104,067、output=97,178（其中reasoning=41,741），wall累计2955.090秒。此成本不混进正式版间比较，全部原始证据在[preflight成本记录](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/preflight-v1/COSTS-FINAL.json)及相邻runs。v2确有超过12k且completed的输出，统一提高预算解除了已观察到的基础设施瓶颈。

## 24次正式结果与原始正文

| 请求 | 分数 | input | output（reasoning） | cached | wall秒 | 原始答案 |
|---|---:|---:|---:|---:|---:|---|
| s1-value-domain-A-1-v2 | 8/8 | 235,320 | 9,035（3,298） | 0 | 282.238 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s1-value-domain-A-1-v2/answer.md) |
| s1-value-domain-A-2-v2 | 8/8 | 235,320 | 8,336（3,088） | 0 | 257.980 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s1-value-domain-A-2-v2/answer.md) |
| s2-correctness-work-A-1-v2 | 8/8 | 231,046 | 10,554（3,624） | 0 | 296.731 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s2-correctness-work-A-1-v2/answer.md) |
| s2-correctness-work-A-2-v2 | 8/8 | 231,046 | 13,383（7,001） | 0 | 394.665 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s2-correctness-work-A-2-v2/answer.md) |
| s3-pack-total-cost-A-1-v2 | 8/8 | 238,897 | 9,481（3,106） | 0 | 279.153 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s3-pack-total-cost-A-1-v2/answer.md) |
| s3-pack-total-cost-A-2-v2 | 8/8 | 238,897 | 11,697（4,660） | 0 | 338.994 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s3-pack-total-cost-A-2-v2/answer.md) |
| s4-derived-reuse-A-1-v2 | 8/8 | 231,220 | 10,298（3,624） | 0 | 320.533 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s4-derived-reuse-A-1-v2/answer.md) |
| s4-derived-reuse-A-2-v2 | 8/8 | 231,220 | 10,807（3,624） | 0 | 327.519 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s4-derived-reuse-A-2-v2/answer.md) |
| s5-maximum-plan-cache-A-1-v2 | 8/8 | 231,101 | 15,013（8,740） | 0 | 441.512 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s5-maximum-plan-cache-A-1-v2/answer.md) |
| s5-maximum-plan-cache-A-2-v2 | 8/8 | 231,101 | 9,393（3,452） | 230,912 | 288.717 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s5-maximum-plan-cache-A-2-v2/answer.md) |
| s6-history-parent-rename-A-1-v2 | 8/8 | 231,468 | 9,100（2,260） | 0 | 234.263 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s6-history-parent-rename-A-1-v2/answer.md) |
| s6-history-parent-rename-A-2-v2 | 8/8 | 231,468 | 9,645（2,857） | 0 | 221.459 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s6-history-parent-rename-A-2-v2/answer.md) |
| s1-value-domain-B-1-v2 | 8/8 | 243,284 | 9,903（3,624） | 0 | 260.194 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s1-value-domain-B-1-v2/answer.md) |
| s1-value-domain-B-2-v2 | 8/8 | 243,284 | 8,573（2,588） | 0 | 257.886 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s1-value-domain-B-2-v2/answer.md) |
| s2-correctness-work-B-1-v2 | 8/8 | 239,010 | 11,459（4,660） | 0 | 256.029 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s2-correctness-work-B-1-v2/answer.md) |
| s2-correctness-work-B-2-v2 | 8/8 | 239,010 | 10,613（4,086） | 0 | 306.791 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s2-correctness-work-B-2-v2/answer.md) |
| s3-pack-total-cost-B-1-v2 | 8/8 | 246,861 | 12,239（4,453） | 0 | 286.546 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s3-pack-total-cost-B-1-v2/answer.md) |
| s3-pack-total-cost-B-2-v2 | 8/8 | 246,861 | 9,859（3,003） | 0 | 288.941 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s3-pack-total-cost-B-2-v2/answer.md) |
| s4-derived-reuse-B-1-v2 | 8/8 | 239,184 | 11,598（4,660） | 0 | 307.889 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s4-derived-reuse-B-1-v2/answer.md) |
| s4-derived-reuse-B-2-v2 | 8/8 | 239,184 | 8,066（1,552） | 0 | 232.049 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s4-derived-reuse-B-2-v2/answer.md) |
| s5-maximum-plan-cache-B-1-v2 | 8/8 | 239,065 | 9,519（3,624） | 0 | 273.965 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s5-maximum-plan-cache-B-1-v2/answer.md) |
| s5-maximum-plan-cache-B-2-v2 | 8/8 | 239,065 | 10,806（4,660） | 0 | 248.265 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s5-maximum-plan-cache-B-2-v2/answer.md) |
| s6-history-parent-rename-B-1-v2 | 8/8 | 239,432 | 9,175（2,588） | 0 | 265.119 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s6-history-parent-rename-B-1-v2/answer.md) |
| s6-history-parent-rename-B-2-v2 | 8/8 | 239,432 | 9,709（3,106） | 0 | 279.586 | [answer](../../../../../skill-libs/graph-base/1.3.1/sources/development/evaluation/formal/runs/s6-history-parent-rename-B-2-v2/answer.md) |

每个答案旁保存prompt、request、RUN、provider终态response与SSE；大JSON/JSONL已按整合规则gzip。包内实际相对路径、存储hash及解压前后hash/bytes见[实际存储清单](DELIVERY.json)；原239项基础清单与本次复核增量分别保留。机器可读逐次成本另见per-run.csv与REQUEST-AUDIT.json。原始模型Markdown在sources/development/evaluation中保留原样，不能当技能正文修写。

## 限制

六组自足源码题、每组两次，且A已经具备完整方案/历史等知识、正文预展开量很大；事实评分出现满分，不能据此推断总体任务成功率或所有方案质量相同。本次P材料仅预展开elementwise/indexing/layout，未覆盖新增`under-fusion.vector_producer_consumer`叶的自主选用；该叶的来源/技术/构建验证另见总报告，本次没有自主选用证据。新增意图覆盖是本轮观察，不等于编译可行、实际router检索改善或910C性能提升。没有编译、硬件校准、oracle执行、profile或设备计时；所有优化仍须真实工程的语义/存储/同步与完整计时验证。
