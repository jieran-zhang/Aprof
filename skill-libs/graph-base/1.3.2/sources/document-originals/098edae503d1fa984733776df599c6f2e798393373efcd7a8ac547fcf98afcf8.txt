---
schema_version: aprof.knowledge-record/v1
id: implementation.pipeline-sync.slots
kind: recipe
version: 1.1.0
status: active
title: Workspace 槽、任务描述符与跨阶段所有权
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/fused_infer_attention_score/op_kernel/arch22/fia_kernel_nonquant.h
  original_path: attention/fused_infer_attention_score/op_kernel/arch22/fia_kernel_nonquant.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 95
  - 1120
  sha256: sha256:f9329654b3966cbb62b4f23c4d6d91cd2fcc48335a58915075f9f52184f4f837
  excerpt_sha256: sha256:51be295b11320b07caaffe8c601255e1c445fa184612fe67e19ed521696afd4b
- path: skills/ascendc-aprof-optimization/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/flash_attention_score/op_kernel/arch22/flash_attention_score_s1s2_bn2gs1.h
  original_path: attention/flash_attention_score/op_kernel/arch22/flash_attention_score_s1s2_bn2gs1.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 399
  - 1100
  sha256: sha256:e739820e172fa26ae73c802ad8ca2ceabb1080ee9dd1e3c2c8226d08f7d6e34a
  excerpt_sha256: sha256:4a9a63533fd44f30032a770d25255ed92d8912b97484c2feea89c38fe62a081f
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md
  original_path: ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 155
  sha256: sha256:ea3be814234904a2d8a4a3b99847aec00c849f3fb3ce2647390a3dce0a734ba1
  excerpt_sha256: sha256:ea3be814234904a2d8a4a3b99847aec00c849f3fb3ce2647390a3dce0a734ba1
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md
  original_path: docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 28
  - 151
  sha256: sha256:69845e8fa794040e321959eaa57105a79cdf880c2d9460b7bf65a53f3c644827
  excerpt_sha256: sha256:02edbe3918b020be18c5b07b81c9bc18153e3f3ab7ba41a9962391c7173aa399
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md
  original_path: docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 28
  - 151
  sha256: sha256:fb6098e64301d056e53eb0f083dcc96083075fc8da78409492f905653c311f96
  excerpt_sha256: sha256:c5145c71c4361eef7d3e7a5597dfa8bc235c92153767ab8322ebee5109ed0b5d
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: implementation.pipeline-sync
references:
- implementation.pipeline-sync.pipeline
- implementation.buffer-lifetime.reuse
- implementation.fusion-composition.cv_multistage_handoff
evidence_status: source_reviewed_not_benchmarked
---

# Workspace 槽、任务描述符与跨阶段所有权

## 核心原则与适用条件

slot 不是一个通用取模数字，而是某类对象在其完整生存期内的存储租约。跨 AIC/AIV 的中间结果、跨 s2 的在线状态、三阶段的任务描述符、L1 ping-pong 即使都用 `%2/%3`，仍属于不同的索引空间。只有最后一个异步读者完成，租约才结束。

适用于 C2 已确定融合 region、逻辑 task、AIC/AIV 配比、workspace 划分和阶段依赖的 FA/FIA、split-K 或复杂 CV kernel。C3 可以落实每槽的 offset、代次和 ready/free，但不能自行把 task 改成另一个维度、增加跨核消费者，或把 GM 中转换成 UB 直通；遇到这些需求返回 C2。对普通单 tile Vector，应先使用 TQue，不为简单实现新增多种全局槽。

## 先建生产者—消费者表

下表是**本文抽象**，列名不要求工程使用同名成员。每一行需在当前源码中定位真实对象和同步边。

