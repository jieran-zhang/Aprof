# case-12 maximum：无硬件两轮自主分析

选定 `action.restructure_broadcast`，R1/R2均为conditional_plan。R1未生成候选源码，R2只补静态证据；性能not_measured。原20case全部纳入成本与回归范围，特化适用case=11,12,13,20；其余保留原fallback。

目标910C/A3→dav-2201只表示任务声明的目标适用域，依据platform-basis.json；不是硬件探测。实际SKU/可见核/可用UB/SDK/API支持均未伪造。

## R1具体方案

保留sameShape已有Vector路径。针对case11的[rows,513]+[1,513]按整行/行片段搬入；case12/13/20沿最后连续轴W=37/256/101分段，一次解码外轴及读取对应单一broadcast值，生成局部副本后按原max语义计算。U∈{256,512,1024,2048}，单槽UB至少3*A(U*s)+转换/比较临时区+R；广播标量区另计A(s)。FP16 case18维持已有row路径可后续保留8193列分段。int64 case5/19保留64bit比较并单独外提地址解码，禁止转float。未知shape继续原fallback，不用case值域改变dtype。

## 机会比较

- action.restructure_broadcast（selected，case 11,12,13,20）：将重复rank解码降至每连续片段，并把长连续x1从scalar GM读取改为DataCopy+批量比较。
- action.vectorize_scalar_loop（deferred，case 5,19）：同形int64 case5很大但目标Vector int64比较未有能力依据；不能用float替代，纯地址外提保留可行。
- action.reuse_input_tiles（deferred，case 18）：case18在255行重复加载同8193元素半精度源，可保留一行或列片段；目前已Vector，不消除其他四组逐输出解码。

## 全20case源码成本

以下为逻辑字节/源码操作计数，不是HBM实测，也不能换算为时延。完整shape、dtype、分发与其他成本列见R1-source-costs.json。

| case | dtype | 输出元素数 | 逻辑GM读写字节 | 结构差异 |
|---|---|---:|---:|---|
| 1 | float16 | 1048576 | 6291456 | vector; rank=2; scalar除模=0 |
| 2 | float32 | 4194304 | 50331648 | vector; rank=2; scalar除模=0 |
| 3 | bfloat16 | 16777216 | 100663296 | vector; rank=2; scalar除模=0 |
| 4 | int32 | 67108864 | 805306368 | vector; rank=2; scalar除模=0 |
| 5 | int64 | 16777216 | 402653184 | scalar; rank=2; scalar除模=67108864 |
| 6 | int8 | 134217728 | 402653184 | vector; rank=2; scalar除模=0 |
| 7 | float16 | 1046529 | 6279174 | vector; rank=2; scalar除模=0 |
| 8 | float32 | 1030189 | 12362268 | vector; rank=2; scalar除模=0 |
| 9 | bfloat16 | 1181953 | 7091718 | vector; rank=2; scalar除模=0 |
| 10 | float16 | 49691433 | 298148598 | vector; rank=3; scalar除模=0 |
| 11 | float32 | 1051137 | 12613644 | scalar; rank=2; scalar除模=4204548 |
| 12 | float32 | 9684639 | 116215668 | scalar; rank=4; scalar除模=77477112 |
| 13 | int32 | 7864320 | 94371840 | scalar; rank=5; scalar除模=78643200 |
| 14 | float32 | 1000007 | 12000084 | vector; rank=1; scalar除模=0 |
| 15 | float16 | 10912759 | 65476554 | vector; rank=5; scalar除模=0 |
| 16 | float32 | 3042039 | 36504468 | vector; rank=5; scalar除模=0 |
| 17 | bfloat16 | 1049088 | 6294528 | vector; rank=2; scalar除模=0 |
| 18 | float16 | 2089215 | 12535290 | vector; rank=2; scalar除模=0 |
| 19 | int64 | 2093567 | 50245608 | scalar; rank=2; scalar除模=8374268 |
| 20 | float32 | 10549248 | 126590976 | scalar; rank=5; scalar除模=105492480 |

