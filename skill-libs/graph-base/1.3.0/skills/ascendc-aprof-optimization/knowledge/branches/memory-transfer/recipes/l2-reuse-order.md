---
schema_version: aprof.knowledge-record/v1
id: implementation.memory-transfer.l2-reuse-order
kind: recipe
version: 1.1.0
status: active
title: 分片内复用与 L2 工作集约束
scope:
  platforms:
  - dav-2201
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/data_copy_ub.h
  original_path: examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/data_copy_ub.h
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 21
  - 145
  sha256: sha256:f5ca47ce371eb60e16d3fac8bb0a5f8921c62de8515d22de92b900e3c7733911
  excerpt_sha256: sha256:848f0dfa47facbfcddf126f931b9a62f125a0aced77b4f9229eb7eb23768b8f0
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/README.md
  original_path: examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 82
  - 394
  sha256: sha256:7126d511236c3539b2710934c468c56500e39ac336531597a3360d6c74282cff
  excerpt_sha256: sha256:9f27996a1bd449d385a01b00b0a11a0562c3e17bf8762c3e55e33dd241596031
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/data_structures/GlobalTensor/SetL2CacheHint.md
  original_path: docs/zh/api/SIMD-API/basic_api/data_structures/GlobalTensor/SetL2CacheHint.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 3
  - 112
  sha256: sha256:62807570650c1a69ab2bf0ba2bce606a4a3141d5d9d976fdbf3bdaf1d4df1092
  excerpt_sha256: sha256:8b3a062e7527c371f256ed15a82ae19d75e97d7d618d7381aa07605d627ce6ee
learning: {}
tags:
- l2-cache
- reuse-distance
- loop-order
- arch22
seed_reason: 审读固定开源修订并提炼中文实现配方，保留既有 ID 语义；API 单位以实际 API 文档为准；未做目标 SDK 编译或 NPU 性能验证。
parent: implementation.memory-transfer
references:
- implementation.memory-transfer.strided-pad
- implementation.memory-transfer.cache-hint
- implementation.buffer-lifetime.reuse
evidence_status: source_reviewed_not_benchmarked
---

# 分片内完成重复访问，缩短 L2 复用距离

## 原理与适用条件

同一大矩阵被依次遍历多轮时，下一轮读回之前可能已经被后续片段逐出 L2。若数学上允许把“轮次在外、分片在内”变为“分片在外、轮次在内”，可缩短复用距离，减少 HBM miss。它与 cache bypass 是不同候选：这里保留 NORMAL 并调整已被 C2 允许的访问顺序，不通过删掉必需读取制造收益。

适用前提是分片之间无时序依赖、每片输出所有者固定、重复阶段的输入不被前一阶段更新、没有必须保持的随机数/副作用顺序。对于在线递推、跨片归约、in-place 更新后再读取、原子写入或要求固定浮点归约顺序的算法，循环交换可能改变语义，必须保留 C2 原轨迹或请求重规划。本文只采用 arch22/A2/A3 数据搬运证据，不迁入 3510 的缓存大小或阈值。

## 与缓存策略的组合门禁

本文依赖该输入允许经过 L2 的读取路径。对当前 Action 实例的同一 tensor、有效地址域、实现、workload 和阶段范围，必须从真实源码/API 配置或已核验的当前计划构造 `constraint.l2_cache_enabled`：已确认 NORMAL 为 true，已确认 DISABLE 为 false；配置、视图别名或条件分派不清楚时保持 unknown，不能因为 API 有默认值就补成 NORMAL。事实绑定原始文件的 hash 和 locator，不可借另一输入或另一 Action 实例的检查结果。Action hint 只缩小文档范围，没有填入该事实的权力。

若当前模式为 DISABLE，本方案不能标为就绪或进入 C3 实施；条件未知时可以继续做方案分析、读正文补证据。现有路由统一用 `needs_evidence` 表达 false 和 unknown，需查看事实本身区分“已知不兼容”和“尚未确认”，不要把 false 改为 unknown 消除反例。已确认 NORMAL 只证明路径允许 L2，不证明命中、驻留容量或性能收益；仍须满足依赖、所有权和预算要求。