| 槽域 | 数据 | 写者 | 读者 | 首轮初始化 | 释放条件 |
|---|---|---|---|---|---|
| handshakeSlot | QK scores / P / PV 中间块 | C1 / V1 / C2 | V1 / C2 / V2 | ready计数空、free允许首写 | 对应阶段读完本块；有两个AIV时包含双方 |
| taskStateSlot | shape、offset、tail、stage有效位 | task创建方 | C1、V1、C2、V2调度 | 全部invalid | 最后一阶段不再引用描述符 |
| selfRefSlot | running max/sum、重标定因子、Oacc | 同query的前一s2阶段 | 后续s2/V2与最终输出 | m=-∞、l=0；Oacc初始化或首块专门分支 | 同query最终s2及输出完成 |
| L1RotationSlot | Q/P、K/V大包 | MTE2 | MTE1 | free已预置 | 大包最后一次LoadData读完 |
| L0RotationSlot | baseK A/B及L0C累加 | MTE1/Cube | Cube/Fixpipe | free已预置 | 最后一次Cube读或Fixpipe读完 |

`-∞` 是 running max 的数学初值，不意味着全mask行可任意用 `-∞-(-∞)` 计算。mask、全无效行和空KV的输出语义必须沿用原oracle，独立判断是否跳过阶段并保留合法通知。

## 用区间与代次求槽深度

对象 i 的占用区间为 `[acquire_i, release_i)`，release 包含真实异步消费者完成。最小槽深度至少是任意时刻的最大存活数：

```text
domainDepth >= max_time count(i : acquire_i <= time < release_i)
slot(seq) = seq % domainDepth
generation(seq) = seq / domainDepth
addr(core,seq) = base + core*coreStride + slot(seq)*slotStride
end = addr + slotBytes <= regionEnd
```

取模只分配地址，不提供同步。重用前必须证明旧 generation 已释放；event 本身通常不携带代次，代次由确定的发射/等待顺序或调试元数据保证。HardEvent 的不同事件类型可有独立的 ID 命名空间，须按目标 API 核验；CrossCore 则不能按 mode 划分独立资源：同一核每个 flagId 对应一个计数器，切换 mode 前必须完成旧 mode 的全部 Set/Wait，禁止同一 flagId 跨 mode 同时存活。不要把某类事件的复用规则推广到另一类；`PIPE_ALL` 或 `volatile` 不能替代跨核可见性与通知。

令 C 为逻辑AIC组合数，S/P/O/U 四类中间张量每槽元素数分别为 E_S/E_P/E_O/E_U，字节 e_S/e_P/e_O/e_U，槽深分别 d_S/d_P/d_O/d_U。本文给出的保守布局预算为：

```text
coreStride = dS*align(ES*eS,aS) + dP*align(EP*eP,aP)
           + dO*align(EO*eO,aO) + dU*align(EU*eU,aU)
workspace = C*coreStride + flashDecodePartials + layout/featureExtra
metadataBytes = taskDepth * sizeof(TaskDescriptor)  # 不混进数据槽字节
```

若采用按类型先排所有core的布局，则每类区域分别占 `C*d_j*slotStride_j`；偏移公式不能与按core排布混用。shape、dtype、对齐、Split-KV、post-quant或Rope改变后都须重算。槽区间两两不重叠，且全量包含在Host声明workspace中。

## arch22 源码事实：3份描述符不等于3份中间结果

S1 的 FIA arch22 `PRELOAD_NUM=2`，`FIA_PRELOAD_TASK_CACHE_SIZE=3`。`InitWorkspace` 为 mm1、vec1、mm2、vec2 分别按 `GetBlockNum()*2*elements*sizeof(type)` 推移区域；task缓存则用3份 RunInfo。`ExecuteTask` 在节拍t发 C1(t)，发 V1/C2(t-1)，再发 V2(t-2) 并使该描述符 invalid。因此不能因描述符 `%3` 就把 GM 数据槽也改成 `%3`，反过来也不能把描述符压成2份而覆盖仍供V2使用的offset。

S2 的 FA arch22 同样存在 `extraInfo[taskId%3]` 与 `taskIdMod2` 的分离，并按输入类型/格式为BMM1/Vec1分配不同workspace倍数。这些是具体实现事实，不能推广为所有 FA 固定用两份或三份。S3要求buffer深度、事件、地址、退出路径一起闭合；设计文档中针对其它架构的默认PRELOAD值只可作候选。

## 可执行的索引片段与排程模型

下面是普通 C++ 索引逻辑，可放进既定kernel的标量路径；`uint64_t` 避免多核大shape的偏移乘积在32位先溢出。深度、stride和region大小均由Host预先验证为正且无溢出，所有偏移以字节计，GlobalTensor下标另转换成元素单位。

