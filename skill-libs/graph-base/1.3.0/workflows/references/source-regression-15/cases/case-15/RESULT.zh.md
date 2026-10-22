# case-15 resize_bilinear：无硬件两轮自主分析

选定 `action.vectorize_scalar_loop`，R1/R2均为conditional_plan。R1未生成候选源码，R2只补静态证据；性能not_measured。原20case全部纳入成本与回归范围，特化适用case=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20；其余保留原fallback。

目标910C/A3→dav-2201只表示任务声明的目标适用域，依据platform-basis.json；不是硬件探测。实际SKU/可见核/可用UB/SDK/API支持均未伪造。

## R1具体方案

固定(nc,oh)后按Wtile∈{64,128,256}输出列分片；用原FP32 ResizeCoord直接算每个ow的w0/w1/dw，禁止累加scale递推。读入所需两源行的有界区间，按索引从UB取a/b/c/d，再批量执行原a*ah*aw+b*ah*dw+c*dh*aw+d*dh*dw的乘加顺序和最终Cast，不启FMA。强下采样若连续源span大于4*Wtile则用保守索引fallback或仅搬稀疏需要点；上采样保留两源行窗口。容量2*A(span*s)+至少A(7*4*Wtile)+输出raw+索引表+Tmp+reserve≤UB。所有20case分组执行，输出连续片归单核。

## 机会比较

- action.vectorize_scalar_loop（selected，case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：把逐输出输入解码和插值运算移到UB/Vector，地址按连续输出row分段，直接减少主体Scalar数据处理。
- action.hoist_invariant_control（deferred，case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：每row只算ih/h0/h1/dh，宽坐标按列计算或缓存可减少重复坐标，但仍4个GM标量读及输入解码。
- action.reuse_input_tiles（deferred，case 4,5,7,13,14,18,19,20）：上采样同源行/列强复用；整2倍下采样邻居不重叠，统一驻留整源行可能多搬无用字节。

## 全20case源码成本

以下为逻辑字节/源码操作计数，不是HBM实测，也不能换算为时延。完整shape、dtype、分发与其他成本列见R1-source-costs.json。

| case | dtype | 输出元素数 | 逻辑GM读写字节 | 结构差异 |
|---|---|---:|---:|---|
| 1 | float16 | 1048576 | 10485760 | out=[256, 256]; align=False; src=[512, 512] |
| 2 | float32 | 4194304 | 83886080 | out=[512, 512]; align=False; src=[1024, 1024] |
| 3 | bfloat16 | 16777216 | 167772160 | out=[1024, 1024]; align=False; src=[2048, 2048] |
| 4 | float16 | 8388608 | 83886080 | out=[512, 512]; align=True; src=[256, 256] |
| 5 | float32 | 67108864 | 1342177280 | out=[1024, 1024]; align=True; src=[128, 128] |
| 6 | bfloat16 | 6005783 | 60057830 | out=[511, 511]; align=False; src=[1023, 1023] |
| 7 | float16 | 8388608 | 83886080 | out=[512, 512]; align=False; src=[256, 256] |
| 8 | float32 | 344064 | 6881280 | out=[128, 128]; align=True; src=[1537, 769] |
| 9 | bfloat16 | 1486848 | 14868480 | out=[64, 64]; align=False; src=[367, 373] |
| 10 | float16 | 8388608 | 83886080 | out=[1024, 256]; align=False; src=[2049, 513] |
| 11 | float32 | 786432 | 15728640 | out=[512, 512]; align=False; src=[1025, 1025] |
| 12 | bfloat16 | 16032016 | 160320160 | out=[1001, 1001]; align=False; src=[2003, 2003] |
| 13 | float32 | 9371648 | 187432960 | out=[256, 256]; align=False; src=[17, 67] |
| 14 | float16 | 344064 | 3440640 | out=[128, 128]; align=False; src=[13, 4001] |
| 15 | float32 | 16777216 | 335544320 | out=[256, 1024]; align=False; src=[512, 2049] |
| 16 | bfloat16 | 33292288 | 332922880 | out=[512, 512]; align=True; src=[1024, 1024] |
| 17 | float16 | 4194304 | 41943040 | out=[2048, 256]; align=False; src=[4097, 511] |
| 18 | float16 | 4194304 | 41943040 | out=[512, 512]; align=False; src=[256, 256] |
| 19 | bfloat16 | 4194304 | 41943040 | out=[512, 512]; align=True; src=[256, 256] |
| 20 | float32 | 2359296 | 47185920 | out=[192, 768]; align=False; src=[384, 384] |

## R2新增静态证据与条件后继

