# case-11 foreach_addcdiv_scalar：无硬件两轮自主分析

选定 `action.software_pipeline_stages`，R1/R2均为conditional_plan。R1未生成候选源码，R2只补静态证据；性能not_measured。原20case全部纳入成本与回归范围，特化适用case=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20；其余保留原fallback。

目标910C/A3→dav-2201只表示任务声明的目标适用域，依据platform-basis.json；不是硬件探测。实际SKU/可见核/可用UB/SDK/API支持均未伪造。

## R1具体方案

保留TensorList逐tensor、8Mi元素host chunk、每元素Div→Muls→Add及原Cast。核内用U∈{1024,2048,4096}、输入/输出物理槽d∈{1,2}；首轮CopyIn(0)，DeQue后允许CopyIn(1)，按队列契约交错计算与搬出，末轮drain。d=2仅用于本核tileCount≥2且8*A(U*s)+4*A(4U)*(s!=4)+R≤UB_available；单tile保留d=1。不把模板depth和物理num混为一谈。

## 机会比较

- action.software_pipeline_stages（selected，case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：跨tile预取释放单槽依赖，必要GM流量仍为4Ns，代价是更多raw槽及序言尾声。
- action.reuse_disjoint_onchip_buffers（deferred，case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：将Div后的fc区用于之后Cast(a)可从四FP32 scratch降至三块，但需先延后Cast(a)并核对API alias/事件；尚未知道容量是否限制tile。
- action.coalesce_cast（rejected，case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：三输入各只扩位一次、输出只缩位一次；删除Cast会变更FP32除法路径，case12/13异常值不允许用scalar特化跳过算术。

## 全20case源码成本

以下为逻辑字节/源码操作计数，不是HBM实测，也不能换算为时延。完整shape、dtype、分发与其他成本列见R1-source-costs.json。

| case | dtype | 输出元素数 | 逻辑GM读写字节 | 结构差异 |
|---|---|---:|---:|---|
| 1 | float32 | 2097152 | 33554432 | host launch=2; UB2048=32768B |
| 2 | float16 | 12582912 | 100663296 | host launch=3; UB2048=49152B |
| 3 | bfloat16 | 16777216 | 134217728 | host launch=2; UB2048=49152B |
| 4 | float32 | 67108864 | 1073741824 | host launch=8; UB2048=32768B |
| 5 | float16 | 67108864 | 536870912 | host launch=8; UB2048=49152B |
| 6 | bfloat16 | 1046529 | 8372232 | host launch=1; UB2048=49152B |
| 7 | float32 | 1030189 | 16483024 | host launch=1; UB2048=32768B |
| 8 | float16 | 1181953 | 9455624 | host launch=1; UB2048=49152B |
| 9 | bfloat16 | 99382866 | 795062928 | host launch=12; UB2048=49152B |
| 10 | float32 | 1051137 | 16818192 | host launch=1; UB2048=32768B |
| 11 | float16 | 2184546 | 17476368 | host launch=2; UB2048=49152B |
| 12 | float32 | 1000003 | 16000048 | host launch=1; UB2048=32768B |
| 13 | bfloat16 | 10912759 | 87302072 | host launch=2; UB2048=49152B |
| 14 | float32 | 3042039 | 48672624 | host launch=1; UB2048=32768B |
| 15 | float32 | 2098176 | 33570816 | host launch=2; UB2048=32768B |
| 16 | bfloat16 | 8356860 | 66854880 | host launch=4; UB2048=49152B |
| 17 | float16 | 2093567 | 16748536 | host launch=1; UB2048=49152B |
| 18 | float32 | 4188156 | 67010496 | host launch=2; UB2048=32768B |
| 19 | bfloat16 | 2089980 | 16719840 | host launch=1; UB2048=49152B |
| 20 | float32 | 10549248 | 168787968 | host launch=2; UB2048=32768B |

## R2新增静态证据与条件后继

