---
schema_version: aprof.knowledge-record/v1
id: implementation.buffer-lifetime.fallback
kind: recipe
version: 1.1.0
status: active
title: Buffer 存活期与布局 回退方法
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
learning: {}
tags:
- last-consumer
- static-allocation
- ub-fallback
seed_reason: 审读固定开源修订并提炼中文实现配方，保留既有 ID 语义；API 单位以实际 API 文档为准；未做目标 SDK 编译或 NPU 性能验证。
parent: implementation.buffer-lifetime
references:
- implementation.buffer-lifetime.arch22-bank-layout
- implementation.buffer-lifetime.reuse
evidence_status: source_reviewed_not_benchmarked
---

# 存活期或地址共享证据不足时保留独立 buffer

## 适用条件与保守策略

当共享后出现偶发精度错、跨tile污染、编译/运行容量超限，或最后消费者、API alias能力、UB实际地址/银行映射未知时，恢复原独立物理区和原合法同步。保留C2数学、精度、任务所有权和输出顺序；不因为UB紧张而自动降精度、切归约或改为跨核部分和。

## 重建可审查的分配表

每个queue记录槽数与单槽字节，每个TBuf记录字节和alignment，每个自定义arena记录完整高水位，每个API记录workspace。例：两个half输入、一个half输出、每tile T元素、三个队列均双槽，基础需求为 `6×AlignUp(2T,32)` 字节；若还需一个float转换区，另加 `AlignUp(4T,32)`，再加reduce临时区、布局padding和其他常驻状态。这个例子的输入/输出槽必须确实同时物理分配，不能用“多数时刻没用”减掉。

`peakAlive=max_t Σalive alignedBytes` 用于寻找以后可共享的机会；实际 `InitBuffer` 总分配不自动等于这个下界。每个byte offset对应的区间都应落在唯一受控分配内；两个LocalTensor视图指向同址不代表框架替你预留了两者，也不代表相应API允许部分重叠。

## 修复顺序与替代路径

| 现象/缺项 | 先做的可逆动作 | 何时可继续优化 |
|---|---|---|
| 异步最后消费者未知 | 恢复原事件/队列协议和独立槽 | 为每次覆盖建立完成边 |
| TBuf元素数超过分配字节 | 重算 `count*sizeof(T)<=len` | dtype转换和尾部容量全覆盖 |
| queue num=2 占用漏算 | 按真实槽数重算 | 目标总可用UB已核验 |
| padding后超容量 | 撤回padding或在C2允许范围内缩tile | 调用次数/尾块/同步全部同步修改 |
| bank结构未知 | 保持普通合法对齐布局 | 取得当前SoC映射和真实地址证据 |
| API alias不支持 | 使用独立输入/输出区 | 已证实的原地重载才能改回 |

为定位生命周期错误可在两阶段间暂用已支持的保守全流水完成边作对照；这只是核验手段，不应以其跑通后直接宣布性能优化完成。若独立区在C2允许的最小tile和槽数下仍不能容纳，应返回C2重规划，不可删除算法必需状态或使用未保留的物理地址。

## 检查与产物

覆盖单tile、连续多tile、两阶段长度不等、short tail、所有dtype和多次重复；精度检查沿用原oracle全域。逐次标记每槽分配、生产、所有消费、最终完成、释放/复用。记录真实分配字节、各区间、可用UB证据、实施的完成边与性能代价；只在这些证据闭合后尝试`implementation.buffer-lifetime.reuse`或arch22 bank布局。构建和性能验证状态必须分别说明，来源样例正确不等于目标kernel已验证。

来源事实：InitBuffer文档说明槽数、每槽字节和内部32B上取整；TBuf::Get说明元素长度；Add双缓冲代码展示输入/输出槽复用前的跨引擎等待。分配审查表和故障回退顺序是提炼，无硬件收益承诺。
