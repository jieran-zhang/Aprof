# 独立匿名行为审阅

评分在未读取 masking.json、原 runs 或历史评测结果的条件下完成；只读匿名 answer/source 与冻结 FACTS、ADDENDUM 及当前包内知识。逐字连续引文、原始源码定位和拟采用/参考/拒绝资料的完整提取见 grades.json；评分身份已写入 GRADES-LOCK.json，不随之后的历史定性检查改分。

## 结果

五维顺序：源码与硬件事实；完整方案与依赖；工作/覆盖/代价影响选择；P/O正文实质采用；边界/unknown/归因/外部轮次。0/1/2采用共同锚点。Action数量、方案大小、字数或是否换Action均不计分。adopted表示进入纸面计划，不表示已执行。

| 匿名回答 | 算子 | 纸面选择 | 五维 | 合计 |
| --- | --- | --- | --- | --- |
| answer-01c6ded3ab | grid_sampler_3d | 输出owner不变，Scalar生成坐标/样本，Vector按原八项顺序计算bilinear，nearest保留 | 2/2/2/2/2 | 10/10 |
| answer-3ac7de846c | maximum | 同形int8的6Cast+float Max改3Cast+half Max，完整int8域精确 | 2/2/2/2/2 | 10/10 |
| answer-3be217d2ac | transpose | 共同连续尾段批量DMA；其余置换保持Raw复制并用混合进位递推地址 | 2/2/2/2/2 | 10/10 |
| answer-77a9a43cb4 | maximum | 同形int8精确half Max链，保留owner/4096tile，广播为强替代 | 2/2/2/2/2 | 10/10 |
| answer-a3f44151bb | reduction_sum | 保留单核AR全载，基础ReduceSum仅作为有具体API缺项的强替代 | 2/2/2/2/2 | 10/10 |
| answer-a8d96b5afc | transpose | 双端连续轴矩形/条带任务，DMA+原始整数Scalar UB重排，通用回退 | 2/2/2/2/2 | 10/10 |
| answer-c4844129d1 | grid_sampler_3d | 原owner及几何/取数不变，bilinear算术批量Vector，T∈256/512/1024 | 2/2/2/2/2 | 10/10 |
| answer-f57f8ae4c2 | reduction_sum | 保留现有单核AR全载；基础ReduceSum、增核/流水均作具体成本比较 | 2/2/2/2/2 | 10/10 |

八答均到充分档，并非因重复相同Action或列出大量资料。Maximum两答都以完整int8域的精确half表示减少转换，保留必要GM字节；Grid两答都实质核算Vector前新增14路暂存与累加初始化，保留几何/随机取数残余；Transpose两答选择不同可解释路线，分别覆盖连续段+通用地址递推，或双端连续矩形+局部原始位重排；Sum两答均在具体代价比较后保留已有单核全载，零Action不扣分。

## 可核验的行为

### answer-01c6ded3ab — grid_sampler_3d

选择：输出owner不变，Scalar生成坐标/样本，Vector按原八项顺序计算bilinear，nearest保留。

- 源码与硬件事实（2）：正确区分FP16手工解码、Scalar主循环与末端Vector Cast；保留原乘法括号/八项顺序和14/6分域。 引文定位 `review/subjects/answer-01c6ded3ab/answer.md:31`。
- 完整方案及必要依赖（2）：一个实例覆盖Scalar producer、Vector consumer、有效写回和缓冲最后消费者；没有为API/文件增凑Action。 引文定位 `review/subjects/answer-01c6ded3ab/answer.md:217`。
- 工作/覆盖/代价影响选择（2）：对照24乘+8加的Scalar减少与16个FP32数组、staging/UB/发射新增代价；说明强替代与重开条件。 引文定位 `review/subjects/answer-01c6ded3ab/answer.md:135`。
- P/O正文实质采用（2）：P将G/B/H/F绑定实际采样语义，并明确Gather仅参考原则；O的count、Cast、尾块和别名约束进入方案。 引文定位 `review/subjects/answer-01c6ded3ab/answer.md:232`。
- 范围/unknown/归因/外部轮次（2）：三部分摘要明确一轮授权、R0唯一实际工程与未测；API/资源缺项为实施条件，性能缺测不否决比较。 引文定位 `review/subjects/answer-01c6ded3ab/answer.md:448`。

关键缺口：目标Mul/Add/Cast的浮点/精确alias、SDK与完整UB预留仍须闭合；回答明确conditional_plan，未假称已通过。；nearest、跨c几何重算、Scalar随机取数和输入扩位保留；没有将全正确性覆盖冒称全域优化。

### answer-3ac7de846c — maximum

