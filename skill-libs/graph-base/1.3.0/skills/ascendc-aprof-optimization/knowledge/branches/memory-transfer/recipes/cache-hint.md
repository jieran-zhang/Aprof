---
schema_version: aprof.knowledge-record/v1
id: implementation.memory-transfer.cache-hint
kind: recipe
version: 1.0.0
status: active
title: 一次性流式输入与复用输入的 L2 hint 区分
scope:
  platforms:
  - dav-2201
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/data_structures/GlobalTensor/SetL2CacheHint.md
  original_path: docs/zh/api/SIMD-API/basic_api/data_structures/GlobalTensor/SetL2CacheHint.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 3
  - 112
  sha256: sha256:62807570650c1a69ab2bf0ba2bce606a4a3141d5d9d976fdbf3bdaf1d4df1092
  excerpt_sha256: sha256:8b3a062e7527c371f256ed15a82ae19d75e97d7d618d7381aa07605d627ce6ee
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/00_vector_compute/add_high_performance/add.asc
  original_path: examples/01_simd_cpp_api/05_best_practices/00_vector_compute/add_high_performance/add.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 27
  - 345
  sha256: sha256:f7d075958365a8fc1af9879e90ab6494573f8869d3a538832c537d8e0f905042
  excerpt_sha256: sha256:d2b85d269202c81ba81366f010df36bf3c512f17f84bd0b145c0dd1425e49cda
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/00_vector_compute/add_high_performance/README.md
  original_path: examples/01_simd_cpp_api/05_best_practices/00_vector_compute/add_high_performance/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 357
  - 485
  sha256: sha256:b5b6a86283fe52b79c7990bb8ccf5072ead5a50fbd46ae5aaa7a3e056aab1580
  excerpt_sha256: sha256:5c6d2994aaf79df1876377bb814db5f8bee465813e3dbac2fbe8cf3ad7a959cc
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/README.md
  original_path: examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 82
  - 394
  sha256: sha256:7126d511236c3539b2710934c468c56500e39ac336531597a3360d6c74282cff
  excerpt_sha256: sha256:9f27996a1bd449d385a01b00b0a11a0562c3e17bf8762c3e55e33dd241596031
learning: {}
tags:
- l2-cache
- streaming
- arch22
seed_reason: 审读固定开源修订并提炼中文实现配方，保留既有 ID 语义；API 单位以实际 API 文档为准；未做目标 SDK 编译或 NPU 性能验证。
parent: implementation.memory-transfer
references:
- implementation.memory-transfer.l2-reuse-order
- implementation.memory-transfer.coalesce
evidence_status: source_reviewed_not_benchmarked
---

# 按实际复用关系设置 L2 Cache hint

## 原理、适用域与默认路径

L2 默认启用。对一次性流式输入，写入和置换 cache 可能增加开销并挤出真正复用的数据；对多核或跨 tile 反复读取的权重、公共向量和中间结果，保留 cache 可能减少 HBM 流量。策略按每个 GlobalTensor 的实际访问轨迹决定，不能只看“本核读一次”，也不能把单次 kernel 内无复用等同于整个执行序列无复用。

来源 API 明确支持 Atlas A2/A3，本文只提供 arch22 路径的 NORMAL/DISABLE 候选。目标 SoC/SDK 仍需独立核验；不使用文档标为尚未支持的 PERSISTENT，也不把 hint 当作跨核同步或一致性保证。C2 未授权 cache 策略改动时先保留当前方案，记录需要重规划的输入。

## 操作方法

列出每个 tensor 的读核集合、访问轮数、复用距离、相邻算子消费者和同时竞争的工作集。无证据时保留 NORMAL。对确认每段仅读一次且其他核/近邻消费者不复用的大流式输入，单独测试 DISABLE；对共享输入继续 NORMAL，避免“整个算子统一 bypass”。输入输出若是同一 GM 区间的不同视图，列清所有视图 hint 与生命周期，不能以换视图规避访问分析。

下面是 Add 的 CopyIn 初始化片段，`x/y` 是本任务的有效 `__gm__ half*`，`n` 为 half 元素数；Host 已验证两段 GM 地址和 count。`xGm/yGm` 为类成员 `AscendC::GlobalTensor<half>`，`onePassX/Y` 是 C2 冻结且有访问证据的元数据策略位，不在 kernel 内根据 benchmark 名或计时结果改变。

```cpp
xGm.SetGlobalBuffer(x, n); // n 单位：half 元素，逻辑字节=2*n
yGm.SetGlobalBuffer(y, n);
xGm.SetL2CacheHint(onePassX ? AscendC::CacheMode::CACHE_MODE_DISABLE
                          : AscendC::CacheMode::CACHE_MODE_NORMAL);
yGm.SetL2CacheHint(onePassY ? AscendC::CacheMode::CACHE_MODE_DISABLE
                          : AscendC::CacheMode::CACHE_MODE_NORMAL);
// 随后沿用原来已验证的 DataCopy/DataCopyPad、计算、事件和写回路径。
```

两候选的 shape、核数、tile、双缓冲、数学操作与输出地址完全相同，只变某 tensor 的 hint。每次执行显式设定需要的模式，避免复用对象时上一条路径的 hint 泄漏。hint 不申请额外 UB，不允许删除等待事件；被禁用 cache 的输入仍须保持 GM 有效直到 DMA 读取完成。

## 成本与比较方法

设一个共享片段大小 `W` 字节，访问 `q` 轮。逻辑 load 总量两版均为 `qW`；理想可复用 cache 时 HBM 读接近 `W`，全 miss/bypass 则接近 `qW`，最多相差 `(q-1)W`，这只是说明风险的上界。流式 `q=1` 时无上述复用节约，才有可能受益于 bypass；系统中其他工作集和 cache 行浪费会使实际结果偏离估算。NORMAL 不能保证命中，DISABLE 不能保证端到端加速。

在固定输入和同一测量协议下比较 Task、MTE2、HBM 读量和 L2 hit/miss；A2/A3 来源样例需要汇总 r0/r1 通道，不能把单通道命中率当总命中率。保留原有冷/热态协议，避免 baseline 冷 cache、候选热 cache。一次只改一类 tensor；cache hit 降低但 Task 更快可能是流式候选的合理现象，Task 变慢即使某引擎指标更好也不接受。

## 失败边界与来源

共享权重被误判一次性、多个核读同一输入、后继算子很快消费刚写出的结果、重复调用工作集可驻留时，bypass 容易回退。恢复 NORMAL 是最小退路。若复用存在但工作集大于可用 L2，应评估 `implementation.memory-transfer.l2-reuse-order` 的分片内复用；这需要 C2 已允许相应遍历顺序，不能在本条偷偷变算法。

来源事实：asc-devkit Add case5 在双缓冲 Add 中对两个一次性输入设置 DISABLE；官方 SetL2CacheHint 文档说明默认 NORMAL、产品支持和 PERSISTENT 尚未支持。本文的访问表、qW 模型与隔离实验是提炼，原 case 的耗时和收益没有迁入任何 910C 默认结论。
