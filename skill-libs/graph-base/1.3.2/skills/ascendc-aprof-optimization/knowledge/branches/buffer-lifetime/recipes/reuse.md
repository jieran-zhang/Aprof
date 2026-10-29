---
schema_version: aprof.knowledge-record/v1
id: implementation.buffer-lifetime.reuse
kind: recipe
version: 1.2.0
status: active
title: 存活期、合法复用与 UB 布局核验
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/common/ub_resident_design.md
  original_path: ops/ascendc-performance-best-practices/reference/common/ub_resident_design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 342
  sha256: sha256:422c329fdf4dcb62d095afc88371f7bb44f51aa624398cc977cdc0e995b8d5e3
  excerpt_sha256: sha256:422c329fdf4dcb62d095afc88371f7bb44f51aa624398cc977cdc0e995b8d5e3
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/resource_management/TPipe/InitBuffer.md
  original_path: docs/zh/api/SIMD-API/basic_api/resource_management/TPipe/InitBuffer.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 34
  - 220
  sha256: sha256:36da88132f7d5f62484bc98896bd99577bcce25d71a84e21220731a557aea34d
  excerpt_sha256: sha256:70619eed307e130c5d64b3936d3c609e096c608ba0b6bba136e773385fe5bd2d
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/resource_management/TBuf/Get.md
  original_path: docs/zh/api/SIMD-API/basic_api/resource_management/TBuf/Get.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 34
  - 98
  sha256: sha256:23ef70d79cf63af9b179082dc436f6fc80c6441a050e3a7600838af3cd94617a
  excerpt_sha256: sha256:7ddd61b3e98c4e594924b5e620a362b82b9ad4fe81310f3956d9afcacd73dded
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/00_vector_compute/add_high_performance/add.asc
  original_path: examples/01_simd_cpp_api/05_best_practices/00_vector_compute/add_high_performance/add.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 27
  - 345
  sha256: sha256:f7d075958365a8fc1af9879e90ab6494573f8869d3a538832c537d8e0f905042
  excerpt_sha256: sha256:d2b85d269202c81ba81366f010df36bf3c512f17f84bd0b145c0dd1425e49cda
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 31
  - 144
  sha256: sha256:a41ac2ff57f181c342d823a1b453bfabfb20c56bf840e31f4dff7232cefdc80a
  excerpt_sha256: sha256:9b82f521bfc25b8c16cea361e35e230d057580630377745c5a4a099d56a39447
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/posembedding/rotary_position_embedding/op_host/rope_interleaved_tiling.cpp
  original_path: posembedding/rotary_position_embedding/op_host/rope_interleaved_tiling.cpp
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 395
  sha256: sha256:0f2bac0d6cd52e57ef38976b7fb8205e3104f2e0ea26f3689f0be1dd0a09cec6
  excerpt_sha256: sha256:0f2bac0d6cd52e57ef38976b7fb8205e3104f2e0ea26f3689f0be1dd0a09cec6
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/posembedding/rotary_position_embedding/op_kernel/rotary_position_embedding.cpp
  original_path: posembedding/rotary_position_embedding/op_kernel/rotary_position_embedding.cpp
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 291
  sha256: sha256:5160d08c053ba32694df0c699d31ddc9b67a26d3ae4545f4fb9d6122efc3400e
  excerpt_sha256: sha256:5160d08c053ba32694df0c699d31ddc9b67a26d3ae4545f4fb9d6122efc3400e
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/posembedding/rotary_position_embedding/op_kernel/rotate_interleaved_split_bs.h
  original_path: posembedding/rotary_position_embedding/op_kernel/rotate_interleaved_split_bs.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 299
  sha256: sha256:92e2365907ffbd499d113d173a67bd2ade41d1a92d82f3d20b3965eaad17b001
  excerpt_sha256: sha256:92e2365907ffbd499d113d173a67bd2ade41d1a92d82f3d20b3965eaad17b001
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/posembedding/rotary_position_embedding/op_kernel/rotate_interleaved_common.h
  original_path: posembedding/rotary_position_embedding/op_kernel/rotate_interleaved_common.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 145
  sha256: sha256:564521918a374297b74d8bdfad264bcd8359c0be3689188e0ac83490de4360e1
  excerpt_sha256: sha256:564521918a374297b74d8bdfad264bcd8359c0be3689188e0ac83490de4360e1
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/scalar/coding_principles.md
  original_path: ops/ascendc-performance-best-practices/references/common/scalar/coding_principles.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 478
  sha256: sha256:a387544bac3f38ad940fae2930e75c9f7cda45c8e25324f4cd864bee1ce4827c
  excerpt_sha256: sha256:a387544bac3f38ad940fae2930e75c9f7cda45c8e25324f4cd864bee1ce4827c
