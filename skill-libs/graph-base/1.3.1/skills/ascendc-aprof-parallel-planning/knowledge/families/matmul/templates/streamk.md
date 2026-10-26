---
schema_version: aprof.knowledge-record/v1
id: planning.matmul.streamk
kind: template
version: 1.0.0
status: active
title: StreamK：工作量调度与完整波次/尾轮混合
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cann-samples/17c948bb961fc6a660e4fcab45f6bf217c9c6239/Samples/2_Performance/matmul_story/matmul_recipes/examples/matmul_a16w16/README.md
  original_path: Samples/2_Performance/matmul_story/matmul_recipes/examples/matmul_a16w16/README.md
  revision: 17c948bb961fc6a660e4fcab45f6bf217c9c6239
  lines:
  - 1
  - 55
  sha256: sha256:859310bf9a0f40bdb3d04489c6f855a6d8ceac5af492d7fad4e053e284a71ade
  excerpt_sha256: sha256:555806dc59d555693b4b4b0dbfe4fbf06c2f9f830f5f20c3ca9b5a8a5c0e2ac9
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cann-samples/17c948bb961fc6a660e4fcab45f6bf217c9c6239/Samples/2_Performance/matmul_story/matmul_recipes/include/block/matmul_block_scheduler_streamk.h
  original_path: Samples/2_Performance/matmul_story/matmul_recipes/include/block/matmul_block_scheduler_streamk.h
  revision: 17c948bb961fc6a660e4fcab45f6bf217c9c6239
  lines:
  - 1
  - 186
  sha256: sha256:ab29684d3cf7520f21b489fb640f6b4d0fb565b4bfbe505abc6b3b78052ae129
  excerpt_sha256: sha256:ab29684d3cf7520f21b489fb640f6b4d0fb565b4bfbe505abc6b3b78052ae129
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cann-samples/17c948bb961fc6a660e4fcab45f6bf217c9c6239/Samples/2_Performance/matmul_story/matmul_recipes/include/tiling/matmul_tiling_streamk.h
  original_path: Samples/2_Performance/matmul_story/matmul_recipes/include/tiling/matmul_tiling_streamk.h
  revision: 17c948bb961fc6a660e4fcab45f6bf217c9c6239
  lines:
  - 1
  - 239
  sha256: sha256:32fa438fe9654c9fa9210404f7fc8917b6cc6a954517c8386ff0a3aef5b71084
  excerpt_sha256: sha256:32fa438fe9654c9fa9210404f7fc8917b6cc6a954517c8386ff0a3aef5b71084
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cann-samples/17c948bb961fc6a660e4fcab45f6bf217c9c6239/Samples/2_Performance/matmul_story/matmul_recipes/include/kernel/matmul_kernel_streamk.h
  original_path: Samples/2_Performance/matmul_story/matmul_recipes/include/kernel/matmul_kernel_streamk.h
  revision: 17c948bb961fc6a660e4fcab45f6bf217c9c6239
  lines:
  - 1
  - 222
  sha256: sha256:2620de263fa37e6b934bfb45b92e4c96fdffa78b1633a0c02da6c77cdc8c50f4
  excerpt_sha256: sha256:2620de263fa37e6b934bfb45b92e4c96fdffa78b1633a0c02da6c77cdc8c50f4
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cann-samples/17c948bb961fc6a660e4fcab45f6bf217c9c6239/Samples/2_Performance/matmul_story/matmul_recipes/include/epilogue/matmul_block_epilogue_streamk.h
  original_path: Samples/2_Performance/matmul_story/matmul_recipes/include/epilogue/matmul_block_epilogue_streamk.h
  revision: 17c948bb961fc6a660e4fcab45f6bf217c9c6239
  lines:
  - 1
  - 252
  sha256: sha256:b65b404c861cc441983a9f87e41d28d80f47ebecb9a5f8382bd0cc2d83a242f4
  excerpt_sha256: sha256:b65b404c861cc441983a9f87e41d28d80f47ebecb9a5f8382bd0cc2d83a242f4
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 138
  sha256: sha256:080b31488432d91c218eacb24f37608c99425ab7b6b692f2e6e7691a407475a6
  excerpt_sha256: sha256:080b31488432d91c218eacb24f37608c99425ab7b6b692f2e6e7691a407475a6
learning: {}
tags:
- streamk
- dp-sk-scheduling
- arch35-source-platform-qualified
seed_reason: 从固定开源修订的实际调度代码提炼独立规划模板；与现有输出分块、静态切 K 语义区分；未做 NPU 性能训练。
parent: planning.matmul
references:
- planning.matmul.mn
- planning.matmul.splitk
evidence_status: source_reviewed_not_benchmarked
---

# StreamK：工作量调度与完整波次/尾轮混合

## 与静态 Split-K 的区别及证据边界

本条独立 ID `planning.matmul.streamk`。静态 Split-K 先规定各输出 tile 的 K 分段；StreamK 以核的工作量与波次为调度对象，完整输出任务和需要合并的 K 片可混合，不能默认所有输出都写 S 份 partial。两者数值归并可复用，但任务生成、workspace 规模和调度比较必须分开。

本次实际代码证据是 cann-samples **NPU ARCH 3510 / Ascend 950 路线**的 SK/DPSK：前面的完整 MN 波次走普通数据并行（DP），欠载尾轮的 MN tile 切 K（SK），并在邻近波次安排预取/计算交错。它是 StreamK 家族的混合实例，不是任意线性工作区间或动态抢任务的完整实现，也不证明 arch22 有同一调度器。

