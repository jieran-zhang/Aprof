# MaskedScale：R1静态机会与条件方案

任务仅使用原始源码与原20case。910C/A3是任务目标；没有执行设备查询、build/native/profiling或训练。无实测时延。

源码/矩阵引用见source-refs.json与matrix-costs.json；完整20case均纳入正确性/性能后继范围，分组只决定候选与fallback。

关键源码位置（均为当前父本，非推断硬件）：

- source/op_kernel/masked_scale_kernel.asc:52 — void Process
- source/op_kernel/masked_scale_kernel.asc:76 — void Compute
- source/op_kernel/masked_scale_kernel.asc:56,63 — CopyIn
- source/op_kernel/masked_scale_kernel.asc:58,100 — CopyOut
- source/op_kernel/masked_scale_kernel.asc:41,42,43,44,45,46,48 — InitBuffer
- source/op_kernel/masked_scale_tiling.h:23 — Compute
- source/op_kernel/masked_scale_tiling.h:16,28,29 — blockNum
- source/op_kernel/masked_scale_tiling.h:17,30 — tileElements

当前源码成本：

|case|N输出|dtype|逻辑GM字节|额外结构|
|---|---:|---|---:|---|
|1|1048576|float16|5242880|77824|
|2|4194304|float32|37748736|94208|
|3|16777216|bfloat16|100663296|73728|
|4|67108864|float16|536870912|81920|
|5|67108864|float32|603979776|94208|
|6|1046529|bfloat16|5232645|77824|
|7|1030189|float16|5150945|77824|
|8|1181953|float32|11819530|90112|
|9|49691433|bfloat16|397531464|81920|
|10|1051137|float16|5255685|77824|
|11|1092819|float32|9835371|94208|
|12|1000007|bfloat16|6000042|73728|
|13|10912759|float32|130953108|98304|
|14|3042039|float16|15210195|77824|
|15|1049088|float32|9441792|94208|
|16|2089215|bfloat16|10446075|77824|
|17|2093567|float16|10467835|77824|
|18|2094078|float32|20940780|90112|
|19|2089980|bfloat16|16719840|81920|
|20|10549248|float32|94943232|94208|

静态字节只含显式分配；API临时/保留区另计。GM是逻辑有效请求量，不冒充HBM实际流量。首四项当前核数C=min(cores,ceil(N/4096))且blockLength=ceil(N/C)，未查询cores。AdamW另按512元素对齐块长，T依赖B。

候选 storage（reuse_disjoint_onchip_buffers；适用case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：xf只用于Mul(of,xf,mf)，随后不再读旧xf；of后续仅Muls及FromFloat。因此目标完全alias xf可删outFp_一片。

比较：每种X/M dtype都可减少4T静态字节并扩大tile域；相对直接删int8→half→float转换，不依赖未核验的直接Cast支持，也不改精度。 预测：UB系数从2sx+sm+12+2Ibyte下降为2sx+sm+8+2Ibyte，T4096减少16384字节。

候选 casts（coalesce_cast；适用case 1,2,5,6,7,10,11,14,15,16,17,20）：int8/uint8先转half再转float，整型值范围可在half精确表示；直接int8→float若目标支持可省一次Cast与half缓冲。

比较：数值域可静态证明，但实际目标SDK直接Cast是否支持未读到已验证平台，暂缓；不把int8→half→float当成必然冗余性能瓶颈。 预测：若支持直接Cast，则每tile减少一个转换和2T中间区；否则保持两段。

候选 pipeline（software_pipeline_stages；适用case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：两路CopyIn及一路CopyOut使用单槽，Compute含转换及两个乘法。

比较：能打开搬运重叠但多dtype槽宽不同，增槽压缩T；先用确定生命周期减少物理分配再决定双缓冲。 预测：输入搬运可与前tile计算重叠，逻辑GM字节(2sx+sm)N不变。

选定方案：删除outFp_，令of=xf，以Mul(xf,xf,mf)后Muls(xf,xf,scale)保持原先先乘mask再乘scale；FromFloat(yLocal,xf)保留原RoundMode。T=64k，第一候选4096；后续T≤floor64((UB原预算-API预留)/(2sx+sm+8+2Ibyte))，Ibyte表示int8/uint8 mask。输入输出所有权、每个有效count和半精度输出路径保持原定义；不把scale0或mask0替换成常数以规避Inf/NaN。

具体补证据：需确认目标Mul完整dst=src0别名及依赖完成规则，实际B与CopyPad/API字段上限。整型mask两段Cast的支持不能推断为直接转换支持。

正文如何改变判断：完整Problem目录已检查28项。连续一遍扫描没有中间GM往返、跨kernel链或归约，未把无支持的融合/归约/复用机制作为主机会；这不是依赖profile排除。对所列每项已按expansion读取正文，具体阅读影响在decision.knowledge_use。容量条目使“静态分配可减少”与“真实容量瓶颈”分开；流水条目要求真实物理槽及完成边，不能只改depth。

C2状态：条件规划；缺真实architecture_profile（SoC/ISA确证、core数、可用UB与SDK/API能力/来源），不能形成可实施的严格C2/C3。已有分区提取不计并行优化；SwiGLU整段owner属于新规划。C1可以建立严格机器记录并校验；所有正确性/性能须后续原20case完整验证，未编译、未实现、未测量。