选择：同形int8的6Cast+float Max改3Cast+half Max，完整int8域精确。

- 源码与硬件事实（2）：实际路径、int64同形Scalar例外、FP16专用广播边界和原oracle语义均准确。 引文定位 `review/subjects/answer-3ac7de846c/answer.md:67`。
- 完整方案及必要依赖（2）：单个coalesce_cast覆盖独立half临时区、三次转换、Max和读写完成边，未用不必要Action凑数。 引文定位 `review/subjects/answer-3ac7de846c/answer.md:229`。
- 工作/覆盖/代价影响选择（2）：6S到3S、17T到9T、3N GM字节不变；广播短行/API/特殊值的联合成本实际影响选择。 引文定位 `review/subjects/answer-3ac7de846c/answer.md:167`。
- P/O正文实质采用（2）：具体Cast值域、P连续owner、Broadcast对齐和Compare/Select的256B/8KiB约束改变方法及替代排序。 引文定位 `review/subjects/answer-3ac7de846c/answer.md:369`。
- 范围/unknown/归因/外部轮次（2）：区分完整20case回归与case6实际优化，未测SDK/capacity不造ready或KEEP，保留无硬件限制。 引文定位 `review/subjects/answer-3ac7de846c/answer.md:205`。

关键缺口：安装SDK的half Max/转换具体位置与同步、可用UB和隐含预留尚待核验；不是该纸面证明的事实错误。；一般FP16广播与浮点Scalar三元选择的既有API域问题单列；本轮只改同形int8，不夸大全域正确。

### answer-3be217d2ac — transpose

选择：共同连续尾段批量DMA；其余置换保持Raw复制并用混合进位递推地址。

- 源码与硬件事实（2）：恢复Raw位保持、输出flat所有权与每元素rank解码；case1/14共同连续尾轴和高rank合轴边界准确。 引文定位 `review/subjects/answer-3be217d2ac/answer.md:73`。
- 完整方案及必要依赖（2）：两Action有独立目标、互斥域，明确不重复计工作；A2递推不变量与A1边界完整。 引文定位 `review/subjects/answer-3be217d2ac/answer.md:193`。
- 工作/覆盖/代价影响选择（2）：保留2Ns逻辑GM字节、核算连续段数量/UB/同步/Scalar状态，明确非连续GM读取仍残余；比较矩形转置替代。 引文定位 `review/subjects/answer-3be217d2ac/answer.md:131`。
- P/O正文实质采用（2）：P按双端连续性收敛范围，O给出有效508B而非512B、地址递推、尾块及宽整数检查。 引文定位 `review/subjects/answer-3be217d2ac/answer.md:373`。
- 范围/unknown/归因/外部轮次（2）：条件计划未冒称API就绪或全域Vector转置；三部分摘要区分纸面与实际、允许整体联合评价而不作成员归因。 引文定位 `review/subjects/answer-3be217d2ac/answer.md:386`。

关键缺口：VECIN TBuf→GM DataCopyPad方向/位置/类型及非对齐写出契约、可用UB、最终递推地址尚待闭合；回答没有把这些缺项藏在ready里。；其余18case仍Scalar离散GM复制，矩形保位转置API路线待补；未宣称全部perm均变成DMA转置。

### answer-77a9a43cb4 — maximum

选择：同形int8精确half Max链，保留owner/4096tile，广播为强替代。

- 源码与硬件事实（2）：恢复实际int64和FP16广播例外、UB映射和单物理槽；区分源码API与已验证支持。 引文定位 `review/subjects/answer-77a9a43cb4/answer.md:75`。
- 完整方案及必要依赖（2）：单Action内完整处理转换、三个独立half区与最后消费者，不把减Cast等同新增流水/复用意图。 引文定位 `review/subjects/answer-77a9a43cb4/answer.md:294`。
- 工作/覆盖/代价影响选择（2）：比较134M int8域的3次Cast删除、32KiB空间节省与广播93,587,070轴处理/短行/API成本，条件改变会重排优先级。 引文定位 `review/subjects/answer-77a9a43cb4/answer.md:175`。
- P/O正文实质采用（2）：P连续/广播与O Cast/Compare/Select/数值/生命周期正文均对应具体判断和本次不采用的方法。 引文定位 `review/subjects/answer-77a9a43cb4/answer.md:353`。
- 范围/unknown/归因/外部轮次（2）：一轮范围、R0未验、完整int8域证明与全20case回归/残余明确；没有用未测否决方法或制造正式通过。 引文定位 `review/subjects/answer-77a9a43cb4/answer.md:370`。

关键缺口：SDK half Max/Cast支持和V内依赖、UB隐含预留与最终完整oracle待核验；条件方案范围准确。；通用half广播和浮点三元选择的既有问题未被int8优化掩盖。

