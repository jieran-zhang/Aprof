# 执行事实、成本比较和完整交接：原因台账

本台账审查已结束实验，不进行新硬件实验，不更改历史准入或结果。引用文件均在本目录的 `sources/development`，原路径与字节 hash 见 [EVIDENCE.json](EVIDENCE.json)。实验材料属于开发审查依据，不替代五仓库固定修订的知识来源。以下时间点类别不可混用。

## 1．值域和整域触发未进入最终选择

**选择前已有。** 原始 workload 含大有限值范围；R14 C1 选择 small AoS/归约及 Boolean 向量化，C2 定义任一有限输入 `abs(x)>=32` 时整个 NC plane 改走软件 FMA。见 [原 C1](sources/development/grid/reports/stages/C1-R14.md)、[原 C2](sources/development/grid/reports/stages/C2-R14-plan.md)。

**修复新增。** 最终 Cast 的严格误差边界使正常路径也增加扫描、压缩和逐点修正；原 `196T→132T` 模型只描述主 Mul/归约链，不能代表完整候选。原补充已经指出这一限制，却没有把新增路径绑定到重新比较的选择。见 [最终数值补充](sources/development/grid/reports/stages/C2-R14-final-rounding-addendum.md)。

**选择后审查。** 对原始 case 11 的相同输入字节回读，66/66 个 NC plane 触发整域软件路径；2,371,842 个输出对应 18,974,736 次源码整数 FMA 求值。此精确统计形成于选择后，不能回填 C1。但原范围和源码足以在选择时发现慢路径可能广泛触发，不能默认罕见。见 [覆盖复核](sources/development/review/grid-R14-case11-existing-input-guard-frequency-review-v1.json)。

**断点。** 理解偏重 shape/dtype 与内存合法性；数据相关触发粒度没有连接实际工作。修复被视为正确性闭合，缺少关键成本改变时返回比较的行为。文档有“必须计入”的要求，没有完成代入及重选。

**修复归属。** 工程阅读方法解释数据相关控制；Action 选择规则约束触发粒度和保护代价；C3 对影响关键预测的修复回传 C1。既不预言硬件慢多少，也不由安全通过推出值得优先实施。

## 2．准备工作被记录，却未与潜在节省比较

**选择前已有。** R15 源码准备模型列明四域额外 Xp 写入/同时存活字节约 32～520 MB、必要邻域请求字节不变、内点 DMA 调用减少。完整方案仍有 pack/geometry/sample/compact。C1 引用父本 sample 阶段耗时，但未说明新增准备工作需要减少多少目标工作才能偿还。见 [原准备模型](sources/development/grid/artifacts/R15-preparation-zpair-costs-pending-R14.json)、[原 C1](sources/development/grid/reports/stages/C1-R15.md)、[原 C2](sources/development/grid/reports/stages/C2-R15-plan.md)。

**选择后新增。** 原输入的内点精确比例约为 100%/95.3263%/99.9641%/100%；这不支持“边界比例高”作为主要解释。真实 p 循环是 N×S，不能按 N×C×S 计算搬运 API。一次 API、block、字节是不同计数。见 [计数复核](sources/development/review/grid-R15-postselection-coverage-count-level-review-v1.json)。

**选择后测量观察。** 四个目标域整调用均有效回退；pack 阶段中位数增加约 411.530/149.382/747.092/945.650 us，sample 仅两个域下降。阶段中位数不能相加替代整调用中位数，也不是消融归因。见 [既有 Task 阶段复核](sources/development/review/grid-R15-existing-Task-stage-budget-review-v1.json)。

**断点。** “少 API、额外字节、收益未知”被并列陈述，却没有判断少掉哪种工作、新增工作怎样摊销、哪个条件支持优于低代价替代。未知收益成为空泛继续的理由。

**修复归属。** 统一比较计数层级及准备成本；已有同范围阶段耗时只约束可省空间，不假设阶段可全消除，不将字节直接除以峰值带宽生成收益。知识允许试验，但选择必须给出具体竞争条件。

## 3．局部适用没有形成完整正式交接

**运行时缺陷。** Maximum 首轮读取 case 身份可接受裸矩阵行，有效反馈却要求完整 `cases[{case_id,workload}]`。首轮和反馈的消费不一致导致后继链被阻断。见 [历史错误](sources/development/maximum/rounds/R2/contracts-04/decision-validation-blocked.json)。

**知识缺口与过窄解释并存。** 派生计算结果不属于原始输入复用；动态 buffer 管理简化也不能硬套控制外提。另一方面缓存 Action 的目标本为 GlobalTensor，不能只因 recipe 的示例是输入就把输出策略一律排除。补充知识必须遵守目标 SDK，`rwMode` 若为预留字段不能虚构单独读写控制。

**执行偏离。** Maximum R15 有 [文字完整方案](sources/development/maximum/rounds/R15/selected-plan.md)，但 [决策](sources/development/maximum/rounds/R15/contracts-02/action-decision-v3.json) 的 `schemes=[]`、所选身份为空；它保存为图外研究，不是完成的 v4 共同交接。Grid 的布局等局部合法路由同样没有授权全部派生/数值变换。旧 Problem→Action 边的性能条件不应靠伪造 profiling 填满，临时 Problem 已可复用注册 Action，无须补造边。

**修复归属。** 新任务首次实施前冻结完整 workload 映射；按版本保留历史原义。准确注册必要独立意图，接好已有文档；正式 C1→共同 P→成员 O→源码始终绑定同一非空方案身份。图外授权允许研究，但不能充当正式技能交接已通过的结论。

## 4．上下文和历史

R14 局部 Context 继承旧预算元数据；实际 C0/TASK 授权并未错，不能据此推断硬件越权或选择因果。见 [既有元数据复核](sources/development/review/grid-R14-R15-router-budget-metadata-review-v1.json)。新上下文由当前 C0、父本和适用证据构造；三部分历史保留影响选择的事实及重开条件，不重复包装全部旧记录。无效计时、静态反证、正确性失败分别处理。