```cpp
const uint64_t dataSlot = stageSeq % dataDepth;
const uint64_t taskSlot = taskSeq % taskDepth;
const uint64_t stateSlot = querySeq % stateDepth;
const uint64_t l1Slot = packageSeq % l1Depth;
const uint64_t dataByteOffset = regionBaseBytes
    + uint64_t(logicalCoreId) * coreStrideBytes
    + dataSlot * dataSlotStrideBytes;
// 不能以taskSlot替换dataSlot；合法地址仍须等待旧代消费者完成。
```

下面是**契约伪代码**；阶段函数和租约操作需由当前工程的公开SDK API实现，不依赖来源仓库私有服务类。

```text
create(task):
    require descriptor_slot(task) no longer referenced by any stage
    write immutable offsets, valid lengths, query id, first/last flags
    mark descriptor valid
produce(stage,task):
    wait old generation of data_slot(stage,task) released
    write all valid elements and prescribed padding
    publish ready after actual producer pipeline completes
consume(stage,task):
    wait corresponding ready
    read only descriptor's valid region
    publish released after last asynchronous reader completes
retire(task):
    require final stage and any state writeback complete
    invalidate descriptor; keep query state until its final s2 finishes
```

## 双AIV、空任务与进展证明

C:V=1:2不是两方可以重复写同一完整tile。按C2契约确定 `logicCoreId`、`subId` 和两份互不重叠的行区间；奇数M可用 `start=floor(subId*M/2), end=floor((subId+1)*M/2)` 推导所有权，但相应Fixpipe布局和API是否接受需单独验证，不能只改数学索引。两个AIV都参与的 mode2 回传必须有两个生产者；不能让其中一个提前return而另侧永等。对无任务core、mask跳过、空KV、drain，列出双方是否仍发送/消费通知。

S4的官方说明中，mode2 是AIC与所有AIV；A2/A3的Wait参数不参与硬件指令，默认Wait可正常配合源码中的Set<2>。评审应核对真实模式、参与核和通知数量，不能由模板文字不一致直接判死锁。950 mode4及单AIV独立flag映射属于另一能力范围，不能带入dav-2201路径。

## 验证与回退

至少跨越数据深度与描述符深度的最小公倍数，例如2和3时执行超过6个任务并再重复；覆盖同query多s2、query切换、尾M/N/K、Split-KV首末分片和空任务。静态核对每区字节上界、每槽读写序列、每代通知计数；动态结果按原oracle全case检验，性能在正确后才测。

周期性错、只在多s2错、回卷后挂起，优先保留该case并检查租约和状态，不加缓冲掩盖。回退到C2允许的串行发布/消费或更浅流水；若修复需要增加workspace、改变核参与关系或state所有者，交回C2。

## 固定来源与证据级别

- S1：[attention/fused_infer_attention_score/op_kernel/arch22/fia_kernel_nonquant.h](../../../sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/fused_infer_attention_score/op_kernel/arch22/fia_kernel_nonquant.h)，行 95–1120；修订 `d7e6a7c6c1450c040049486845336c77f3100406`。
- S2：[attention/flash_attention_score/op_kernel/arch22/flash_attention_score_s1s2_bn2gs1.h](../../../sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/flash_attention_score/op_kernel/arch22/flash_attention_score_s1s2_bn2gs1.h)，行 399–1100；修订 `d7e6a7c6c1450c040049486845336c77f3100406`。
- S3：[ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md](../../../sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md)，行 1–155；修订 `41377d0a442cd5b1c2356874873a3dda591c6633`。
- S4：[docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md](../../../sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md)，行 28–151；修订 `d378849769f9ee610af9d0ac38db2b3b6bed3209`。
- S5：[docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md](../../../sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md)，行 28–151；修订 `d378849769f9ee610af9d0ac38db2b3b6bed3209`。

来源事实、本文推导与待验证项在正文分别标注。冻结源码及仓库许可证随包保存；本次仅完成审读，未在目标 SDK 构建，未运行 NPU 正确性或性能测量。源码存在不代表当前 shape 已分派到该路径，任何收益都须由当前候选的完整正确性、Task Duration 与针对性 timeline 证明。