### answer-a3f44151bb — reduction_sum

选择：保留单核AR全载，基础ReduceSum仅作为有具体API缺项的强替代。

- 源码与硬件事实（2）：准确恢复3×32 FP32、1block、按值tiling、独立scratch；特别识别5个padding为原oracle可见零值。 引文定位 `review/subjects/answer-a3f44151bb/answer.md:19`。
- 完整方案及必要依赖（2）：零Action有具体保留理由，不制造重复搬运/拆核/高阶API碎片化；C2/C3完整提取原结构。 引文定位 `review/subjects/answer-a3f44151bb/answer.md:155`。
- 工作/覆盖/代价影响选择（2）：比较一次Sum与三次基础ReduceSum、按行增核、partial写读24S字节和微小任务固定代价，未把调用名当指令数。 引文定位 `review/subjects/answer-a3f44151bb/answer.md:115`。
- P/O正文实质采用（2）：P FullLoad的AR/h=3、scratch与有效/物理长度，O生命周期/搬运/流水适用边界实际决定保留；基础ReduceSum四参数与结果安放缺口具体。 引文定位 `review/subjects/answer-a3f44151bb/answer.md:261`。
- 范围/unknown/归因/外部轮次（2）：摘要保留R0、未测/未构建、候选缺失与剩余机会；不把保留实现伪装为正式P_KEEP/NOOP。 引文定位 `review/subjects/answer-a3f44151bb/answer.md:210`。

关键缺口：保留R0不需强制新增候选。若重开ReduceSum，scratch、目的地址/打包和注册意图仍需明确；这些缺项阻止替代方案直接实施，不否决知识。；输入短文件、未检查ACL返回值、比较失败仍exit0等限制已明确，未来验收不能只看退出码。

### answer-a8d96b5afc — transpose

选择：双端连续轴矩形/条带任务，DMA+原始整数Scalar UB重排，通用回退。

- 源码与硬件事实（2）：准确恢复Raw位模式、每元素rank解码、4096为选核目标而非UBtile及20case结构。 引文定位 `review/subjects/answer-a8d96b5afc/answer.md:64`。
- 完整方案及必要依赖（2）：一个访问重组Action配套Host/Kernel ABI、矩形owner、DMA、局部重排与完成边，覆盖一般高rank时固定其余轴而非错误二维reshape。 引文定位 `review/subjects/answer-a8d96b5afc/answer.md:142`。
- 工作/覆盖/代价影响选择（2）：对比Nr到Kr、2Ns不变、O(N)局部Scalar重排/双区容量和计数器替代，提供具体重选条件。 引文定位 `review/subjects/answer-a8d96b5afc/answer.md:167`。
- P/O正文实质采用（2）：P双端stride/合轴和O多块DMA双端单位、固定pitch、最后消费者均实质进入算法/容量/尾部；未虚构转置API。 引文定位 `review/subjects/answer-a8d96b5afc/answer.md:390`。
- 范围/unknown/归因/外部轮次（2）：明确Raw DMA与Scalar UB可见性为实施缺项，PIPE_ALL不自动解决；一轮只做条件计划，未造实现/正确性/收益。 引文定位 `review/subjects/answer-a8d96b5afc/answer.md:440`。

关键缺口：原始整数DMA支持、Scalar UB访问与DMA交接可见性、实际UB预算未闭合；这是一份有准确公式和映射的条件方案，不是可直接执行候选。；相邻矩形/跨核短行物理写入契约须确认；若需要共同物理owner会返回C2，没有声称逻辑不重叠已证明安全。

### answer-c4844129d1 — grid_sampler_3d

选择：原owner及几何/取数不变，bilinear算术批量Vector，T∈256/512/1024。

- 源码与硬件事实（2）：区分Scalar主体与末端Cast、64B输出分区、14bilinear/6nearest和非有限grid继承缺口。 引文定位 `review/subjects/answer-c4844129d1/answer.md:75`。
- 完整方案及必要依赖（2）：一个Action完整组织14路Scalar输入、原八项运算图、FP16转换/有效写回和最后消费者，不添加无必要成员。 引文定位 `review/subjects/answer-c4844129d1/answer.md:217`。
- 工作/覆盖/代价影响选择（2）：同时计24M+8M Scalar发射、15路新增Scalar暂存、65,536/67,584B区以及原始随机取数/几何残余，给出替代和重开条件。 引文定位 `review/subjects/answer-c4844129d1/answer.md:137`。
- P/O正文实质采用（2）：P独立几何骨架与派生状态Action缺口改变选择，O count/Cast/Compare/有效搬出及别名资源具体影响方法。 引文定位 `review/subjects/answer-c4844129d1/answer.md:437`。
- 范围/unknown/归因/外部轮次（2）：三部分摘要保留一轮权限、R0、未实现未测与残余；独立核验SDK模式/alias而不将性能unknown设为安全门禁。 引文定位 `review/subjects/answer-c4844129d1/answer.md:463`。

