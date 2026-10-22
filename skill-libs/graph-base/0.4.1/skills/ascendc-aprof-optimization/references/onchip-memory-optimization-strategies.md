# On-chip Memory Optimization Strategies

本文用于 `problem_family=onchip_memory` 的 candidate 设计。目标是用 UB/L1/L0/workspace 的容量、
生命周期和冲突模型支撑结构性改动。

## Deep Routing

| 场景 | Decision gate | Structural patch shape |
| --- | --- | --- |
| UB tmp 过多压缩 tile | live tensors 峰值接近 UB，tile/DB 被迫变小 | live-range map 后复用互斥 buffer，删除死 TBuf/TQue |
| UB resident | 小参数或 state 重复 GM load，复用次数足够 | scale/bias/LUT/gamma/running state 常驻，写失效条件 |
| Zone reuse | 同一大 UB 区在不同 stage 复用 | 按 stage 分 zone，显式 lifetime barrier 和 alias proof |
| bank/group conflict | ResourceConflictRatio 或 trace proxy 指向冲突 | 调整 offset、padding、stride、operand layout |
| Softmax state resident | max/sum/O_acc 每 tile 分配/回写 | state buffer 放到 S2 loop 外，控制 workspace spill |
| workspace slot 混用 | handshake/self-ref/task-state 共用 slot 出错或等待 | 拆 slot 语义、轮转份数和跨 stage 生命周期 |
| MatMul L1/L0/Fixpipe | CUBE 等 L1/L0 或 Fixpipe 输出阻塞 | FullLoad、小侧驻留、L0C DB、Fixpipe buffer 重算 |

## Capacity Formula

- UB：列出每个 LocalTensor 的 dtype、aligned bytes、bufferNum/stageNum、存活区间与 zone。
- L1/L0：MatMul/FA 必须分开算 A/B/C/scale/bias/Fixpipe；不要只看总容量。
- Softmax/FA：`runningMax + runningSum + O_acc + score/current tile` 同时存在时计算峰值。
- Workspace：按语义拆 slot；handshake、self-ref、partial output、task state 不能共用一个常量蒙混。
- Bank padding：`new_ub_bytes = old_ub_bytes + padding_stride * rows`，收益必须大于 tile 缩小损失。
- 芯片差异：bank/bank-group、UB 大小和 RegBase 行为随 SoC 变，候选要记录平台分母来源。

## Required Evidence

- `InitBuffer`、`TBuf`、`TQue`、`LocalTensor`、workspace 分配清单。
- UB/L1/L0/Fixpipe/workspace 容量分母，来自 `npu-arch` 或平台查询。
- LocalTensor lifetime 和 queue ownership，特别是 `FreeTensor` 前后。
- ResourceConflictRatio、bank/bankgroup proxy 或 trace stall。
- 多 shape 下 resident/slot 是否会失效。

## Abort Conditions

- 未证明生命周期互斥时复用同一 UB 区域。
- 没有 conflict evidence 却为了 padding 扩大 UB 占用。
- resident/padding 导致主 tile 变小、DB 失效或 MTE 小块增加。
- workspace slot 优化牺牲精度、顺序、跨核同步或 dynamic shape。
- SoC bank 差异未确认，却把 layout patch 作为 production-safe。

## Metric Delta

- UB footprint 下降，或 tileLength/DB/stage depth 可安全增大。
- 重复 GM load 下降，MTE2 time 下降。
- ResourceConflictRatio 或 simulator conflict proxy 不回退。
- MatMul/FA L1/L0/Fixpipe 复用改善，CUBE/Fixpipe wait 下降。
