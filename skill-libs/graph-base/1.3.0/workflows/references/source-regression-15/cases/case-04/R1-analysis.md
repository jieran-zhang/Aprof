# SwiGLU：R1静态机会与条件方案

任务仅使用原始源码与原20case。910C/A3是任务目标；没有执行设备查询、build/native/profiling或训练。无实测时延。

源码/矩阵引用见source-refs.json与matrix-costs.json；完整20case均纳入正确性/性能后继范围，分组只决定候选与fallback。

关键源码位置（均为当前父本，非推断硬件）：

- source/op_kernel/swi_glu_kernel.asc:28 — void Process
- source/op_kernel/swi_glu_kernel.asc:59 — void Compute
- source/op_kernel/swi_glu_kernel.asc:40,48 — CopyIn
- source/op_kernel/swi_glu_kernel.asc:42,89 — CopyOut
- source/op_kernel/swi_glu_kernel.asc:18,19,20,22,23,24 — InitBuffer
- source/op_kernel/swi_glu_tiling.h:16 — Compute
- source/op_kernel/swi_glu_tiling.h:11,22,23 — blockNum
- source/op_kernel/swi_glu_tiling.h:12,24 — tileElements

当前源码成本：

|case|N输出|dtype|逻辑GM字节|额外结构|
|---|---:|---|---:|---|
|1|1048576|float16|6291456|S=1024, Q=1024, 不计核切分DMA=3072|
|2|4194304|float32|50331648|S=2048, Q=2048, 不计核切分DMA=6144|
|3|16777216|bfloat16|100663296|S=4096, Q=4096, 不计核切分DMA=12288|
|4|67108864|float16|402653184|S=67108864, Q=1, 不计核切分DMA=49152|
|5|66797640|float32|801571680|S=32760, Q=2039, 不计核切分DMA=48936|
|6|1046017|bfloat16|6276102|S=1046017, Q=1, 不计核切分DMA=768|
|7|1017072|float16|6102432|S=1008, Q=1009, 不计核切分DMA=3027|
|8|1181953|float32|14183436|S=1181953, Q=1, 不计核切分DMA=867|
|9|932547|bfloat16|5595282|S=7, Q=133221, 不计核切分DMA=399663|
|10|1049088|float16|6294528|S=512, Q=2049, 不计核切分DMA=6147|
|11|138957|float32|1667484|S=509, Q=273, 不计核切分DMA=819|
|12|1000003|bfloat16|6000018|S=1, Q=1000003, 不计核切分DMA=3000009|
|13|76648|float32|919776|S=536, Q=143, 不计核切分DMA=429|
|14|1519518|float16|9117108|S=506, Q=3003, 不计核切分DMA=9009|
|15|1048576|float32|12582912|S=2048, Q=512, 不计核切分DMA=1536|
|16|2080641|bfloat16|12483846|S=2080641, Q=1, 不计核切分DMA=1524|
|17|2095104|float16|12570624|S=2095104, Q=1, 不计核切分DMA=1536|
|18|4190208|float32|50282496|S=2048, Q=2046, 不计核切分DMA=6138|
|19|4178940|bfloat16|25073640|S=1044735, Q=4, 不计核切分DMA=3072|
|20|2611200|float32|31334400|S=50, Q=52224, 不计核切分DMA=156672|

静态字节只含显式分配；API临时/保留区另计。GM是逻辑有效请求量，不冒充HBM实际流量。首四项当前核数C=min(cores,ceil(N/4096))且blockLength=ceil(N/C)，未查询cores。AdamW另按512元素对齐块长，T依赖B。

候选 packed_segments（coalesce_contiguous_transfers；适用case 1,2,7,9,10,11,12,13,14,15,18,20）：短segment把主体拆碎。每segment两次读一次写；把R个完整segment的物理[x0,x1]对一次连续搬入，再UB重排并整批计算/写回。

比较：比仅外提除模同时减少DMA与Vector小count；比仅批量strided输入还覆盖碎片输出。代价为UB重排和额外暂存，需实际API支持。 预测：完整R段从3R次DMA降为1次packed输入+1次连续输出，必要3sRS字节不变；Vector主链由R次变1次批量。

候选 layout（reorder_contiguous_access；适用case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：逻辑x0相邻段在GM间隔S个x1元素；可比较多块strided DataCopyPad分别取x0/x1。

比较：保留2路输入语义但非对齐S可能引入UB padding，且Vector仍要处理strided布局；与packed方案比较API参数/重排成本，不能简单把x0段拼为连续。 预测：规则二维DMA可减少输入发射，但目标stride单位/行padding与计算span必须核验。

候选 vector（batch_vector_api_calls；适用case 9,12,20）：case9/12/20的S分别7/1/50，主体每段执行5(FP32)或8(低精度)个Vector调用。

比较：只在UB已连续后可合批，不能跨依赖串联不同算术操作；作为packed方案的配套执行而非单独无需布局的捷径。 预测：批R段使每运算count由S变RS，元素运算总数不变。

候选 metadata（hoist_invariant_control；适用case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：每段计算outIndex/S和outIndex%S并读tiling字段。

比较：递推段号可以减少标量除模，但S1仍有约百万轮及300万DMA，不如改变批量粒度的结构机会。 预测：用段指针和段余量递推可删除稳态除模；编译已消除程度未知。

选定方案：C2重新规划短S组的整段owner：Q=N/S段，核c分配[q0,q1)，处理R个完整段，R≥2且RS≤T、(5s+12·[s=2])RS+shuffleTmp≤B。一次读x[2qS:2(q+R)S]到packed，再以a[rS+j]=raw[2rS+j], b[rS+j]=raw[2rS+S+j]作UB向量重排；保持原Cast及Muls/Exp/Adds/Div/Mul，最后写y[qS:(q+R)S]。优先S∈{1,7,50}，候选R使RS≈512/1024/2048；其他S及API无法合法高效重排时走原segment路径，所有20case都覆盖。不能用逐元素GetValue实现shuffle冒充高效向量化。

具体补证据：真实架构/SDK上的UB重排、Gather/Deinterleave或合法strided重载、支持dtype、mask/stride单位及Tmp字节未知；已能证明映射和完整段owner，不能借950/3510能力补证。

正文如何改变判断：完整Problem目录已检查28项。连续一遍扫描没有中间GM往返、跨kernel链或归约，未把无支持的融合/归约/复用机制作为主机会；这不是依赖profile排除。对所列每项已按expansion读取正文，具体阅读影响在decision.knowledge_use。容量条目使“静态分配可减少”与“真实容量瓶颈”分开；流水条目要求真实物理槽及完成边，不能只改depth。

C2状态：条件规划；缺真实architecture_profile（SoC/ISA确证、core数、可用UB与SDK/API能力/来源），不能形成可实施的严格C2/C3。已有分区提取不计并行优化；SwiGLU整段owner属于新规划。C1可以建立严格机器记录并校验；所有正确性/性能须后续原20case完整验证，未编译、未实现、未测量。