关键缺口：实际SDK Mul/Add精确alias、Scalar/Vector浮点模式、UB/预留尚未闭合，最终源码与全oracle未执行；回答准确保留conditional_plan。；nearest、几何重算、随机X读取及FP16标量扩位保留；跨c几何状态有注册意图缺口。

### answer-f57f8ae4c2 — reduction_sum

选择：保留现有单核AR全载；基础ReduceSum、增核/流水均作具体成本比较。

- 源码与硬件事实（2）：准确恢复3×32FP32、8个物理输出与5个零、96/8元素搬运、单核无偏移及独立scratch。 引文定位 `review/subjects/answer-f57f8ae4c2/answer.md:23`。
- 完整方案及必要依赖（2）：零Action保留判断不造假的优化/KEEP回执，C2完整提取既有owner/通路与C3零改动范围。 引文定位 `review/subjects/answer-f57f8ae4c2/answer.md:169`。
- 工作/覆盖/代价影响选择（2）：四参数ReduceSum候选从1调用变3调用、scratch/目的布局/打包和同步完整比较，未凭高阶名字认定更慢。 引文定位 `review/subjects/answer-f57f8ae4c2/answer.md:135`。
- P/O正文实质采用（2）：P FullLoad/Split与O搬运/单tile流水/生命周期/物理输出边界改变保留决定，精确点名替代API合法性缺项。 引文定位 `review/subjects/answer-f57f8ae4c2/answer.md:220`。
- 范围/unknown/归因/外部轮次（2）：原oracle全8元素/NaN/exit0/短文件限制与一轮未测状态分开；不宣称正式NOOP或未来实施授权。 引文定位 `review/subjects/answer-f57f8ae4c2/answer.md:278`。

关键缺口：若后续重开基础ReduceSum，需scratch、目的地址/布局、三结果打包与意图归属；本次保留选择不要求强行试验。；全部8输出、NaN比较、短输入/未检返回值/比较失败exit0均单列，后继验收不能以原exit0当正确性。

## 适用限制

未发现冻结标准所列明确失败：没有编造已实施/正确性通过/加速比，没有强制换Action、增加Key或无条件否决未测方法。各答对具体SDK、资源、数值和同步缺口仍有实施门槛；本评分接受其有边界的条件方案，不将其提升为C3准入通过。所有总分只说明本次提供充分静态材料时的方案表达质量，不能证明真实检索效率、实际多轮硬件反馈、runtime语义正确、性能收益或相对旧版本的因果改进。

四份后继记录另作定性检查，结论在下节单独记录，不合并到80/80。

## 四份后继的独立定性检查

初轮grades.json已在阅读后继前锁定，仍匹配原hash；本节不解盲、不改八份初轮评分。完整连续引文与身份见HISTORY.json。

- grid_sampler_3d R2：保留原Action，但把未闭合alias改为18个独立FP32数组的保守条件布局，计算74T/72T+R及1024/1536/2048、双槽预算；几何复用仍保留注册意图缺口与成本。 证据 `history-runs/grid_sampler_3d-r2/answer.md:1`。
- grid_sampler_3d R3：没有强换Action或造新候选，保留R0及条件方案，交付18数组容量、34/35调用表达式模型、几何复用/nearest残余，按外部三轮范围结束。 证据 `history-runs/grid_sampler_3d-r3/answer.md:1`。
- maximum R2：保留int8转换链收缩，以128KiB核算R0 17T与S1 9T及4096/8192/16384参数边界，固定T的6L→3L与放大tile另减L分别计数；广播、双槽、case18驻留重新比较。 证据 `history-runs/maximum-r2/answer.md:1`。
- maximum R3：保留同一Action条件方案和R0，明确不因已投入而自动继续；结束本授权范围且不追加第四轮，资源/GM工作/未测残余持续保留。 证据 `history-runs/maximum-r3/answer.md:1`。

四份均保留R0、未实施/未测及残余机会；同Action可以继续，最终停止来自外部三轮范围，未以accepted或连续无收益自创停止。128KiB只收窄容量分析，不变成设备探测、API支持或性能证据。

限制：这是提供摘要的无工具静态后继，不能证明自主读取效率；没有实际patch、失败候选或有效/无效硬件计时，不能外推真实实验反馈能力。