learning: {}
tags:
- alias
- capacity
- static-allocation
- ub-lifetime
seed_reason: 审读固定开源修订并提炼中文实现配方，保留既有 ID 语义；API 单位以实际 API 文档为准；未做目标 SDK 编译或 NPU 性能验证。
parent: implementation.buffer-lifetime
references:
- implementation.buffer-lifetime.arch22-bank-layout
- implementation.tiling-tail.valid-length
evidence_status: source_reviewed_not_benchmarked
---
# 按最后消费者安排合法复用与 UB 布局

## 原理与适用条件

相同 UB 字节可在互不重叠的生命周期中承载不同临时值，减少显式静态分配或给更大的 tile 留出空间。优化对象是物理存储分配和完成边，不是 C++ 变量的词法作用域。输入是 C2 已选数据流、dtype、精度、tile、队列深度与可调布局；不能以减少临时区为由改为低精度累计、改变归约顺序或丢弃必需中间状态。

对每个逻辑值标注 `(producer, 所有consumer, 最后完成事件, bytes, 对齐, API是否允许原地/重叠)`。存活从第一次 DMA/计算写入开始，直到最后一次异步读取消费完成。输入已经 `DeQue` 不代表读取完成，输出发出 DataCopy 不代表 MTE3 已读完；`FreeTensor` 必须服从所用队列的合法生产/消费协议。跨 tile 的 accumulator、广播参数和重用索引表可能比单个 tile 活得更久。

## 容量模型：区分下界与实际分配

令 `Ai=AlignUp(bytes_i,32)`，若使用更严格的 API 对齐或 bank padding 则按实际扩大。`L=max_t Σalive_i Ai` 只是理想可共享安排的活跃字节下界。多个独立 `InitBuffer` 的静态内存不会因为其用途不同时刻自动重叠；其分配量仍按每次分配和槽数累加，除非工程明确把它们映射到同一个受控 arena/TBuf。只有真正复用一段存储，才能将串行 A/B 的 `A+B` 降到 `max(A,B)`。

```text
queueBytes = Σqueues numSlots × AlignUp(slotBytes,32)
otherBytes = Σ独立TBuf AlignUp(len,32) + API workspace + 显式padding
arenaBytes = max_i(offset_i + allocatedSpan_i) // 自定义地址布局的高水位
UB需求 = 不重叠独立分配之和；共享arena只能计一次但必须完整占有
```

转换 dtype 后重算字节：half输入T元素为`2T`，float中间量T元素为`4T`，不能复用旧元素容量字段。InitBuffer 的 len 单位是字节，`TBuf::Get<T>(len)` 的 len 单位是元素，`len*sizeof(T)` 必须不超过分配长度。双缓冲增加的是实际物理槽数，不只是把队列模板深度改成2。

## 实现顺序和片段

先复用确定串行且不跨 DMA 的临时值，再评估其他阶段；保留原独立区作为正确性对照。每对复用值必须有最后读完成→下一次写开始的真实完成边；如果靠全流水 barrier 才能释放，记录由此失去的 overlap，不能只报告节约容量。原地操作另须核对具体计算 API 的重叠约束，即使生命周期图无冲突也不能推定任意部分重叠合法。

下面是“两个串行阶段共用临时区”的 float 示例。`pipe` 是本 kernel 唯一的 `TPipe`；`nA,nB>0` 是已合法的元素数。`xA,yA,xB,yB` 都是已就绪、容量分别足够的 `LocalTensor<float>`，彼此及 scratch 不重叠；示例数学分别为 `yA=xA*xA+xA`、`yB=xB*xB+xB`。只在实际 C2 数学正好包含这些操作时移植；此处用保守完成边展示交接，不构成业务算法改写。