按20case解析scale_factor到真实outH/outW，逐输出列枚举w0/w1集合并算span与unique数；整2倍下采样源pair不重叠，跨输出reuse不成立；8倍上采样case5共享源区显著，复用策略须分组。源行边界clamp使h0==h1或w0==w1允许读复用却不允许删四项运算：0*Inf/NaN仍影响结果。若API/精度不满足，只先外提oh相关坐标且仍用原ResizeOne算术，不声称Vector方案已实现。

没有R1性能结果可支持/否定加速；前轮源工作预测只获得公式/地址适用性的静态支持，没有声称编译器已生成更少指令。R2-static-evidence.json给出每个case检查对象和结果。

## 实际阅读与采用

P/O全树咨询与Action绑定P路由回执均已保存；以下是条件方法采用，未形成正式C2 selection或C3执行。

- diagnosis：`skills/ascendc-aprof-diagnosis/graph/problems/problem.scalar_control_hot_loop.md` lines:292-304：把逐输出输入解码和插值运算移到UB/Vector，地址按连续输出row分段，直接减少主体Scalar数据处理。

- diagnosis：`skills/ascendc-aprof-diagnosis/graph/problems/problem.control_metadata_overhead.md` lines:310-322：每row只算ih/h0/h1/dh，宽坐标按列计算或缓存可减少重复坐标，但仍4个GM标量读及输入解码。

- diagnosis：`skills/ascendc-aprof-diagnosis/graph/problems/problem.insufficient_input_reuse.md` lines:265-277：上采样同源行/列强复用；整2倍下采样邻居不重叠，统一驻留整源行可能多搬无用字节。

- parallel-planning：`skills/ascendc-aprof-parallel-planning/knowledge/families/indexing/templates/gather_output_owned.md` lines:104-116：Gather模板的尾轴源窗口/输出owner原则迁移到ResizeCoord生成的有界索引，未声称是GatherElements算子；取数只搬值，之后另保留四项FP32插值，强下采样源span按实址计。

- optimization：`skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/batch.md` lines:85-97：Resize按W=64/128/256有效count规划，GM范围须单独核对；逐步乘加/Cast与原手工解码的全域语义仍unknown。

- optimization：`skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/input-tile-residency.md` lines:121-133：相邻四点只是部分重叠，不能删整次第二加载；逐输出列枚举union后保留两源行共同区，强下采样pair分离时撤回驻留。

- optimization：`skills/ascendc-aprof-optimization/knowledge/branches/scalar-control/recipes/hot-loop-address.md` lines:70-82：nc/oh不变量只可提到行作用域；ow坐标仍直接FP32求值，禁止累加scale产生不同舍入，输入pair代次变化时重建窗口。

检索目录28个Problem全量审视后按源码问题展开，不用邻接top-k锁候选；D的每个候选分别绑定自己使用的Problem正文、适用依据与反证。未采用模板无需伪装已实施。

## 不能判断及后续补项

- constraint.capacity：连续源span随缩放比变化，实际UB及Gather临时区未知，需逐tile而非只按Wtile预算。
- constraint.target_api：目标SDK的UB Gather/index单位、half/bf16输入Cast、count乘加及特殊值行为未核验。
- constraint.numeric_order：原四项FP32累加顺序与源手工解码特殊值必须保留，Vector Cast/融合对NaN/Inf和bf16 round的等价需要核验。
- 性能：Vector与UB Gather是否摊薄索引准备成本、强下采样span带来额外字节是否抵消Scalar指令减少。

源事实、source refs/hash、原矩阵、R1/R2 reasoning/decision、expansion、P/O route、阅读记录均在本目录。C1按handoff/v3 schema与reasoning/decision校验；严格C2缺真实architecture与parallel/dispatch implementation绑定，未伪造。没有C3、计时结果、加速比或训练记录。

路由阶段区别：全树P/O咨询、Action绑定P候选、条件方法采用分别见route-selection-status.json；未生成正式C2 selection或C3 execution。逐项true条件的源码/数学证明见condition-audit.json。

独立复核修正：ResizeCoord索引域和四项插值表达式可由源码恢复，但手写half/BF16解码的次正规数/NaN处理与目标Cast、Vector乘加舍入/融合、正负零和Inf传播的全域等价尚未核验。完整constraint.semantic_equivalence保持unknown，不由clamp/地址证明推成true。 数学映射另有已知source.element_mapping_equivalence；条件Vector方向保留。

所有已知constraint.ref.locator现逐谓词定位condition-audit.json的basis字段，并提供原host/tiling/kernel/原oracle精确行引用；无lines:1标题充作证明。
