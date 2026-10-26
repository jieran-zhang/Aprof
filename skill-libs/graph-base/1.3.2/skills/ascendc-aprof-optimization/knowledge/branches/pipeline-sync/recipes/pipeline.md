---
schema_version: aprof.knowledge-record/v1
id: implementation.pipeline-sync.pipeline
kind: recipe
version: 1.2.0
status: active
title: 流水阶段、队列与事件的闭合实现
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
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 139
  sha256: sha256:411edebe99b43b0bb05bac2754c1d4ffd4abe46c726df718c0c1b4a7131eb0ed
  excerpt_sha256: sha256:411edebe99b43b0bb05bac2754c1d4ffd4abe46c726df718c0c1b4a7131eb0ed
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
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/cann-samples/17c948bb961fc6a660e4fcab45f6bf217c9c6239/Samples/2_Performance/rms_norm_quant_story/src/4_double_buffer.asc
  original_path: Samples/2_Performance/rms_norm_quant_story/src/4_double_buffer.asc
  revision: 17c948bb961fc6a660e4fcab45f6bf217c9c6239
  lines:
  - 1
  - 569
  sha256: sha256:6b027cb2b0faa24546a5d13339f06f93a1e8fe0bed527c80866038ae12c0557a
  excerpt_sha256: sha256:6b027cb2b0faa24546a5d13339f06f93a1e8fe0bed527c80866038ae12c0557a
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/cann-samples/17c948bb961fc6a660e4fcab45f6bf217c9c6239/Samples/2_Performance/rms_norm_quant_story/CMakeLists.txt
  original_path: Samples/2_Performance/rms_norm_quant_story/CMakeLists.txt
  revision: 17c948bb961fc6a660e4fcab45f6bf217c9c6239
  lines:
  - 1
  - 57
  sha256: sha256:6e7620af55c25f4c17416072ad4e9b82f065e23d55b58449d56db6ad3e46a123
  excerpt_sha256: sha256:6e7620af55c25f4c17416072ad4e9b82f065e23d55b58449d56db6ad3e46a123
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/cann-samples/17c948bb961fc6a660e4fcab45f6bf217c9c6239/Samples/2_Performance/rms_norm_quant_story/README.md
  original_path: Samples/2_Performance/rms_norm_quant_story/README.md
  revision: 17c948bb961fc6a660e4fcab45f6bf217c9c6239
  lines:
  - 1
  - 607
  sha256: sha256:31d54b8888424d789e909b56e16e410042d3575ce85c3b0df8e62f717affa2aa
  excerpt_sha256: sha256:31d54b8888424d789e909b56e16e410042d3575ce85c3b0df8e62f717affa2aa
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/intra_core_sync/PipeBarrier_ISASI.md
  original_path: docs/zh/api/SIMD-API/basic_api/sync_control/intra_core_sync/PipeBarrier_ISASI.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 97
  sha256: sha256:730571f5039906830624ccba76cff76d318305831f96538d7821be7c7c737773
  excerpt_sha256: sha256:730571f5039906830624ccba76cff76d318305831f96538d7821be7c7c737773
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: implementation.pipeline-sync
references:
- implementation.pipeline-sync.slots
- implementation.buffer-lifetime.reuse
evidence_status: source_reviewed_not_benchmarked
---

# 流水阶段、队列与事件的闭合实现

## 原理与 C2/C3 边界

流水把不同 tile 的搬运、计算、搬出交错，隐藏一部分等待；同一 tile 的数据依赖仍然串行。`InitBuffer(..., 2, ...)` 提供两块物理存储，既不自动证明 overlap，也不等于把 `TQue<..., depth>` 的 depth 改成 2。核融合决定哪些算子在一次 kernel 中执行，数据通路决定中间值走 GM 还是 UB，流水决定不同任务如何重叠；三者各自需要证据。

C2 冻结任务切分、核配比、tile 范围、布局、buffer 上限、workspace 所有者和允许的同步拓扑。C3 可在该范围内实现阶段、队列、事件和收尾；若要改变 task 粒度、跨核依赖、融合区间或内存通路，必须返回 C2 重规划。适用于 tile 数至少 2、存在可隐藏搬运/计算间隙且容量可闭合的 elementwise、Matmul 或既定 CV kernel。零/单 tile 和短尾必须有正确路径，无需为了“启用流水”制造多余阶段。

## 容量、时间与所有权

令第 j 类 buffer 的物理块数为 d_j，每块有效元素 n_j、元素字节 e_j、要求对齐 a_j；`align(x,a)=ceil(x/a)*a`。必须计算：

```text
UB_required = Σ_j d_j * align(n_j * e_j, a_j) + scratch + API内部预留
L1_required = dA * align(baseM*baseK*stepKa*eA,aA)
            + dB * align(baseK*baseN*stepKb*eB,aB) + 其他L1区
L0A_required = d0A * padded_A_tile_bytes
L0B_required = d0B * padded_B_tile_bytes
L0C_required = d0C * padded_C_tile_bytes
```

