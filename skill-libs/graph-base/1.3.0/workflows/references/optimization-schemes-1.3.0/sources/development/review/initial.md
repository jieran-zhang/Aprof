# 独立初审

审查范围为当前未封版 graph-base 1.3.0 的完整方案/跨轮摘要文档、四 skill、四角色与 C1/C2/C3/C5 契约，以及本次独立冻结的四份原始工程。未读历史优化分析、未读八份主体回答、未改实现、未运行硬件或训练。

## 结论

完整方案与摘要正文目前没有强制多 Action、强制换 Action、默认消融或内置固定轮数。四 skill 和角色明确：先理解完整路径与比较机会；单 Action 足够时直接用；必要多成员共同计划统一资源/依赖；P/O 正文必须影响判断；后继允许相同 Action；外层提供轮次/停止/重试范围。摘要保持当前状态、已尝试路线、剩余机会三部分，且不替代证据、授权或知识晋升。机器身份检查与自然语言语义审阅被明确区分，不能仅凭字段齐全认定方案充分。

主要文档缺陷是公共契约仍写当前 handoff/v3。其他发现属于评测事实边界或本次静态评测的覆盖限制，不能据此预设主体应选择哪个 Problem、Action、方案规模或修改路径。

## 具体发现

### IR-001 [P2] 公共契约仍把新C1/C2/C3指向handoff/v3

公共契约72行明确说当前诊断及C1/C2/C3使用aprof.handoff/v3，95行只描述v3和v1历史。四skill、主workflow和各阶段contract均要求新方案action-decision/v3 + handoff/v4。公共契约是所有角色必读的唯一交接入口，因此会导出互相冲突的格式要求。

证据：`skill-libs/graph-base/1.3.0/workflows/contracts/common.md:72`, `skill-libs/graph-base/1.3.0/workflows/contracts/common.md:95`, `skill-libs/graph-base/1.3.0/workflows/aprof-performance-workflow.md:28`, `skill-libs/graph-base/1.3.0/workflows/contracts/diagnosis.md:57`。

建议：明确新方案采用v4/v3，v3交接及v1/v2决策仅按冻结语义回放；保留旧文档和schema。

### IR-002 [P2] Sum的padding虽非有效归约结果，仍属于原oracle检查范围

FACTS说8个物理元素、仅前3有效，容易漏掉后5个padding必须为零的当前样例输出约束。原实现Duplicate清零8个元素，golden为8个零数组再写前3项，CompareResult遍历outSize/sizeof(float)=8项。不得因为只有3项有效而无证明删除清零或只写3项后将其他项留未定义。

证据：`scaffolding/curation/graph-base-1.3.0-optimization-schemes/evaluation/FACTS.md:8`, `scaffolding/curation/graph-base-1.3.0-optimization-schemes/evaluation/sources/reduction_sum/sum.asc:110`, `scaffolding/curation/graph-base-1.3.0-optimization-schemes/evaluation/sources/reduction_sum/sum.asc:178`, `scaffolding/curation/graph-base-1.3.0-optimization-schemes/evaluation/sources/reduction_sum/scripts/gen_data.py:60`。

建议：评分时检查完整物理输出和oracle；允许等价地只清零padding等方案，但需证明Sum写入范围与依赖，不能按预选Action扣分。

### IR-003 [P2] Maximum的FP16广播专用路径没有通用广播适用保护

FP16任意非sameShape都走专用路径，实际寻址固定x1[off]和x2[off % outLastAxis]。矩阵唯一FP16广播case18满足这一结构；host tiler却接受一般broadcast。比如x1=[2,1],x2=[1,3]合法输出[2,3]，专用路径会把只有2个元素的x1按6元素访问。因此FACTS应被理解为当前路径说明，不能当作通用FP16广播正确性已经成立。

证据：`scaffolding/curation/graph-base-1.3.0-optimization-schemes/evaluation/FACTS.md:6`, `scaffolding/curation/graph-base-1.3.0-optimization-schemes/evaluation/sources/maximum/op_kernel/maximum_kernel.asc:91`, `scaffolding/curation/graph-base-1.3.0-optimization-schemes/evaluation/sources/maximum/op_kernel/maximum_kernel.asc:109`, `scaffolding/curation/graph-base-1.3.0-optimization-schemes/evaluation/sources/maximum/op_kernel/maximum_kernel.asc:158`, `scaffolding/curation/graph-base-1.3.0-optimization-schemes/evaluation/sources/maximum/op_kernel/maximum_tiling.h:43`, `scaffolding/curation/graph-base-1.3.0-optimization-schemes/evaluation/sources/maximum/scripts/cases.py:20`。

建议：对声明全API范围的方案单独说明这一现存缺口；若只覆盖20case则标明范围。不能要求主体修复本轮范围以外的原始工程，也不能奖励虚称通用覆盖。

