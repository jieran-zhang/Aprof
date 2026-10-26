---
schema_version: aprof.knowledge-record/v1
id: planning.matmul.resident
kind: template
version: 1.1.0
status: active
title: 小侧驻留与 L1/L0 复用
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/matmul/fullload_design.md
  original_path: ops/ascendc-performance-best-practices/reference/matmul/fullload_design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 344
  sha256: sha256:e96e583c3cddcfba079a664f273533ecef25eec7bdc48fae8c1ae4f50e755f50
  excerpt_sha256: sha256:e96e583c3cddcfba079a664f273533ecef25eec7bdc48fae8c1ae4f50e755f50
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 138
  sha256: sha256:080b31488432d91c218eacb24f37608c99425ab7b6b692f2e6e7691a407475a6
  excerpt_sha256: sha256:080b31488432d91c218eacb24f37608c99425ab7b6b692f2e6e7691a407475a6
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 139
  sha256: sha256:411edebe99b43b0bb05bac2754c1d4ffd4abe46c726df718c0c1b4a7131eb0ed
  excerpt_sha256: sha256:411edebe99b43b0bb05bac2754c1d4ffd4abe46c726df718c0c1b4a7131eb0ed
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/gmm/grouped_matmul/op_host/op_tiling/grouped_matmul_tiling.cpp
  original_path: gmm/grouped_matmul/op_host/op_tiling/grouped_matmul_tiling.cpp
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 777
  - 837
  sha256: sha256:e6a78676240ef526b9a1ec46d24fe348ddb053b9becb9cc6bfa58803b6ed5c25
  excerpt_sha256: sha256:eb22efb1917bc3e23cbe4d5be5e0d501f31302baeef59a6a42a9e5832514b9fa
learning: {}
tags:
- arch22-source
- l1-l0-reuse
- resident-lifetime
seed_reason: 在保留原 ID/迁移来源的基础上审读固定开源修订，补全中文算法、任务所有权、字节成本与架构边界；未做 NPU 性能训练。
parent: planning.matmul
references:
- planning.matmul.gmm
- planning.matmul.mn
evidence_status: source_reviewed_not_benchmarked
---

# 小侧驻留、分层复用与流式侧调度

## 适用域与算法选择

当某个 A/B 基本块在多个对侧块中重复使用，且其地址、内容和量化参数在整个复用窗口内不变，可比较 L1 或 L0 驻留。典型情况是一个 `Mwindow×Kwindow` 的 A 配多个 N tile，或一个 `Kwindow×Nwindow` 的 B 配多个 M tile。小侧按实际字节和布局判断，不能只比 M 与 N 的数值。

先保留 MN 独占输出和完整 K 所有权，再选择驻留层、侧和窗口。arch22 的 L0A cache 与 L1 全载/多缓冲模板证明两种层级可分别存在；不代表任何 `M×K` 能放下，也不代表驻留必须占一半 L1。若只复用一次，驻留通常没有省流量的依据。

## 任务、生命周期与同步

任务键 `(group,mTile,nTile)` 与普通 MN 相同。一个所有者可顺序处理一组共用小侧的输出 tile，驻留区跨这些 tile 存活；流式侧在其自己的槽中轮转。驻留从“最后一次写完成”开始，到“最后一个消费者完成”为止，不能按流式侧当前轮已消费就释放。跨组权重地址或 scale 改变时结束该窗口。

驻留改变的是重复装载层级：L1 驻留减少 GM→L1 请求，L0 驻留减少 L1→L0 请求；L2 分片是跨核共享工作集的调度，不能当作某核私有驻留的同义词。API 内部缓存与手排固定槽需要分别审读，不能重复预留同一块内存或错误地删掉内部依赖。

## 字节模型与符号

令 `R` 为窗口内同一驻留数据的消费次数；`Br` 为按目标布局对齐后的驻留字节；`Bs` 为一槽流式数据字节；`ds` 为同时存活流式槽数；`Bother` 为同层其他常驻区/API 临时区；`Ulevel` 为该层可用字节。