每级分别小于目标平台查询得到的可用空间；不能把全部存储当作一个池，也不能把来源中的 192KB、固定 tile 或“CV 必须三缓冲”变成 910C 常量。保留 tile 不变时，块数翻倍会增加容量；是否缩 tile、减少 scratch 或维持单块由 C2 的自由度决定，不机械地要求 tile 减半。

| 对象 | 写者/生产者 | 读者/消费者 | 就绪条件 | 可重写/回收条件 |
|---|---|---|---|---|
| 输入 UB 槽 | MTE2 | Vector | MTE2→V 或输入队列 DeQue | Vector 最后一次读取完成 |
| 输出 UB 槽 | Vector | MTE3 | V→MTE3 或输出队列 DeQue | MTE3 已读完本槽 |
| A/B 的 L1 包 | MTE2 | MTE1 | MTE2→MTE1 | 包中最后一个 baseK 已装入 L0 |
| L0A/L0B 槽 | MTE1 | Cube | MTE1→M | Cube 已完成读取 |
| L0C 槽 | Cube | Fixpipe | M→FIX | Fixpipe 已读完，且该 tile K 累加已结束 |

同一事件 ID 出现两次并非自动冲突：检查事件类型、方向、参与核与重叠生命周期。自定义事件需记录“首次可写”的预置、每代 ready/free 的发出和消耗次数、退出时 drain。不能等待从未发出的反向事件，也不能用早退跳过对侧必等的通知。

## 实施顺序与排程伪代码

1. 先保留单 tile 正确基线，列出每个阶段真实读写地址、有效长度、产生/释放时刻。
2. 为每种存储单独分槽并预算，选择 queue 管理或手写 event；不要两套机制无契约地同时管理同一槽。
3. prolog 只发合法首批输入；steady 只等待本次消费所需依赖；drain 处理剩余输出，不再发新输入。
4. 对所有 `t+lookahead` 先判 `< tileCount`，再计算指针和发 DMA；对尾块同时维护 allocatedCount 与 validCount。
5. 先核对 0/1/2 tile 和一次回卷，再看长流水。正确后比较总时间和 timeline。

以下是**调度模型伪代码**，`launch_*`、`wait_*` 表示由队列或目标 SDK 事件实现的契约，不是可调用 API。每槽状态带任务代次；等待只放在将要读写该槽的位置。

```text
for t in [0, tileCount):
    s = t % inputDepth
    wait_input_released(s, generation=t/inputDepth)   # 首代由初始空闲状态满足
    launch_copy_in(t,s)
    wait_input_ready(t,s)
    launch_compute(t,s,out_slot(t))
    # 计算指令一经合法发射，可发下个槽的搬运；不能覆盖仍在读的 s
    wait_output_ready(t)
    launch_copy_out(t)
# drain 每个已提交但未完成的搬出，然后释放资源
```

标量发射顺序与硬件完成顺序不同；模型不保证速度。若每轮 `PIPE_ALL` 或先等待所有前序任务再发新任务，往往把所有阶段重新串行化。

## 可落地的 Ascend C 队列片段

下面是 float、连续且 `n` 为 32B 对齐元素数的单 tile 函数，`xGm/yGm` 已绑定 GM，`inQ/outQ` 属于本核的 TPipe。它使用 `kernel_operator.h`，展示真实 API 的所有权路径；尾块需在 Host 分流到合法的 DataCopyPad/有效长度路径。它可以作为合法队列骨架，是否跨迭代重叠由编译结果和 timeline 判断。

```cpp
#include "kernel_operator.h"
using namespace AscendC;
// 成员：TPipe pipe; GlobalTensor<float> xGm, yGm;
// 成员：TQue<TPosition::VECIN,1> inQ;
// 成员：TQue<TPosition::VECOUT,1> outQ;
// Init中：pipe.InitBuffer(inQ,2,tileElems*sizeof(float));
//         pipe.InitBuffer(outQ,2,tileElems*sizeof(float));
// 物理块数2；本函数每次最多有1个未DeQue的元素，符合depth=1。
__aicore__ inline void OneTile(uint64_t off, uint32_t n) {
    auto x = inQ.AllocTensor<float>();
    DataCopy(x, xGm[off], n);
    inQ.EnQue(x);
    x = inQ.DeQue<float>();
    auto y = outQ.AllocTensor<float>();
    LeakyRelu(y, x, 0.001f, n);
    outQ.EnQue(y);
    inQ.FreeTensor(x);
    y = outQ.DeQue<float>();
    DataCopy(yGm[off], y, n);
    outQ.FreeTensor(y);
}
```

