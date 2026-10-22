# 1.3.0 十五原始算子独立语义复核

本复核只依据原始 raw-inputs、1.3.0 当前知识正文与 autonomy-a/b/c 的当前记录；未读取旧 source-regression-15 或过去硬件答案。只执行纯 CPU 文件与公式核验，没有编译、原始 Python 导入、native 或硬件执行。验收不取决于 Action 多样性或字段存在。

已完成15例原始kernel/host、工作负载、R1/R2主方案与最强替代的语义审读；case01容量表述已修回核实，case12两项问题也已修回复核。全部结论限无硬件条件规划。

| 算子 | 已抽核核心公式 | 知识实际影响与范围判断 |
|---|---|---|
| 01 exp | 2Ns GM；float=8T、16位=12T；两raw槽均16T；T=4096对应32768/49152→65536B | pipeline正文最后消费者/物理槽条件得到采用；性能未知未冒充安全失败。float与放大tile容量相等；比较文字原未限定dtype，已修回R1/R2/REPORT并复核，不改变选择。 |
| 02 mish | 每tile15个源级Vector API；(2s+12)T+256ceil(ceil(T/8)/256)；T=2048→4096数值吻合 | coalesce保留每元素Exp/Ln/Tanh与负尾两Select，仅减少API发射。R2 Compare有效长度不扩写限制明确；选项不等于性能最优结论。 |
| 03 masked_scale | 每输出2sx+sm；5或6 API；(2sx+sm+12+2Iint)T | 输入mask为乘数，未以布尔化省工作。half能精确表示[-128,255]不证明目标直Cast支持，R2保留转换，未滥用unknown否决流水。 |
| 04 SwiGLU | 输出N=input/2，S=半轴×后续积；x0=out+floor(out/S)S；GM=3Ns，UB=12T/18T | coalesce/strided-pad正文实质限制成同owner多行批量，A=ceil(Ss/32)32/s、padding和输出有效长度分离。长S域明确不覆盖。 |
| 05 AdamW | 5Ns GM；20T/30T+mask+10240；四raw输入8T与E4T共享只减4T→26T | reuse正文“Free非物理共享”与最后读完成边被采用；float明确不收益，新增barrier和双槽40T竞争方案改变排序；不是派生数学复用借名。 |

独立纯 CPU 复算 A 全部100个matrix-derived GM字节值及SwiGLU全部20个segment映射，均吻合。原始kernel逐条计数支持上述API/容量结论。尚未据静态模型宣称候选已实现、正确性通过或加速。

C 冻结版（case12 两项问题已修回复核，详见后文）：

| 算子 | 核心公式与原源码抽核 | 实际知识影响、R2与范围判断 |
|---|---|---|
| 11 foreach | 4Ns GM、每tile4 DMA；FP32 16T、16位24T；T2048数据区32768/49152B，双槽均65536B | coalesce不跨host TensorList成员/8M chunk；R2把8192容量代价与双槽并列，收缩为4096优先。完整连续结构适用的标注合理，API仍partial。 |
| 12 maximum | 原scalar av>bv?av:bv；host zero-stride广播，scalar case5/11/12/13/19/20；FP16 case18已Vector | 排除已有Vector与int64收益，R2域缩到11/12/13/20合理。发现并已修正：FP32改为有明确条件的GT+Select/短行scalar参数，int32单独Max；替代方案N个比较与新增batch分列，见issues。 |
| 13 RoPE | GM=5RDs；UB float20D、窄dtype30D；窄dtype Cast=5D/row；BSND共享trig连续head，BNSD距离S | Vector batch正文保留两次乘法链与原加法顺序/禁FMA；驻留仅减trig请求，其流量占1/5，Nhead=1无head复用。R2实质收缩最强替代覆盖，无强制换Action。 |
| 14 transpose | 原N*rank除/模，GM2Ns；case1/14后缀128/127；二维和一般perm区分吻合 | transpose/strided-pad将矩形源pitch、UB pitch、局部置换和fallback纳入；full conditional仅任务骨架，不冒称所有dtype API已验证。 |
| 15 resize | 4N邻域请求，原加权8乘+3加=11N；几何与nc无关但x base依赖nc；四值和输出显式FP32区至少20St B | 采样正文仅partial采用，G/B/H/F绑定原ResizeCoord/clip/Floor/权重/加权次序；新geometry action_id=null，意图缺口诚实记录。R2区分上/下采样窗口代价、几何活跃区和task数，未偷换原输入复用。 |

独立复算 C 全100个matrix-derived表行：foreach元素/chunk/UB、maximum广播dispatch/内轴stride、RoPE行/复用距离/UB、transpose后缀、resize输出/几何/邻域计数均吻合（check_c.py）。这不构成候选数值通过或硬件收益验证。

B 冻结版复核：