### IR-004 [coverage_limit] 一轮静态no-tools回答不能验证真实跨轮更新或router/contract执行

两次重复使用同一个独立一轮prompt，只要求输出下一轮可复用摘要；没有回传前轮失败/实际patch/有效或无效结果再要求后继重比较。材料只静态展开skills及三份reference、全部O/Problem、family P，没有执行角色contract读取、router或handoff回放。retrieval_cost_evaluated=false与no-tools限制已有正确声明。

证据：`scaffolding/curation/graph-base-1.3.0-optimization-schemes/harness/prepare.py:29`, `scaffolding/curation/graph-base-1.3.0-optimization-schemes/harness/prepare.py:46`, `scaffolding/curation/graph-base-1.3.0-optimization-schemes/harness/prepare.py:61`, `scaffolding/curation/graph-base-1.3.0-optimization-schemes/PROTOCOL.json:6`, `scaffolding/curation/graph-base-1.3.0-optimization-schemes/evaluation/FACTS.md:12`。

建议：八份输出只评价静态方案质量、知识实质采用和摘要初始内容；跨轮真实更新、按需阅读效率、真实逐成员路由和机器兼容性分别标未覆盖，交由后继场景和runtime检查，不以没调用工具为技术扣分。

### IR-005 [evaluation_note] 五维0/1/2缺少锚点和失败项对总分的处理规则

当前列出五维与单列失败项，但未规定每维0/1/2含义、明确错误怎样影响对应维度、是否有总体验收阈值。若要报告验收结论，单纯总分容易掩盖越界/API/数值错误，且不能把Action数、多Action或换Action变成隐含加分。

证据：`scaffolding/curation/graph-base-1.3.0-optimization-schemes/evaluation/FACTS.md:10`。

建议：匿名评审先逐维列证据和具体错误；0=关键缺失/冲突，1=有可用判断但缺会影响选择的具体环节，2=关键判断与源码/方法/代价充分相连。单列明确失败，不用总分抵消。无硬件测量、单Action、无变更或有条件方案不自动扣分。

## 四份原始事实独立核对

- GridSampler3D：`linear/spatialOut` 决定 N/C，`linear%spatialOut` 决定输出空间；grid 三元坐标同 batch/spatial 跨 channel 可共享，但现有 flat 输出分核没有共同 owner 保证。FP16 `GridToFloat` 手工位解码、X 随机标量读、坐标/权重/八项累加主要为 Scalar；FP16 外围 1024 tile 上的 Cast 和批量写回不代表主体已 Vector 化。三线性顺序、nearest ties-to-even、zero/border/reflection、alignCorners 及 NaN/Inf mask 属于数值约束。没有按此事实预选任何 Action。定位：kernel:8,98,125,143,170；tiling:40；definition:19,28；verify_result:29,35。
- Maximum：int64 无条件进入 Scalar，即便 sameShape；其他 dtype 的 sameShape 为既有批量路径，BF16/int8 含转换；FP16 非 sameShape 走专用内轴段路径，其适用边界见 IR-003。其余广播每输出逐 rank 解码，再标量选值。整数全值域和浮点 NaN/Inf 不能被测试小值范围或窄化替代；Vector 方法的精度、可用 dtype、尾块、转换和临时存储需逐项核对。定位：kernel:44,50,125,156；verify_result:18,21；tiling:37,43。
- Transpose：输出 flat owner，各元素 rank 次除模求输入位置；1/2/4/8 字节 Raw 搬运，oracle 逐位比较。二维块转置可为有条件方案，但不能把全部 rank/permutation 宣称覆盖；高 rank 含连续后缀的域也要按真实连续性论证。定位：kernel:7,16,28；tiling:21；definition:6；verify_result:6,15。
- Sum：固定 FP32 输入 3×32=96 元素，单核，输入/输出队列深度均1，一次 CopyIn→Sum→CopyOut。原输入384字节，物理输出32字节，另有 GetSumMaxMinTmpSize 返回的 scratch；不能未经 API 证明把 scratch 置零。5个 padding 的 oracle 约束见 IR-002。定位：sum.asc:50,87,91,110,116,157,178；gen_data.py:46,60。

29 个 evaluation/inputs.json 所列源码文件的 SHA256 全部核对一致。四种 workload 数量分别为20、20、20、1；未使用任何原优化结论或预选答案。

## 后续审查

等待 runtime 实现完成通知后检查新 schema/决策/bindings v4 的实际绕过路径、逐实例条件、保证依赖、旧版本兼容和性能/安全分离。等待匿名材料后按五维证据评八份 no-tools 回答，技术评分不以 Action/Key 数量、换动作、未测硬件或预定方案为标准。

未检查：新 runtime 代码和测试、八份主体输出、真实硬件正确性/性能。当前结论只覆盖静态文档、原始事实及评测协议。