不要把 `CopyIn(0); CopyIn(1);` 的两次连续 EnQue 硬塞进 depth=1 队列；要么在第一次 Compute/DeQue 后再预取，要么在 SDK 允许时明确扩大队列深度并重新证明容量。队列 Free 是交回队列管理，支持的队列用法由框架维护依赖；若改成手工地址复用，必须自己等待异步读者真正完成。源 S1 的示意循环不是可原样移植的完整程序。

## Matmul/CV 的架构限制

S2/S3 的 arch22 路线支持 L1/L0 ping-pong 与精确反向事件。A/B 的大包长度不同，L1 释放计数应按各自包末尾；只在合法的首 baseK 等 ready、末 baseK 发 free。高阶 Matmul 内部已管理的 buffer/event 不重复手排。

跨核同步与本核 HardEvent 不同。S4 的官方 API 文档明确：A2/A3 支持 CrossCore mode 0/1/2；其 Wait 的 mode/pipe 参数不作为硬件输入，Wait 会阻塞全部流水后续发射。显式写相同 mode 有助审读，但不能把 arch22 中 `Set<2>` 配默认 `Wait` 一律判为挂死。950 的 mode 4 使用不同硬件指令，才必须显式选择；这不构成 910C 可用能力。`PipeBarrier<PIPE_V>` 只表达 V 内依赖，不能替代 GM 跨核发布/消费握手。

## 验证、失败与回退

验证零任务、单 tile、两 tile、奇数 tile、尾长 1/对齐边界、槽回卷、多次重复及多核不均匀任务。记录队列最大未 DeQue 数、各槽 live 区间、事件计数和 workspace 最大地址。性能上看 Task Duration、启动/稳态/收尾各段和实际重叠，不用“配置了两块”替代机制证据。

首轮挂起常见于未预置 free；周期性错常见于复用早于最后读；末轮漏写常见于 drain 缺失；双缓冲变慢可能是 tile 缩小后发射/同步变多。回退到同算法同 dtype 的单槽、逐 tile 正确路径，保留原失败；需要新所有者、核数、数据通路或融合区间时返回 C2。

## 固定来源与证据级别

- S1：[ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md](../../../sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md)，行 40–249；修订 `41377d0a442cd5b1c2356874873a3dda591c6633`。
- S2：[ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md](../../../sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md)，行 1–139；修订 `41377d0a442cd5b1c2356874873a3dda591c6633`。
- S3：[ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md](../../../sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md)，行 1–155；修订 `41377d0a442cd5b1c2356874873a3dda591c6633`。
- S4：[docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md](../../../sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md)，行 28–151；修订 `d378849769f9ee610af9d0ac38db2b3b6bed3209`。

来源事实、本文推导与待验证项在正文分别标注。冻结源码及仓库许可证随包保存；本次仅完成审读，未在目标 SDK 构建，未运行 NPU 正确性或性能测量。源码存在不代表当前 shape 已分派到该路径，任何收益都须由当前候选的完整正确性、Task Duration 与针对性 timeline 证明。

## 选择前比较流水代价，实施后核对真正的完成边

已有queue只证明使用了管理接口，不证明有并发阶段。先列每个tile的实际copy/compute/store及其等待：某个等待是否依赖本tile，是否错误等待其他槽，是否在下一独立任务发射前执行了全流水完成。缩小同步按依赖边做，不按“删除barrier数量”做。MTE2→V输入就绪、V→MTE2输入槽可覆盖、V→MTE3输出就绪、MTE3→V输出槽可覆盖是不同边；`PIPE_V`不能替代跨引擎边。

令N为tile数，`ti,tc,to`分别为单tile搬入/计算/搬出时间（同一单位，未测时保留符号）。无重叠参考为 `N*(ti+tc+to)`；在资源独立、依赖允许且达到稳态的理想模型中为 `ti+tc+to+(N-1)*max(ti,tc,to)`。这是时间下界式比较模型，不是收益保证；共享带宽、发射、队列阻塞、尾部与启动成本都可能破坏理想假设。没有时间依据就仅报告可以重叠的阶段，不编造数值。

增加槽数d若迫使tile从T减到T'，要同时比较tile数从`ceil(total/T)`增至`ceil(total/T')`后的API/事件/尾部次数；不能只看“覆盖了搬运”。参数化tile+单/双槽可在C2许可范围内比较，无需先增加Tiling Key。无法证明多槽覆盖范围、或仅单tile域时保留简单计划也是合理结果。

固定cann-samples RMSNormQuant故事的`4_double_buffer.asc`使用两份输入/输出物理槽、单份gamma输入并在循环前搬入及转FP32 gamma。它的CMake明确限定dav-3510、README限定950，代码中VF/Reg不可直接移植910C。可复用的工程推导是“长存活复用区与轮转槽分别预算”，不是把该样例的性能、数量或Reg路径当作A3证明。
