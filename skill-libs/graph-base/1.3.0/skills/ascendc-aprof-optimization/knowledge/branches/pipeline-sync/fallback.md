---
schema_version: aprof.knowledge-record/v1
id: implementation.pipeline-sync.fallback
kind: recipe
version: 1.1.0
status: active
title: 流水与同步的正确性回退及重规划边界
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md
  original_path: ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 40
  - 249
  sha256: sha256:142cc0055136ff3bc203672f4c4365cf4f09b41a175a7bfa1d89f3df3b2500ae
  excerpt_sha256: sha256:28c3372885746552f8fc7c07805f7f715efc2c32ef72a3a0155dcbd49a0967a3
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
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/mmad_gelu.asc
  original_path: examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/mmad_gelu.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 21
  - 613
  sha256: sha256:2fb232c81805420c88755d9bc41ea3561c3f4107946306425d1a43b48c31dd1d
  excerpt_sha256: sha256:a9dc9e4064f9198bc1a959600b5ec80e454c71f38ac2681b7cbe3e0a8d5d9728
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: implementation.pipeline-sync
references:
- implementation.pipeline-sync.pipeline
- implementation.pipeline-sync.slots
evidence_status: source_reviewed_not_benchmarked
---
# 流水与同步的正确性回退及重规划边界

## 何时进入

缺少真实生产者/消费者、无法证明同槽最后一次读取、容量或事件额度不够、当前SDK无所需原语、未掌握空任务/尾块通知数量，均不能进入更深流水。保留当前正确实现；若不存在正确基线，先实现最浅的合法路径。源码示例或历史速度只给候选，不覆盖当前case的缺证。

C3的最小回退单位是C2已允许的实现参数：同一tile/算法/数值语义下关闭预取、减缓冲或阶段串行；改变融合region、task拆分、核配比、跨核拓扑、workspace所有者或GM/UB通路，需返回C2。不得为继续跑性能静默取消mask、改GELU近似、改变累加dtype或省略全K归并。

## 先按失败边定位契约

| 现象 | 必须保留的证据 | 可在原计划内尝试的修复 | 不能推导的结论 |
|---|---|---|---|
| 首轮挂起 | 首次Wait及其对应Set、参与核列表 | 补合法free预置/首轮分支 | 不是“需要第三槽”的证据 |
| 回卷后周期性错 | 任务序号、槽代次、最后读者 | 延迟复用至最后读完成 | 总UB足够不代表无race |
| 尾块漏写/越界 | validCount、allocatedCount、DMA范围 | 修正prolog/drain及有效长度 | padding内的值不能冒充有效输出 |
| 双AIV挂起 | 两个subId各自的Set/Wait数量 | 保持空任务也遵守握手契约 | 单AIV早退不自动安全 |
| 无提速/变慢 | Task Duration、阶段timeline、总字节 | 关闭预取或恢复较大tile | MTE stall下降不等于任务更快 |
| 边界精度不符 | 原oracle、首个差异和特殊值mask | 恢复原dtype/运算顺序/近似契约 | 不可将语义错误归为纯流水问题 |

## 最浅可证明路径

按每个合法tile执行“等待槽空闲→搬入→等待就绪→完整计算→等待输出就绪→搬出→等待异步读完后复用”。纯Vector可用支持的TQue、TBuf配对事件或已证明的静态租约管理同核生命周期；根据目标动态域、容量、事件所有权和实际成本选择，任何方案均保留真实跨流水完成边。跨AIC/AIV仍需合法的CrossCore发布/消费，单核`PipeBarrier`无法替代。每轮全局drain可作诊断性的串行候选，但它不是可无条件删减正确同步的理由。

```text
for task in C2_frozen_task_order:
    for tile in task.tiles:
        acquire original input/output regions
        copy valid input; wait copy ready
        compute with original numerical semantics
        publish output only when complete
        wait every asynchronous consumer before region reuse
finish pending output and restore event/queue lifecycle
```

此段是伪代码，不依赖来源repo私有helper。零任务不发DMA；单tile不发next-tile预取；尾块先裁定有效长度再形成地址。Matmul非线性epilogue只能消费完成全部K累加/必要归并的结果；分K partial需要原计划的最终化阶段。

## 平台/API证据不足时

S1的double-buffer示意和收益数字不是910C标定。TQue模板depth约束未DeQue项数，InitBuffer num决定物理块数；把两者混同的实现先回退到每次合法EnQue/DeQue的骨架。S2/S3的官方CrossCore资料优先于泛化描述：A2/A3支持mode0/1/2，Wait参数不改变硬件功能且阻塞全部流水后续发射；mode4属于950能力。不能把950直通样例或默认mode误读作为910C优化依据。

对dav-2201 MatmulGelu，S4在编译期强制Scenario1，即L0C→GM→UB；Scenario2不能作为“更快fallback”。高阶Matmul的VECIN结果位置不独立证明物理L0C→UB直通。若SDK能力缺失，保留GM中转或分离launch基线，由C2决定是否接受另一融合region。

## 完成判据

先通过原oracle全case以及0/1/2 tile、回卷、奇数任务和边界dtype；再按当前统一计时协议比较候选和直接父本，必要时补针对性timeline。失败case、日志、参数和源码差异保留。C3交付实际使用条目ID/版本、容量与事件表、计划符合性及仍缺失的证据；未正确或未测量的候选不因理论overlap获得性能结论。

## 固定来源与证据级别

- S1：[ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md](../../sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md)，行 40–249；修订 `41377d0a442cd5b1c2356874873a3dda591c6633`。
- S2：[docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md](../../sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md)，行 28–151；修订 `d378849769f9ee610af9d0ac38db2b3b6bed3209`。
- S3：[docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md](../../sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md)，行 28–151；修订 `d378849769f9ee610af9d0ac38db2b3b6bed3209`。
- S4：[examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/mmad_gelu.asc](../../sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/mmad_gelu.asc)，行 21–613；修订 `d378849769f9ee610af9d0ac38db2b3b6bed3209`。

来源事实、本文推导与待验证项在正文分别标注。冻结源码及仓库许可证随包保存；本次仅完成审读，未在目标 SDK 构建，未运行 NPU 正确性或性能测量。源码存在不代表当前 shape 已分派到该路径，任何收益都须由当前候选的完整正确性、Task Duration 与针对性 timeline 证明。