适用于 K 较长、MN 独立任务不足，或 MN 已有多轮但最后一轮核利用低且尾轮缩短能覆盖合并成本的候选。先明确目标平台上完整任务、partial 生产者、合并所有者的实际执行能力；arch22 只有静态切 K 的独立支持证据时，使用静态 Split-K 基线，不能直接移植 950 tensor API 与跨 AIC/AIV 拓扑。

## 调度骨架与所有权

设 T 为 MN 输出 tile 总数，P 为目标逻辑所有者数，`q=floor(T/P)`，`r=T mod P`。一种可审阅的混合规划为：`qP` 个 tile 按完整 K 分配，剩余 r 个 tile 各生成合法 K 片；若 T<P，则没有完整波次，全部 T 个输出作为欠载集合。对欠载集合 U，每 tile 有 `S_t` 个 K 片，目标是降低最长核时间，并限制额外归并。

完整 tile 唯一所有者直接执行 epilogue 和写回；split tile 的每个生产者只写 `(tile,kRange)` 独有 partial，唯一合并所有者最终写回。DP 与 SK 集合互斥并覆盖全部输出。若为了重叠而调换执行顺序，slot 必须按逻辑任务键寻址，不能按“当前发射序号”错误关联到另一个输出。

源码的蛇形窗口和末轮置换是缓存/重叠的具体实现；本模板不固定窗口宽度。规划必须报告选定输出顺序、各核任务列表、每段的首尾 K、何时从 DP 转入 SK，以及哪些消费者同时活跃。进一步采用连续 `tile×Kblock` 工作流切分时，应另证明 tile 边界、跨核碎片集合与合并协议；本次资料不把该拓展标成已有可运行支持。

## 归并与同步

partial 完成依赖同时包含“计算结束”和“数据对消费者可见”；950 样例由 Cube 发跨核 flag，Vector 等待并做归并，空闲参与者也经过所需同步。移植或改变 blockDim 时必须重新列出全部参与者和退出路径，不可仅复制几条 flag。

逻辑上每输出只一次 bias、激活、残差、量化和转换。partial 相加改变浮点顺序；合并类型和次序是规划承诺。全局屏障不能由不一致参与者条件调用，局部 PipeBarrier 不能替代跨核完成。跨 kernel 合并也是可比较的实现，需计新增启动开销。

## 字节与工作量模型

`AM_t,AN_t` 为 partial 槽对齐后长宽，`sP` 为 partial 每元素字节，U 是切 K 的输出集合；`I_t=ceil(K_t/BK)` 为每输出 K 基本迭代数，`w_tj` 为该输出第 j 片估计耗时。

```text
Wpartial = Σt∈U S_t AM_t AN_t sP
额外partial请求 ≈ 2 Wpartial；DP输出无需这一份partial开销
工作分配目标 = min max_p Σ(t,j)∈p w_tj
基线满tile轮数 = ceil(T/P)；基线末轮活跃输出数 = r（r=0则无欠载尾轮）
实际工作区 = Wpartial + 协议/对齐元数据 + API临时区 + 同时存活其他中间区
```

`BK` 是合法 K 基本步长，不一定是单核 K 长度。`w_tj` 必须包含有效 M/N、布局转换和当前 K 片长度；不能只用 `T/P` 判断均衡。若只复用一轮 partial 槽，应证明上一轮合并消费结束后才覆写，并按最大同时活跃生产者预算，不能按总 tile 数或某个固定核数猜 workspace。

## 参数与选择

比较纯 MN、全部静态切 K、只拆尾轮、扩大/缩小完整波次集合、每输出 K 片数、合并块形状、DP/SK 交错深度与缓存顺序。r=0 且每核工作已均衡时不为“使用 StreamK”增加归并；短 K 或 workspace/同步主导时退回普通 MN。源实现的 K 门槛、tile、FP32 partial、核比例和 flag 常量仅属于 3510 样例，不能作为任意 dtype/平台的默认值。

## 伪代码与上下文代码

```text
partition output tiles into disjoint DP and underfilled sets
generate complete-K tasks for DP; generate legal K fragments for underfilled set
schedule tasks by bounded per-owner work, preserving slot/consumer lifetimes
complete tile -> one epilogue -> final output
fragment -> unique partial slot -> publish completion
after fragment completion -> merge owner -> one epilogue -> final output
```

```cpp
// 与 3510 样例调度公式相同的主尾任务计数；P>0，S 是本次候选尾片数。
const uint64_t tail = mnTiles % owners;
const uint64_t dpTiles = mnTiles - tail;
const uint64_t scheduledTasks = dpTiles + tail * tailSplits;
// 该简式仅适用于尾片同数的候选；T<P 时 dpTiles=0。
// 完整 tile 和 partial 不能用同一输出写回路径。
```

这是普通 C++ 计数片段，不是可移植的 NPU kernel。完整实现还需处理空 K 片、批次、转置、未整除分片、合法 K 对齐和多套 API 的收尾；不得直接调用来源的 `CheckIsSkScene` 而绕过它的 tiling 支持门禁。

## 融合、验证与回退

规划决定 DP/SK 各自的 epilogue 边界、消费者和中间区；实现选择事件、队列与具体混合入口。即便同 kernel 有 Cube/Vector，partial 合并仍可能经 GM，不能把融合按“无 GM”计收益。

验证 T<P、T=P、r=0、r很小、多个完整波次、K尾、M/N尾、batch/组键、DP/SK 置换、重复调用、空闲核同步和精度。先验证任务恰覆盖与单输出写回，再按同一计时协议比较最长核、workspace 和总耗时。当前未在 950 或 A2/A3 编译/上板；950 源码存在仅证明该特定实现形态，其他平台保留 MN/静态 Split-K 回退。