```cpp
const uint32_t maxCount = nA > nB ? nA : nB; // 元素；Host 已防乘法溢出
const uint32_t scratchBytes = (maxCount * sizeof(float) + 31) / 32 * 32;
AscendC::TBuf<AscendC::TPosition::VECCALC> scratch;
pipe.InitBuffer(scratch, scratchBytes); // 在 Init 阶段一次分配，字节
auto temp = scratch.Get<float>(maxCount); // 同一物理区的视图，元素
AscendC::Mul(temp, xA, xA, nA);
AscendC::PipeBarrier<PIPE_ALL>(); // 保守表达第一个producer完成
AscendC::Add(yA, temp, xA, nA);
AscendC::PipeBarrier<PIPE_ALL>(); // temp 的阶段A最后消费者完成
AscendC::Mul(temp, xB, xB, nB); // 现在才允许覆盖temp
AscendC::PipeBarrier<PIPE_ALL>();
AscendC::Add(yB, temp, xB, nB);
// 后续写回继续使用工程原来合法的 Vector -> MTE3 同步。
```

这段没有新增热循环分配。实际工程把 InitBuffer 移到既有 Init 位置，并用其已有的合法队列/事件协议表达同样依赖；缩窄或移除保守 barrier 必须有对应 API/同步证据，不能默认编译器解决跨引擎依赖。若两阶段需要同时流水，则两个逻辑值仍同时存活，应保留两槽。

## 布局、验证与失败回退

布局偏移按字节对齐递增，`Get<T>` 切片按元素解释；记录每段 `[offset,offset+span)`，检查并发存活段不相交、末端不超目标实际可用 UB。为避 bank 加 padding 时重新计算所有后继 offset、高水位和可用 tile；arch22 的详细地址候选见 `implementation.buffer-lifetime.arch22-bank-layout`，不从 arch35 搬常量。

覆盖单tile/多tile、两阶段不同长度、最后短tile、重复运行、所有dtype路径及跨tile状态。偶发错误常说明异步消费者未结束；形状越大越错常说明容量/元素单位混淆。先恢复独立 buffer 和原完成边验证，再局部重做共享，不能以加大 UB 上界掩盖越界。收益看实际静态分配、最大tile与Task；省UB但串行化热点可能劣化。

来源事实：InitBuffer/Get 文档给出字节/元素契约；Add 实例用 V_MTE2、MTE3_V 表达输入和输出槽最后消费者。生命周期模型、下界与静态分配的区分、串行 polynomial 片段是工程提炼；没有目标 SDK 编译和 NPU 性能证明。

## 区分“复用同一地址”与“保留同一个值”

本条的主意图是串行生命周期共享存储；若一个值将被多次消费，保留它会延长生命周期，反而减少可共享空间。分别记录原始输入值、派生表/转换值和可重算标量：输入重复读取减少的是相应存储层访问；派生值复用减少构造或转换，不一定减少原始tensor流量；多个临时值共用地址只减少分配峰值，可能并未减少计算。

设派生状态每tile有Q个元素、每元素s字节、复用r次。重算做r次构造；保留做1次构造及r次读取，显式驻留至少`AlignUp(Q*s,32)`字节，再加槽/metadata。构造次数减少`r-1`，但缓存后tile若变小、任务更少或访问更离散，收益可能反转。UB字节可以精确预算；Scalar自动数组的寄存器/栈/spill只有编译结果才可确认，不把数组声明字节直接加进UB。

固定ops-transformer RoPE SplitBS在Process前构造一次Gather偏移表供各seq/batch迭代使用，保留`headDim*numHeads*sizeof(int32_t)`的索引区；host按dtype及转换临时区选择可容纳的批量范围。它同时复用cos/sin的临时地址，通过V→MTE2完成边等待前值最后消费。前者是值复用，后者是存储复用，不能合并成“都省输入”。该源码只支持所示RoPE布局和分派，不能直接证明任意采样坐标算法的数值等价。

若要把计算迁到外层、改变复用轴或扩大owner域，先确认C2和Action意图覆盖；`hoist_invariant_control`不自动授权任意数学状态预计算，`reuse_input_tiles`也不自动代表派生几何复用。派生状态采用独立action.reuse_derived_results，管理简化采用独立action.simplify_buffer_event_management（均须经独立复核的冻结注册版本）；条件不满足时保留机会/提案，不借旧Action通过交接。

> 文档适配说明：本页已规范代码文字格式；来源和历史回放使用[保留的证据原文](../../../../../../sources/document-originals/fc54fa89be01819a42bfa96c981991188191e0fc5bebf127b49303f03ce98a48.txt)。
