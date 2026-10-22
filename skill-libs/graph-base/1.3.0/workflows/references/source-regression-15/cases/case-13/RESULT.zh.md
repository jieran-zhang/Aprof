# case-13 apply_rotary_pos_emb：无硬件两轮自主分析

选定 `action.vectorize_scalar_loop`，R1/R2均为conditional_plan。R1未生成候选源码，R2只补静态证据；性能not_measured。原20case全部纳入成本与回归范围，特化适用case=1,2,3,4,7,8,9,11,13,14,15,16,18,19；其余保留原fallback。

目标910C/A3→dav-2201只表示任务声明的目标适用域，依据platform-basis.json；不是硬件探测。实际SKU/可见核/可用UB/SDK/API支持均未伪造。

## R1具体方案

先对half rotary mode按H=D/2两个连续半区使用FP32 Mul/Mul/Add，负半保留sign乘法或经数值审查的Neg，不用FMA；q/k各两半，输出最终Cast保持half CAST_NONE、bf16 CAST_ROUND。按原row owner处理，行批R∈{1,2,4,8}，原5D个FP32元素和低精度5D个raw元素，加双乘积scratch最多4D float：UB≤A(36RD)+I16*A(10RD)+Tmp+reserve。interleaved保持原路径，待SDK确认去交错/重排索引后独立候选。全部20case原路径覆盖。

## 机会比较

- action.vectorize_scalar_loop（selected，case 1,2,3,4,7,8,9,11,13,14,15,16,18,19）：half mode的partner是连续半区，逐元素volatile标量乘加可表达为逐半区Vector，仍保留运算边界。
- action.reuse_input_tiles（deferred，case 1,2,3,5,7,8,10,11,14,16,18,20）：layout0且N>1同seq重复读取cos/sin，复用可省trig读但不消除大部分逐元素算术；layout1需改任务顺序。
- action.narrow_sync_scope（deferred，case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：多次PIPE_ALL可能过宽，但当前V cast→Scalar GetValue与Scalar SetValue→V cast均有跨流水边，不能直接删。

## 全20case源码成本

以下为逻辑字节/源码操作计数，不是HBM实测，也不能换算为时延。完整shape、dtype、分发与其他成本列见R1-source-costs.json。

| case | dtype | 输出元素数 | 逻辑GM读写字节 | 结构差异 |
|---|---|---:|---:|---|
| 1 | float16 | 16777216 | 167772160 | half; layout=0; D=128; rows=131072 |
| 2 | float32 | 14179648 | 283592960 | half; layout=0; D=64; rows=221557 |
| 3 | bfloat16 | 6971776 | 69717760 | half; layout=0; D=128; rows=54467 |
| 4 | float16 | 15697920 | 156979200 | half; layout=1; D=128; rows=122640 |
| 5 | float32 | 33554432 | 671088640 | interleaved; layout=0; D=128; rows=262144 |
| 6 | bfloat16 | 16662720 | 166627200 | interleaved; layout=1; D=64; rows=260355 |
| 7 | float16 | 11053952 | 110539520 | half; layout=0; D=128; rows=86359 |
| 8 | float32 | 6328448 | 126568960 | half; layout=0; D=128; rows=49441 |
| 9 | bfloat16 | 9506944 | 95069440 | half; layout=1; D=128; rows=74273 |
| 10 | float16 | 7790464 | 77904640 | interleaved; layout=0; D=128; rows=60863 |
| 11 | float32 | 23635392 | 472707840 | half; layout=0; D=64; rows=369303 |
| 12 | bfloat16 | 2304576 | 23045760 | interleaved; layout=1; D=64; rows=36009 |
| 13 | float16 | 32000064 | 320000640 | half; layout=0; D=64; rows=500001 |
| 14 | float32 | 84864 | 1697280 | half; layout=0; D=128; rows=663 |
| 15 | bfloat16 | 1042432 | 10424320 | half; layout=1; D=128; rows=8144 |
| 16 | float16 | 1998848 | 19988480 | half; layout=0; D=128; rows=15616 |
| 17 | float32 | 62918592 | 1258371840 | interleaved; layout=1; D=64; rows=983103 |
| 18 | bfloat16 | 2088960 | 20889600 | half; layout=0; D=128; rows=16320 |
| 19 | float16 | 260096 | 2600960 | half; layout=1; D=128; rows=2032 |
| 20 | float32 | 12838784 | 256775680 | interleaved; layout=0; D=128; rows=100303 |

## R2新增静态证据与条件后继