在已确认 C2 自由度内改变该输入 hint，可先形成有依据的计划/证据后继，再检查新组合；若超出自由度返回 C2，不能让即将采用的 L2 配方倒过来证明缓存已开启。同 owner 的 UB 输入驻留可以在 DISABLE 下成立，因为它保留已读原值而不依赖第二次 GM 读取命中 L2；这应使用 `implementation.memory-transfer.input-tile-residency` 的原值、地址域、容量和生命周期门禁，不能把本文当成该方法的主配方。

## 访问轨迹与落地方法

原轨迹为 `(repeat=0, shard=0..K-1), (repeat=1, shard=0..K-1), ...`。候选为 `(shard=0, repeat=0..q-1), (shard=1, repeat=0..q-1), ...`。两者访问集合、有效读总量和各输出的最后生成阶段必须一致。对每片建立任务 ID、有效范围、依赖和写回表；每个 repeat 生成不同输出时仍写入原 repeat 的独立输出位置，不能覆盖后续消费者需要的中间结果。

以下为 Host/设计层完整索引骨架，不是可直接调用的上游私有函数。`N` 是每个独立矩阵的逻辑列数，`C` 为 C2 允许的分片列数，`q` 为算法必需的重复阶段数；均为元素/计数且 `C>0,q>0`。输出每条记录是 `(stage, firstCol, validCols)`，用现有的搬运/计算实现消费记录；实际 DataCopyPad 地址和 stride 依 `implementation.memory-transfer.strided-pad`。

```text
K = N / C + (N % C != 0)
for shard in [0, K):
    firstCol = shard * C
    validCols = min(C, N - firstCol)
    for stage in [0, q):
        execute exactly the frozen operation(stage, firstCol, validCols)
        preserve original output address(stage, firstCol)
```

真实片段 `execute` 是实现需求而非库函数；必须接回本项目已存在、已审查的 kernel 阶段，不能复制来源样例里的 `RepeatCopy` 私有方法名当作新 API。实际工程若只能沿用外层阶段顺序，就不要应用本条。

## 工作集、UB 与同步预算

单片有效输入工作集 `Ws=rows×validCols×s`；cache 层需要同时容纳所有参与复用的输入、输出、跨核数据和行粒度放大，粗筛为 `Wconcurrent≈Σactive tensors Ws + competingBytes`。不得用全芯片 L2 物理容量直接作为每核可用预算，更不能在 910C 写死来源的 192MB。全矩阵 `W` 字节、q轮的逻辑读为 `qW`；理想 HBM 读从 `qW` 降至 `W`，实际仍取决于命中、争用和协议。此为推导上界，不是承诺。

UB 只需当前 tile/队列槽，并不把整片 `Ws` 都放入 UB。先按最后消费者计算活跃字节下界 `liveLowerBound=max_t Σalive alignedBytes`，寻找可以共享物理区的值；实际静态 UB 仍按各 queue 的物理槽数乘每槽字节、独立 TBuf 分配，以及共享 arena 的高水位求和。多个阶段分别 InitBuffer 时，即使串行执行也不能把实际分配量写成活跃下界；只有实施合法共享布局后才能扣减。每一 stage 仍遵守 MTE2→Vector→MTE3 的完成边；阶段轮换时释放/重用 UB 要等待最后异步读写完成。输入输出别名会延长活跃期并可能禁止循环交换。

## 验证、失败回退和证据

用同一输入比较每个输出、每片首末有效地址与访问记录总数 `K×q`，覆盖 N 不整除 C、单片、空输入的既有处理、q=1和多核。性能比较 Task、总 GM load、cache hit/miss 与 competing 工作集；只减少 MTE2 时间但增加阶段启动/写回开销时仍拒绝。若无实测复用收益，恢复原遍历顺序和 NORMAL；若证据只支持一次性输入，回到 cache-hint 的逐 tensor 候选。

来源事实：asc-devkit `data_copy` 的整块4轮与分成4片各4轮实验访问同一数据，来源在 A2/A3 展示了局部复用。本文将4/4换为 C2 给定的 C/q，并补上依赖、输出位置、并发工作集与收益上界，是工程提炼；来源实验本身不含计算，不能证明任意业务循环均可交换。本条尚无目标硬件验证。