## R2新增静态证据与条件后继

抽样对齐完整20case的原rank解码与按外轴/连续内轴公式，证明case11/12/13/20的x1偏移等于linear；case12/13/20的x2索引为floor(linear/W)%H。case18源宽8193*sizeof(half)=16386不是32B倍数，不能靠UB padding声称静态Broadcast合法。int64值域虽小也不能授权cast；优先广播分段，比较语义未核验时保持原scalar compare。

没有R1性能结果可支持/否定加速；前轮源工作预测只获得公式/地址适用性的静态支持，没有声称编译器已生成更少指令。R2-static-evidence.json给出每个case检查对象和结果。

## 实际阅读与采用

P/O全树咨询与Action绑定P路由回执均已保存；以下是条件方法采用，未形成正式C2 selection或C3执行。

- diagnosis：`skills/ascendc-aprof-diagnosis/graph/problems/problem.broadcast_strategy_mismatch.md` lines:311-323：将重复rank解码降至每连续片段，并把长连续x1从scalar GM读取改为DataCopy+批量比较。

- diagnosis：`skills/ascendc-aprof-diagnosis/graph/problems/problem.scalar_control_hot_loop.md` lines:292-304：同形int64 case5很大但目标Vector int64比较未有能力依据；不能用float替代，纯地址外提保留可行。

- diagnosis：`skills/ascendc-aprof-diagnosis/graph/problems/problem.insufficient_input_reuse.md` lines:265-277：case18在255行重复加载同8193元素半精度源，可保留一行或列片段；目前已Vector，不消除其他四组逐输出解码。

- parallel-planning：`skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/broadcast.md` lines:98-110：广播模板的零stride/位图合轴使case12/13/20可按W=37/256/101内轴分段；axis=0源字节对齐限制使case18的16386B源不自动满足静态Broadcast。

- optimization：`skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/coalesce.md` lines:76-88：maximum只合并本owner连续x1行片，广播源偏移按零stride计算；不得把跨row或padding当有效元素。

- optimization：`skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/batch.md` lines:85-97：maximum优先有效count并保持广播row边界；scalar ternary与Vector Max的NaN/±0不自动等价，完整semantic_equivalence保持unknown。

- optimization：`skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/input-tile-residency.md` lines:121-133：case18的255行同8193列小源是同原值，驻留需保留x2只读且不能套输出off；实际源宽16386B和独立分配仍计入UB。

检索目录28个Problem全量审视后按源码问题展开，不用邻接top-k锁候选；D的每个候选分别绑定自己使用的Problem正文、适用依据与反证。未采用模板无需伪装已实施。

## 不能判断及后续补项

- constraint.capacity：需实际UB上限和静态Broadcast/比较临时区；U上限只能由3*A(U*s)+Tmp+R闭合。
- constraint.target_api：目标SDK对float/int32 Max或Compare+Select、局部Duplicate/Broadcast及非对齐尾接口支持未知。
- constraint.semantic_equivalence：float广播原scalar av>bv?av:bv与Vector Max的NaN/有符号零行为不自动等价；必须核对原oracle和明确异常值处理后才能替换。
- 性能：源循环解码是否经编译优化以及重复小输入是否L2已命中；分段Vector调用是否摊薄到37/101列仍获益。

源事实、source refs/hash、原矩阵、R1/R2 reasoning/decision、expansion、P/O route、阅读记录均在本目录。C1按handoff/v3 schema与reasoning/decision校验；严格C2缺真实architecture与parallel/dispatch implementation绑定，未伪造。没有C3、计时结果、加速比或训练记录。

路由阶段区别：全树P/O咨询、Action绑定P候选、条件方法采用分别见route-selection-status.json；未生成正式C2 selection或C3 execution。逐项true条件的源码/数学证明见condition-audit.json。

所有已知constraint.ref.locator现逐谓词定位condition-audit.json的basis字段，并提供原host/tiling/kernel/原oracle精确行引用；无lines:1标题充作证明。