| 算子 | 核心公式与原源码抽核 | 实际知识影响、R2与范围判断 |
|---|---|---|
| 06 Gather | 2Nrank除模，N(2b+bi)逻辑GM；实际source按X stride，index按输出shape解码 | gather_output_owned明确非gather轴可不等；case20 X前轴255不能替成index前轴127。hot-loop-address只外提非数据依赖前缀，index/guard保留。rank1收益有限，不虚构整行共享index。 |
| 07 Slice | GM2Nb；小stride T点输入span=s(T−1)+1；新增输入至多(s−1)Nb，UB按span计 | strided-pad与batch只作部分原则采用，未称Gather完整算法。R2 shrink-column步长2048回退标量，new-axis step0不丢base，保留64B owner。负stride/rank8未覆盖明确。 |
| 08 Grid3D | NCS几何与3NCS grid读；X请求上界KNCS，K=1/8；几何复用减少NS(C−ceil(C/Ct))，rawgrid减少3倍该量但不减少几何 | 采样正文部分采用且绑定原Unnormalize/padding/reflection/floor/tie-even/邻点累加；原grid、派生D和X值分开。R2完整八邻点记录224B/点+mask的代价导致有界Ct×St研究；geometry未注册，collect_evidence诚实，未借reuse输入Action晋升。 |
| 09 GELU | none12/tanh15显式API；UB=(2b+32)T+mask，原T1024得到37120/41216B | CompareSelect正文实质加入8192B Select临时区、CompareScalar补齐输入须定义和不能混同Compare重载；RINT/Erfc与负尾特殊值保留。R2缩紧T容量，不把tanh未用erfTmp当自动省分配。 |
| 10 Sigmoid | GM2Nb，8T/12T→双槽16T，1/3显式API；每核tile由真实核数与blockLength决定 | pipeline正文四类完成边和单tile无稳态进入方案；R2以Cavailable≥ceil(N/4096)时每核≤4096为反例，不能由全N大伪造流水收益。 |

独立复算 B 的06/08/09/10全部80行派生矩阵及Slice shrink行/列、new-axis三个关键边界；结果吻合（check_b.py）。另用纯CPU逻辑probe核验Compare的n=0/1/63/64/65/255/256/257/513补齐与predicate容量、原Maximum三元的NaN/±0选择和Grid负/正半整数tie-even；这仅为逻辑模型，不冒充目标API或候选正确性。

## scoped_evidence补强旁审

runtime/src/aprof_runtime/action_decision_v2.py的新增逐prediction证据核验可阻止仅凭同task引用另一父本/候选/workload静态JSON。direct_source例外限实际implementation_ref/change_ref，且仅对source_work可用。valid计时result_ref例外合理：只有path/hash完全相同才能略过包装，外层_feedback先verify_timing原链与算子/父本，v2再核候选源hash和实际case/domain集合；无需让既有统一计时结果额外伪装成attempt_identity回执。

**审查发现并已修复的既有范围限制：** 该例外所依赖的case集合核验不能宣传为shape/完整workload绑定。修复前v2以result.cases的case_id对照前轮path_overview.case_ids/domain；统一计时内部验证A/B capture的workload_ref相同，但未见将该capture每例workload内容/引用绑定回decision.path_overview.workload_ref完整清单的桥。因而同算子/父本/候选、同case ID但不同shape或属性的另一合法计时链，不能仅凭旧case ID检查推导为原决策工作负载测量。root现已增加v2 valid专用桥：前轮冻结cases[{case_id,workload}]唯一且覆盖完整清单，每candidate capture经引用hash读取完整workload payload，逐字段与前轮该case内容比较；复用统一计时已证明的A/B一致，不把完整矩阵hash与单例workload hash直接作相等比较。独立审读确认其仅约束valid，不给静态条件规划增加门禁；matching、同ID异shape、异oracle、missing mapping的CPU测试已审读，根代理运行通过。此为对当前已测反馈合同的旁审限制，不影响本批全部not_measured的三元identity静态回执；本次没有构造或运行设备计时。

## 修回复核与最终判断

case01已将“更小额外UB”限于16位，并明确float容量打平；R1/R2/REPORT一致。case12已将FP32原GT false→第二输入的NaN/±0语义、原oracle潜在差异与int32 Max支持范围显式分开；GT+Select用c=64ceil(n/64)、M=AlignUp(ceil(c/8),32)、模式2和8192B临时区，实际SDK仍条件化。独立复算513/37/101有效行的单槽三数据区+predicate+临时区为15200/8992/9760B，缺口写上界126/54/54元素、Compare组数9/1/2，均正确。最强替代也计这些代价，N个scalar比较减少与新增sum_owner,row ceil(valid/T)批次及repeat/位流量分开；短行可保留按行scalar分支，未强迫换Action。

15例作为自主、无硬件、条件化机制比较可接受。3项具体记录问题均已修回；最终210个round入口引用hash通过，副本source与raw-inputs逐文件内容一致。22种采用文档hash对照当前包一致。每例至少审读一个核心公式和一处实际知识影响；新增采样与CompareSelect有实际分域/容量/数值边界影响，未发现按case ID硬编码选择、派生数学复用借名注册、unknown强行封死性能试验或目标平台实测证据伪造。

上述结论不等于验证其未来最优Action、SDK可编译性、完整C2/C3、数值正确性或硬件收益。全部R1/R2仍未实施/未测；Grid几何意图保留提案，不以“选一个已注册Action”掩盖意图缺口。旁审发现的已测反馈workload桥也已修复并独立审读；这证明证据绑定更严谨，不证明任何设备收益。