逐20case重新计算chunk数与尾长，所有tensor均远大于U，但真实每核循环次数依赖C_available。d=2且U=2048时FP32数据65536B，16bit数据65536B（raw32768+scratch32768）；U=4096需131072B。这个值是候选字节需求，不是设备容量。若所查可用UB不足，先保持U=2048并降d；若timeline已充分重叠则撤回加槽，转向有合法alias依据的scratch复用。

没有R1性能结果可支持/否定加速；前轮源工作预测只获得公式/地址适用性的静态支持，没有声称编译器已生成更少指令。R2-static-evidence.json给出每个case检查对象和结果。

## 实际阅读与采用

P/O全树咨询与Action绑定P路由回执均已保存；以下是条件方法采用，未形成正式C2 selection或C3执行。

- diagnosis：`skills/ascendc-aprof-diagnosis/graph/problems/problem.pipeline_serialization.md` lines:285-297：跨tile预取释放单槽依赖，必要GM流量仍为4Ns，代价是更多raw槽及序言尾声。

- diagnosis：`skills/ascendc-aprof-diagnosis/graph/problems/problem.onchip_capacity_pressure.md` lines:320-332：将Div后的fc区用于之后Cast(a)可从四FP32 scratch降至三块，但需先延后Cast(a)并核对API alias/事件；尚未知道容量是否限制tile。

- diagnosis：`skills/ascendc-aprof-diagnosis/graph/problems/problem.redundant_cast.md` lines:303-315：三输入各只扩位一次、输出只缩位一次；删除Cast会变更FP32除法路径，case12/13异常值不允许用scalar特化跳过算术。

- parallel-planning：`skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md` lines:78-90：连续输出模板要求每输出唯一owner与总分配预算；保留host chunk和现有所有权，双raw槽+四FP32 scratch按65536B(U=2048)计，不把活跃下界当物理分配。

- optimization：`skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md` lines:62-74：foreach中物理num=2与depth=1分别计；每次DeQue后再预取，并闭合输入最后读和MTE3读完后的回收；SDK队列能力另为unknown。

- optimization：`skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md` lines:62-74：foreach中物理num=2与depth=1分别计；每次DeQue后再预取，并闭合输入最后读和MTE3读完后的回收；SDK队列能力另为unknown。

- optimization：`skills/ascendc-aprof-optimization/knowledge/branches/buffer-lifetime/recipes/reuse.md` lines:80-92：独立InitBuffer不因词法作用域而自动共享；foreach只有重排Cast(a)并物理合并fc/fa后才从四FP32区降至三，目标API alias与完成边须核对。

检索目录28个Problem全量审视后按源码问题展开，不用邻接top-k锁候选；D的每个候选分别绑定自己使用的Problem正文、适用依据与反证。未采用模板无需伪装已实施。

## 不能判断及后续补项

- constraint.capacity：缺实际可用UB及编译器/API预留R；需比较候选65536/131072B加R而非把配置示例当实值。
- constraint.target_api：目标安装SDK的TQue物理num=2、depth=1交错EnQue/DeQue与尾DataCopyPad支持尚未核验。
- 性能：当前单槽循环的DMA/Vector是否已有编译调度重叠，Div是否主导，额外槽/较短tile是否增大控制成本。

源事实、source refs/hash、原矩阵、R1/R2 reasoning/decision、expansion、P/O route、阅读记录均在本目录。C1按handoff/v3 schema与reasoning/decision校验；严格C2缺真实architecture与parallel/dispatch implementation绑定，未伪造。没有C3、计时结果、加速比或训练记录。

路由阶段区别：全树P/O咨询、Action绑定P候选、条件方法采用分别见route-selection-status.json；未生成正式C2 selection或C3 execution。逐项true条件的源码/数学证明见condition-audit.json。

所有已知constraint.ref.locator现逐谓词定位condition-audit.json的basis字段，并提供原host/tiling/kernel/原oracle精确行引用；无lines:1标题充作证明。
