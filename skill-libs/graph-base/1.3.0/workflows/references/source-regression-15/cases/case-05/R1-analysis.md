# ApplyAdamW：R1静态机会与条件方案

任务仅使用原始源码与原20case。910C/A3是任务目标；没有执行设备查询、build/native/profiling或训练。无实测时延。

源码/矩阵引用见source-refs.json与matrix-costs.json；完整20case均纳入正确性/性能后继范围，分组只决定候选与fallback。

关键源码位置（均为当前父本，非推断硬件）：

- source/op_kernel/apply_adam_w_kernel.asc:98,226 — void Process
- source/op_kernel/apply_adam_w_kernel.asc:127 — void Compute
- source/op_kernel/apply_adam_w_kernel.asc:104,111,231,283 — CopyIn
- source/op_kernel/apply_adam_w_kernel.asc:106,174,268,314 — CopyOut
- source/op_kernel/apply_adam_w_kernel.asc:89,90,91,92,93,95,215,216,217,218,219,220,221,223 — InitBuffer
- source/op_kernel/apply_adam_w_kernel.asc:17,158,257 — SafeSqrt
- source/op_kernel/apply_adam_w_kernel.asc:37,160,259 — SafeDiv
- source/op_host/apply_adam_w_common.h:10 — Compute
- source/op_host/apply_adam_w_common.h:23,24,66 — blockNum
- source/op_host/apply_adam_w_common.h:38,40,41,42,43,45,49,51,53,54,55,66 — ubFormer
- source/op_host/apply_adam_w_common.h:35,38,44,45 — bytesPerElement

当前源码成本：

|case|N输出|dtype|逻辑GM字节|额外结构|
|---|---:|---|---:|---|
|1|1048576|float32|20971520|20T+mask(T)+10240 <= B|
|2|4194304|float16|41943040|30T+mask(T)+10240 <= B|
|3|16777216|bfloat16|167772160|30T+mask(T)+10240 <= B|
|4|16777216|float32|335544320|20T+mask(T)+10240 <= B|
|5|33554432|float16|335544320|30T+mask(T)+10240 <= B|
|6|1046529|bfloat16|10465290|30T+mask(T)+10240 <= B|
|7|1030189|float32|20603780|20T+mask(T)+10240 <= B|
|8|1181953|float16|11819530|30T+mask(T)+10240 <= B|
|9|49691433|bfloat16|496914330|30T+mask(T)+10240 <= B|
|10|1051137|float32|21022740|20T+mask(T)+10240 <= B|
|11|1092273|float16|10922730|30T+mask(T)+10240 <= B|
|12|1000003|bfloat16|10000030|30T+mask(T)+10240 <= B|
|13|10912759|float32|218255180|20T+mask(T)+10240 <= B|
|14|3042039|float16|30420390|30T+mask(T)+10240 <= B|
|15|1049088|float32|20981760|20T+mask(T)+10240 <= B|
|16|2089215|bfloat16|20892150|30T+mask(T)+10240 <= B|
|17|2093567|float16|20935670|30T+mask(T)+10240 <= B|
|18|2094078|float32|41881560|20T+mask(T)+10240 <= B|
|19|2089980|bfloat16|20899800|30T+mask(T)+10240 <= B|
|20|10549248|float32|210984960|20T+mask(T)+10240 <= B|

静态字节只含显式分配；API临时/保留区另计。GM是逻辑有效请求量，不冒充HBM实际流量。首四项当前核数C=min(cores,ceil(N/4096))且blockLength=ceil(N/C)，未查询cores。AdamW另按512元素对齐块长，T依赖B。

候选 input_pipeline（software_pipeline_stages；适用case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：四输入每tile全部读入后执行safeSqrt/safeDiv长链，再单输出写回；四路输入各一槽。

比较：与12个字段缓存相比，预取作用于每元素四路读流量。相比复用5个FP32算术缓冲，原代码已经就地覆盖grad/m/v并复用scratch，进一步alias易破坏safe分支。 预测：四路输入各2物理槽、输出1槽，FP32需求36T+mask，低精度38T+mask；为下一tile输入打开与当前长计算重叠窗口。

候选 storage（reuse_disjoint_onchip_buffers；适用case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：FP32用5队列，低精度用5原始队列加5FP32缓冲；同一bufB/C/D/E已多用途覆盖。

比较：host按20/30字节系数及mask+10240预留选最大tile，容量是显式约束；没有证据再合并a/b/c/d/e可保留var、分母与特殊值恢复，因此不先减少缓冲。 预测：只有证明额外生命周期分离才可降低系数；不能依据变量名多直接减至四个。

候选 metadata（hoist_invariant_control；适用case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：每tile复制beta1/beta2/oneMinus/invBias/weightDecay/epsilon/signedLr与三个常量bits。

比较：编译器可能消除；该链有四路GM与大量Compare/Select，先选更直接的跨tile调度。字段外提会增长标量生存期，留作编译结果后的后继。 预测：将不变tiling值缓存到Init可减少源码加载，实际spill/LoadStore变化需编译确认。

选定方案：保留host对齐512的blockFormer与输出owner，四路输入队列各配置2物理槽，输出1槽，低精度5个FP32 compute buffer仍1套。T=64k，系数float32=36、half/bf16=38；alpha*T+ceil(ceil(T/8)/256)*256+8192+2048≤B，并保留copy字段上限2097151/s。在当前tile DeQue/读入计算前后为下一tile独立槽预取，队列最大未DeQue数受SDK深度约束，逐代完成后回收。保持SafeSqrt、SafeDiv、weightDecay条件、bias与输出RoundMode全部不变；单tile回退原槽数。

具体补证据：B实际值、目标两槽队列约束和Select内部预留是否仍需8192尚未硬件/SDK确认；8192+2048来自原host源码而非已验证910C资源。

正文如何改变判断：完整Problem目录已检查28项。连续一遍扫描没有中间GM往返、跨kernel链或归约，未把无支持的融合/归约/复用机制作为主机会；这不是依赖profile排除。对所列每项已按expansion读取正文，具体阅读影响在decision.knowledge_use。容量条目使“静态分配可减少”与“真实容量瓶颈”分开；流水条目要求真实物理槽及完成边，不能只改depth。

C2状态：条件规划；缺真实architecture_profile（SoC/ISA确证、core数、可用UB与SDK/API能力/来源），不能形成可实施的严格C2/C3。已有分区提取不计并行优化；SwiGLU整段owner属于新规划。C1可以建立严格机器记录并校验；所有正确性/性能须后续原20case完整验证，未编译、未实现、未测量。