```text
驻留容量: Br + ds Bs + Bother ≤ Ulevel
该层理论省读量: ΔB ≈ (R−1) Br
若 A 按整 K 驻留: Br = AlignLayout(Mwindow,K,sA)
若 B 按 K 窗口驻留: Br = AlignLayout(Kwindow,Nwindow,sB)
L0A/B/C 仍分别满足其缓冲深度 × 基本块实际字节 ≤ 对应可用容量
```

`AlignLayout` 是按真实物理 stride、padding、fragment 和对齐计算的字节函数；`sA/sB` 是每元素字节。scale、zero-point、转置缓存和 bias 若与数据共同存活，单独加进 Br 或 Bother。若量化转换产生新 dtype，必须用转换后字节而非原始压缩字节。

省读量仅是候选收益：驻留挤掉 ping-pong、增大每核输出任务、降低活跃核数，可能使关键路径变长。比较 `max_core_time`、相应搬运层的请求字节和新增等待；若当前已在 Cube 计算主导且该层搬运被隐藏，省字节也可能不缩短时间。

跨核存在共享输入时，可另按 L2 外层窗口比较轮次和缓存重用。令 `ML2,NL2,KL2` 为该轮覆盖的逻辑范围，粗略工作集为 `AlignLayout(ML2,KL2,sA)+AlignLayout(KL2,NL2,sB)+AlignLayout(ML2,NL2,sC)+Baux`，Baux 包括该轮需缓存的附加参数/中间区；与目标可用 L2 预算比较。缓存不是软件保证的私有驻留区，容纳关系只是候选条件，还要检查跨核访问顺序、同轮并发工作集和命中证据。缩窗口增加轮次与尾核成本，不能只选最大可容纳窗口。

## 参数、替代方案与融合边界

候选包括 residentSide、L1/L0 层、M/N/K 复用窗口、流式深度、大包 K 深度、输出遍历顺序。先算最小可用驻留方案，再判断是否值得扩大复用窗口，不能用“能放下的最大窗口”替代负载均衡。

一侧无法整 K 驻留时可只驻留 K 子窗口，累加器必须在所有窗口间保持正确；需要重新计算累加器和写回成本。容量不闭合时缩小窗口或回到常规流式 MN；只有跨核共享明显且工作集可按轮容纳时再比较 L2 分片。未知精度/转换语义不以额外驻留自动补齐。

融合边界在规划中写清：驻留区是否可被后续消费者直接读、跨 Cube/Vector 是否需要 GM 握手、epilogue 是否一次执行。实现中才选择具体 queue/event/API；“驻留 + 融合”不自动消除所有中间 GM。

## 伪代码与关键代码

```text
for each reuse window assigned to this output owner:
    load immutable reusable side into the budgeted resident region
    establish ready dependency
    for each streaming-side/output tile in the window:
        load stream slot after its previous consumer releases it
        compute using resident side; accumulate all declared K windows
        finish epilogue and write only this output owner's valid region
    release resident region after all consumers complete
```

```cpp
// 字节来自规划表；TBuf 位置须与实际 Matmul 通路匹配。
pipe.InitBuffer(residentBuffer, residentBytes);
pipe.InitBuffer(streamQueue, streamSlots, streamBytesPerSlot);
// C3 需把 residentReady、streamReady、consumerDone 映射为 API/事件依赖。
// 不能用一次局部 PipeBarrier 充当“所有消费者已结束”的跨核证明。
```

上述是 buffer 配额片段，不是完整算子；TBuf/TQue 类型、InitBuffer 重载、内存层和占用上限按目标 SDK 核验。规划冻结驻留的不可变地址范围与消费次数，后续实现不得把生命周期缩短到最后一次实际消费之前。

## 验证、停止条件与证据

记录驻留区和流式槽的起止字节、生产/消费阶段、首次 ready、最后释放；覆盖窗口边界、K 尾块、组切换、转置、不同 dtype/scale、仅一个消费者与多消费者、重复调用。若结果随轮数变化或跨组串值，先检查过早覆写与元数据窗口。

固定 arch22 源码/文档支持的是分层复用机制；旧迁移来源中的 arch35 布局、数值或容量只保留溯源，不作为 arch22 参数。没有当前硬件测试，收益与合法 API 能力均需按型号、SDK 和实际分派补证；不满足门禁回到完整 K 流式基线。