遍历D=64/128所有维度证partner映射在行内、两次partner回到原维度；half mode两半闭式等价。原源码对每维4个volatile乘积和2个加法（q/k），使Scalar瓶颈假设比单纯字段缓存更具体；原特殊case13 Inf、14 NaN仍不能由CPU地址证明精度。R1不先融合cos复用，因为case13 N=1完全没有跨head复用；BNSD相邻row改变seq，不能把前row trig盲目驻留。

没有R1性能结果可支持/否定加速；前轮源工作预测只获得公式/地址适用性的静态支持，没有声称编译器已生成更少指令。R2-static-evidence.json给出每个case检查对象和结果。

## 实际阅读与采用

P/O全树咨询与Action绑定P路由回执均已保存；以下是条件方法采用，未形成正式C2 selection或C3执行。

- diagnosis：`skills/ascendc-aprof-diagnosis/graph/problems/problem.scalar_control_hot_loop.md` lines:292-304：half mode的partner是连续半区，逐元素volatile标量乘加可表达为逐半区Vector，仍保留运算边界。

- diagnosis：`skills/ascendc-aprof-diagnosis/graph/problems/problem.insufficient_input_reuse.md` lines:265-277：layout0且N>1同seq重复读取cos/sin，复用可省trig读但不消除大部分逐元素算术；layout1需改任务顺序。

- diagnosis：`skills/ascendc-aprof-diagnosis/graph/problems/problem.excessive_sync_scope.md` lines:304-316：多次PIPE_ALL可能过宽，但当前V cast→Scalar GetValue与Scalar SetValue→V cast均有跨流水边，不能直接删。

- parallel-planning：`skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md` lines:78-90：连续模板的相同索引前提不能直接套RoPE partner。这里只迁移互斥输出区间原则，task边界固定完整row，两个半区仍在同一owner内，不拆成互相覆盖的原地更新。

- optimization：`skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/batch.md` lines:85-97：RoPE half区采用H=32/64连续count，保留逐步乘加和Cast意图；batch正文要求保持原舍入，故完整精度仍须证明，不能仅由partner映射授权。

- optimization：`skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/input-tile-residency.md` lines:121-133：只有同seq的cos/sin原值才可共用；layout0且N>1可复用，case13 N=1无收益，layout1相邻row变seq需重定窗口。

- optimization：`skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md` lines:62-74：RoPE的MTE2→Cast→Scalar GetValue以及Scalar SetValue→Cast边必须保留；仅将数据算术改Vector不自动授权删除所有PIPE_ALL。

检索目录28个Problem全量审视后按源码问题展开，不用邻接top-k锁候选；D的每个候选分别绑定自己使用的Problem正文、适用依据与反证。未采用模板无需伪装已实施。

## 不能判断及后续补项

- constraint.capacity：实际UB与Mul临时区/保留未知；R=1..8须按36RD+低精度10RD+Tmp+reserve逐组预算。
- constraint.target_api：目标SDK Mul/Muls/Add count以及alias、尾长度、完成边支持未验证。
- constraint.numeric_order：Vector逐步舍入与原volatile float乘加及bf16 CAST_ROUND须核对；不允许FMA融合或改变特殊值规则。
- 性能：改Vector后是否主要受每row短DMA/同步限制；H=32/64的Vector发射数相对Scalar节省是否抵消新增scratch。

源事实、source refs/hash、原矩阵、R1/R2 reasoning/decision、expansion、P/O route、阅读记录均在本目录。C1按handoff/v3 schema与reasoning/decision校验；严格C2缺真实architecture与parallel/dispatch implementation绑定，未伪造。没有C3、计时结果、加速比或训练记录。

路由阶段区别：全树P/O咨询、Action绑定P候选、条件方法采用分别见route-selection-status.json；未生成正式C2 selection或C3 execution。逐项true条件的源码/数学证明见condition-audit.json。

独立复核修正：half-mode partner/row映射和目标算术表达式已经静态证明，但目标Vector Mul/Muls/Add是否保留原volatile FP32逐步舍入、正负零、NaN/Inf传播，以及half CAST_NONE和BF16 CAST_ROUND，尚无完整API/编译语义依据。constraint.semantic_equivalence包含这些条件，故保持unknown；不能用数学映射代替全域等价。 数学映射另有已知source.element_mapping_equivalence；条件Vector方向保留。

所有已知constraint.ref.locator现逐谓词定位condition-audit.json的basis字段，并提供原host/tiling/kernel/原oracle精确行引用；无lines:1标题充作证明。
