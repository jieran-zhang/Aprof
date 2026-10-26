# R14 完整共同计划

从R13-attempt-03复制独立attempt，原数学坐标、8邻居索引、原输入/output dtype、padding/align、原20和固定计时全部保留。整体仍research unadmitted；合法局部layout/Boolean vectorize单独router，树形数值与继承派生geometry/软件FMA不得借batch ID准入。

small分派的实际结构条件是bilinear且I*item<=131072。所有该域使用AoS geometry，group Host仍C>=16/原source-cost条件；group内改为全8槽，9原four改full8(T约1280)，源plane重读由8块到10块的约25%新增明确计入，不再将旧ceil guard当通用最优。其它half/float、large/nearest保留原SoA格式，G Scalar fallback也必须按同条件写AoS。idx AoS地址8*p+k（u32 byteoffset），coef AoS同位置float，coef GM基址仍8*geometryLength*u32；workspace64G不减少，也无新Task。producer G output每point32B，原geometryBlockLength16倍保证核边界512B对齐，最后尾只一owner；consumer gp按batch/spatial夹断，不跨N尾。

G使用独立perm8K4/out8K4，perm[q]=((q/8)+(q%8)*K)*4。Arange/ShiftRight/ShiftLeft/Sub/Muls/Add整数生成，借尚未产生的indices作init临时，ALL后才当前G写；所有数<8K*4。两次Gather(indices/coeff)到out后各ALL→MTE3→ALL，才能覆盖out。K512仅给AoS且geometryBlockLength>256，其余64/128/192/256原条件；所有predicate行从32B改max(32,K/8)，数值不变。预测G512 named half153984/float157056，小于TMP188416，实际源码独立重核。

G regular判断：原GE/LE/And保留，guard source64个U32先全-1定义，And只覆盖真实3Kbits；int32 EQ(-1) Compare完整64元素→独立32B输出，ALL后Scalar仅核真实6/12/18/24/48 bits。padding全1不会掩盖真实false；src/dst不重叠，后续candidate/Select写区按最后reader复用。没有Profile Scalar热占比事实，不称PMU确认。

consumer每tensor读1个连续8*count*4B段，短尾idx全sentinel、coef全+0后ALL→MTE2，长度本为32B倍数故无AoS dummy。原X每NC一次cache（group仍每channel/tile重读），一次Gather8T/halfCast8T/Mul8T；normal BlockReduceSum<float>(acc,values,T/8,64,1,1,8)，每32B连续8项归成1float。T128倍数且<=1920：repeat<=240，源范围32T B、目的4T B，独立32B基址且不原地alias，PIPE_V/末ALL闭合。它将原Mul+8Add+Dup约196T UB字节模型降至132T（有效和padding分列），不是算术减半：加法8项顺序改3层树、源仍8项。无普通acc Duplicate；软件分支先定义全T acc再Scalar写valid，ALL后Cast/MTE3。

数值：每term仍原FP32 coefficient与FP32值，tree并非R0/parent位等价；浮点有限舍入/消去可能改变，原floor/MERE/MARE及special完全不改。Float原|x|>=2^124保护仍在，高幅值软件按k0..7 FMA，normal误差不宣称全域证明。Half有限源|x|<32时，8个[0,1]系数的保守sumabs<256，gamma24*256约0.000367<原half floor/4；用于约束新增系数/乘法/树与参考累加的误差余量，half最终量化/坐标保持边界仍用原oracle。有限|x|>=32按数据条件走软件FMA，不按shape/个别值白名单；±Inf/NaN不作此有限guard，普通IEEE term集合的NaN/±Inf分类由原special合同判断，±0符号/payload不新增门槛。该32是数值保护条件，不是性能最佳参数，也不取自本批输入范围；普通有限误差分析不扩大到非法索引/非有限坐标的全域证明。

Half源cache按Align128(I+1)分配并全定义，Float保持Align64；输入load前Duplicate→ALL→MTE2→ALL→sentinel Scalar→ALL。nongroup在当前G写之前借idx和coef两谓词/acc压缩，group保live G改借values两片/acc；Half两次有限区间比较加And分别识别[32,65504]与[-65504,-32]，不以Inf误触发。mask firstWords=Align64(ceil(I/32))，helper完整定义并压缩，最大Half65536源可产生64个full words，需真实检查两个32-bit结果；不沿用03 max32假设。group容量按真实split核，返回ALL后才metadata/Gather/acc恢复。rare软件读已Gather的原FP32 values/coef，没有新增GM重读；每valid点8次整数FMA/Scalar UB读写，可能很慢，频繁触发必须如实计入。Half cache增宽及扫描、G配套、所有新增初始化都在原完整callback；元数据GM有效字节不变、kernel-map/Task数仍4/3/2。

必要C3：本binary原20，weighted18、small非dyadic三路径、narrow normal/extreme、packed nearest，以及新可达half近相消/normal特殊值边界。固定bundle原launch顺序执行、失败即停，build/C4唯一pair分开；pair直接R0/R13-parent/B，不乘历史倍率。G/consumer资源峰、实际API/alias/lastreader/owner先独立闭合，再原oracle，不因CPU证据预填device passed。
