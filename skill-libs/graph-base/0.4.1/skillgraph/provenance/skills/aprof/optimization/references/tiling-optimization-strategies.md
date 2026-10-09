# Tiling Optimization Strategies

本文用于 `problem_family=tiling` 的优化 candidate 设计。目标不是调一个 tile 常量，而是同步重写
任务划分、片上容量、tail 路径和算子族策略。

## Deep Routing

| 场景 | Decision gate | Structural patch shape |
| --- | --- | --- |
| Vec/UB 类 tile 太小 | useful bytes/MTE instruction 低、tile loop 多、UB 还有余量 | 合并连续轴或增大主 tile，同步 `tileLengthAlign`、copy count、tail valid count |
| Vec/UB 类 tile 太大 | `totalTasks < activeCore` 或 tail 拖尾，且每核工作不均 | 减小 tile 或增加 outer/group/head 任务维，重新计算 per-core offset |
| Cube/融合类两级切分 | L1/L0/UB 任一层成为容量瓶颈 | 先 L1/Cube 分块，再为 UB 后处理/融合链切 sub-tile |
| tail 慢路径 | tail 走标量/重复 reload/小块 copy | tail 复用主路径，用 valid count、mask 或 DataCopyPad 控制有效元素 |
| dynamic shape 固定核数 | 小 shape 过开核，大 shape 核数不足 | Host Tiling 按 shape 算 `usedCoreNum`、主/tail 任务和边界 fast path |

## Operator Rules

- **MatMul**：先走 SWAT 七步基线，再评估 FullLoad、StreamK/DP+SK、L0C DB、L1 `stepK`、`nBufferNum` 和 MTE2 preload。
- **Softmax/FA**：S2/D tile 同时受 score tile、Q/K/V tile、running max/sum/O_acc 和 workspace/LSE 限制。
- **Reduction**：按 FullLoad、TwoPass、Welford、Group Reduce、dichotomy、with-index 路由；不要只取最大 UB tile。
- **Sort/TopK**：tileSize 由 value/index/proposal/tmp buffer 和两级归并路数决定；大 N 需要四阶段 tiling。
- **Broadcast/Conversion**：连续轴、row batch、repeat 上限、NDDMA/UB broadcast 或 transpose fusion 必须一起建模。

## Capacity Formula

- Vec/UB：`live_ub_bytes = sum(aligned(tensor_i_bytes)) * bufferDepth + tmp + padding <= UB`。
- DB：`2 * (inputQueue + outputQueue + temp) <= UB`，且 `tileNum >= 2`。
- MatMul：分别计算 `L1`, `L0A`, `L0B`, `L0C`, `Fixpipe`, `workspace`；`baseM/baseN/baseK` 必须对齐 Cube 粒度。
- Sort：`onceMaxElements = floor(ubSize / bytes_per_elem / 32) * 32`，Phase 2/3 和 Phase 4 的 bytes/elem 不同。
- FA/Softmax：`score_tile + Q/K/V tile + running_state + O_acc + mask/bias <= UB/L1`，跨 split 另算 workspace。

## Required Evidence

- shape、dtype、format、输入输出数、main loop 维度和算子族。
- Host Tiling 字段：`blockDim`、`tileLength`、`tileNum`、`tailLength`、stage/buffer/workspace。
- 容量分母：UB、L1、L0A/B/C、workspace slot、AIV/AIC 核数。
- profiling/trace：MTE 指令密度、per-core time、tail case、active core、PipeUtilization。

## Abort Conditions

- 没有 UB/L1/L0/workspace 分母，却要改变 tile 或 stage depth。
- padding 可能进入 Reduce/Softmax/Sort compare、variance、exp 或输出。
- tiny/small workload 已接近 attainable utilization，却只想提高绝对核利用率。
- MatMul/FA/Sort/Reduction 的 workspace combine 或输出顺序没有证明。
- candidate 写死 shape/core/tile 且未标记 `benchmark_specialized`。

## Metric Delta

- MTE 指令数 / 输出元素下降，useful bytes/MTE instruction 上升。
- tail 分支耗时和 per-core time 方差下降。
- 大 shape active core 上升，小 shape 不明显回退。
- MatMul/FA 中 CUBE/MTE/Fixpipe 比例更接近 workload model。
