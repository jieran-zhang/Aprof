# Exp：R1静态机会与条件方案

任务仅使用原始源码与原20case。910C/A3是任务目标；没有执行设备查询、build/native/profiling或训练。无实测时延。

源码/矩阵引用见source-refs.json与matrix-costs.json；完整20case均纳入正确性/性能后继范围，分组只决定候选与fallback。

关键源码位置（均为当前父本，非推断硬件）：

- source/op_kernel/exp_kernel.asc:26 — void Process
- source/op_kernel/exp_kernel.asc:45 — void Compute
- source/op_kernel/exp_kernel.asc:30,37 — CopyIn
- source/op_kernel/exp_kernel.asc:32,69 — CopyOut
- source/op_kernel/exp_kernel.asc:18,19,21,22 — InitBuffer
- source/op_kernel/exp_tiling.h:18 — Compute
- source/op_kernel/exp_tiling.h:11,23,24 — blockNum
- source/op_kernel/exp_tiling.h:12,25 — tileElements

当前源码成本：

|case|N输出|dtype|逻辑GM字节|额外结构|
|---|---:|---|---:|---|
|1|1048576|float16|4194304|49152|
|2|4194304|float32|33554432|32768|
|3|16777216|bfloat16|67108864|49152|
|4|67108864|float16|268435456|49152|
|5|67108864|float32|536870912|32768|
|6|1046529|bfloat16|4186116|49152|
|7|1030189|float16|4120756|49152|
|8|1181953|float32|9455624|32768|
|9|49691433|bfloat16|198765732|49152|
|10|1051137|float16|4204548|49152|
|11|1092819|float32|8742552|32768|
|12|1000007|bfloat16|4000028|49152|
|13|10912759|float32|87302072|32768|
|14|3042039|float16|12168156|49152|
|15|1049088|float32|8392704|32768|
|16|2089215|bfloat16|8356860|49152|
|17|2093567|float16|8374268|49152|
|18|2094078|float32|16752624|32768|
|19|2089980|bfloat16|8359920|49152|
|20|10549248|float16|42196992|49152|

静态字节只含显式分配；API临时/保留区另计。GM是逻辑有效请求量，不冒充HBM实际流量。首四项当前核数C=min(cores,ceil(N/4096))且blockLength=ceil(N/C)，未查询cores。AdamW另按512元素对齐块长，T依赖B。

候选 pipeline（software_pipeline_stages；适用case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：每tile固定CopyIn→Compute→CopyOut，输入输出各1物理槽；跨tile无数学依赖，新增槽可打开预取窗口。

比较：相比仅缓存multiplier/shift，本方案作用于两路GM与完整Vector链的调度；相比扩大4096 tile，不要求先认定发射成本主导。代价是额外物理槽和序言尾声。 低精度fi/fo复用可减少4T并作为B不足时的后继，但不覆盖FP32路径，也不单独产生预取窗口。 预测：输入输出物理槽各由1变2，GM有效字节不变2sN；允许copy(t+1)与compute(t)依赖独立。

候选 storage（reuse_disjoint_onchip_buffers；适用case 1,3,4,6,7,9,10,12,14,16,17,19,20）：低精度Exp的fi只在Muls(fo,fi,multiplier)被消费，后续Adds/Exp均只读fo；使用fi作完全原地计算可删除fpOut_的4T字节，FP32路径原本已直接用out。

比较：是流水的最强资源替代：低精度可省16384字节并扩tile域，但不直接打开跨tile重叠，且不影响7个FP32 case。本轮先检验作用全部dtype的独立槽流水；若双槽B不足，优先把这个复用方案作为条件后继，不能直接拼成未确认的两动作实现。 预测：低精度单槽显式UB从12T变8T，T4096省16384字节；GM字节、Cast次数与原Muls/Adds/Exp次序保持。

候选 tile（dispatch_by_workload；适用case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：三dtype使用同一个4096 tile；FP32为8T字节、低精度为12T字节，允许按资源选择不同T。

比较：大tile可减循环但不能直接解决单槽依赖；20case均约百万级以上，缺少独立的小任务开销区间证据，因此不先造shape阈值。 预测：T改变使总tile数变为Σceil(length_core/T)，单次算法元素运算不变。

候选 metadata（hoist_invariant_control；适用case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：Process反复读取tileElements，Compute读multiplier/shift；字段在一次launch内不变。

比较：编译器可能已外提且每tile处理4096个Exp，当前没有证据说明字段load比流水更重要；保留竞争候选。 预测：源码字段访问由每tile移至Init，真实指令减少须编译确认。

选定方案：保留blockNum/blockLength与精确有效长度；T∈{1024,2048,4096}，原始输入/输出各2物理槽，FP32工作区仍仅当前计算tile一套。UB=(4s+8·[s=2])T+API预留≤B可用，即三dtype数据区均16T。序言只预取tile0；每轮DeQue当前输入后，合法发射下一tile到另一空闲槽，再计算当前tile、入输出队列并发有效长度写回。输出槽仅在MTE3完成后回收；tileCount<2保留单槽。Exp乘加顺序及Cast模式不变。

具体补证据：目标B可用与双物理槽队列/事件支持尚无真实architecture/SDK证据；T=4096数据区65536字节，不把它当已获容量。

正文如何改变判断：完整Problem目录已检查28项。连续一遍扫描没有中间GM往返、跨kernel链或归约，未把无支持的融合/归约/复用机制作为主机会；这不是依赖profile排除。对所列每项已按expansion读取正文，具体阅读影响在decision.knowledge_use。容量条目使“静态分配可减少”与“真实容量瓶颈”分开；流水条目要求真实物理槽及完成边，不能只改depth。

C2状态：条件规划；缺真实architecture_profile（SoC/ISA确证、core数、可用UB与SDK/API能力/来源），不能形成可实施的严格C2/C3。已有分区提取不计并行优化；SwiGLU整段owner属于新规划。C1可以建立严格机器记录并校验；所有正确性/性能须后续原20case完整验证，未编译、未实现、未测量。
