# Mish：R1静态机会与条件方案

任务仅使用原始源码与原20case。910C/A3是任务目标；没有执行设备查询、build/native/profiling或训练。无实测时延。

源码/矩阵引用见source-refs.json与matrix-costs.json；完整20case均纳入正确性/性能后继范围，分组只决定候选与fallback。

关键源码位置（均为当前父本，非推断硬件）：

- source/op_kernel/mish_kernel.asc:27 — void Process
- source/op_kernel/mish_kernel.asc:46 — void Compute
- source/op_kernel/mish_kernel.asc:31,38 — CopyIn
- source/op_kernel/mish_kernel.asc:33,94 — CopyOut
- source/op_kernel/mish_kernel.asc:18,19,20,21,22,24 — InitBuffer
- source/op_kernel/mish_tiling.h:19 — Compute
- source/op_kernel/mish_tiling.h:14,23,24 — blockNum
- source/op_kernel/mish_tiling.h:15,25 — tileElements

当前源码成本：

|case|N输出|dtype|逻辑GM字节|额外结构|
|---|---:|---|---:|---|
|1|1048576|float16|4194304|33024|
|2|4194304|float32|33554432|41216|
|3|16777216|bfloat16|67108864|33024|
|4|67108864|float16|268435456|33024|
|5|67108864|float32|536870912|41216|
|6|1046529|bfloat16|4186116|33024|
|7|1030189|float16|4120756|33024|
|8|1181953|float32|9455624|41216|
|9|49691433|bfloat16|198765732|33024|
|10|1051137|float16|4204548|33024|
|11|1092273|float32|8738184|41216|
|12|1000003|bfloat16|4000012|33024|
|13|10912759|float32|87302072|41216|
|14|3030027|float16|12120108|33024|
|15|1049088|float32|8392704|41216|
|16|2089215|bfloat16|8356860|33024|
|17|2093567|float16|8374268|33024|
|18|2094078|float32|16752624|41216|
|19|2089980|bfloat16|8359920|33024|
|20|10549248|float32|84393984|41216|

静态字节只含显式分配；API临时/保留区另计。GM是逻辑有效请求量，不冒充HBM实际流量。首四项当前核数C=min(cores,ceil(N/4096))且blockLength=ceil(N/C)，未查询cores。AdamW另按512元素对齐块长，T依赖B。

候选 storage（reuse_disjoint_onchip_buffers；适用case 2,5,8,11,13,15,18,20）：FP32路径同时分配in/out队列和fi/work/fo三片FP32区；fi可使用已DeQue的in物理区，fo可使用已分配out区，work单独保存。

比较：不需要先断言UB接近上限。通过减少8T字节给更大tile留空间，优于未经证明删除Mish稳定尾分支；相对双缓冲没有新增原始输入槽。 预测：FP32显式数据区由20T变12T，mask另计；T2048减少16384字节，可在同一原数据预算内提升至T3392。

候选 pipeline（software_pipeline_stages；适用case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：2048 tile输入输出1槽且串行调用；15个Vector调用形成长计算链。

比较：可能隐藏搬运，但增加原始槽容量且长计算本身可能主导；优先减少明确多余的物理区以放宽后续流水。 预测：多tile间允许MTE与Vector交错，但必要Exp/Ln/Tanh调用不变。

候选 casts（coalesce_cast；适用case 1,3,4,6,7,9,10,12,14,16,17,19）：低精度只在链入口扩位、末尾缩位，没有中途FP32→低精度→FP32往返。

比较：正文要求可删数值边界；此处Cast保护原FP32稳定计算，不能按语法出现两次就判冗余，作为当前不采用候选。 预测：删除入口/出口Cast会改变中间精度或输出dtype，当前没有等价删减。

选定方案：仅FP32模板：fi绑定in，fo绑定out，删除fpIn_/fpOut_两项InitBuffer，fpWork_保留；保留开头Adds(fi,in,+0)和末尾Adds(out,fo,+0)的原指令次序（即原地Adds），避免擅自改变±0行为。in活到最终Mul，out活到MTE3完成。先T2048，再在原41216字节显式预算内比较T∈{2048,2560,3072,3392}，UB=12T+ceil(ceil(T/8)/256)*256+API预留≤B。低精度路径继续2048和原Cast/负尾Exp+Select。

具体补证据：需确认目标Adds/Abs/Mul/Tanh等在VECIN/VECOUT位置及完全原地alias的支持，实际UB及Select/Tanh临时需求；不改变负尾-8阈值或浮点运算顺序。

正文如何改变判断：完整Problem目录已检查28项。连续一遍扫描没有中间GM往返、跨kernel链或归约，未把无支持的融合/归约/复用机制作为主机会；这不是依赖profile排除。对所列每项已按expansion读取正文，具体阅读影响在decision.knowledge_use。容量条目使“静态分配可减少”与“真实容量瓶颈”分开；流水条目要求真实物理槽及完成边，不能只改depth。

C2状态：条件规划；缺真实architecture_profile（SoC/ISA确证、core数、可用UB与SDK/API能力/来源），不能形成可实施的严格C2/C3。已有分区提取不计并行优化；SwiGLU整段owner属于新规划。C1可以建立严格机器记录并校验；所有正确性/性能须后续原20case完整验证，未编译、未实现、未测量。
