# Pipeline Parallel Optimization Strategies

本文用于 `problem_family=pipeline_parallel` 的 candidate 设计。重点是生成真正的流水重排，而不是只把
`InitBuffer(..., 1)` 改成 `2`。

## Gap Classification

| Trace / source pattern | Diagnosis | Candidate |
| --- | --- | --- |
| MTE2 全在前、VECTOR/CUBE 全在后 | DB 配置未生效或 loop 串行 | 重写 prolog/steady/drain |
| SetFlag 后立即 WaitFlag | 假 pingpong，event 紧耦合 | 提前发射下一 stage，延后等待 |
| 各 pipe 都低且有空窗 | No-bound bubble | pingpong、UnitFlag、preload、early issue、Vec fusion |
| `SyncAll` 每 tile 出现 | 过宽同步 | 缩小同步范围或改 workspace stage |
| MatMul PING/PONG gap | MTE2 preload 或 L1 pingpong 不足 | 三段结构 + L1 slot/`kL1TileNum` 检查 |
| StreamK AIC/AIV 等待 | partial workspace / AIV reduce 节拍不匹配 | 调整 SK preload、workspace slot、AIC/AIV flag |

## Effective DB Gate

- `tileNum >= 2`，否则 prolog/drain 启动成本无法摊薄。
- `2 * live_ub_buffers <= UB`，必要时另建 tiling candidate 减小 tile。
- CopyIn(i+1)、Compute(i)、CopyOut(i-1) 的依赖能用 queue/event 表达。
- trace 目标是 overlap bubble；若单一 pipe 已真满，先优化该 pipe。

## Structural Patch Shape

- 写成三段：prolog 预取、steady overlap、drain 写回；同步调整 `EnQue/DeQue/FreeTensor` 时机。
- SetFlag/WaitFlag 只在数据真实可用/可覆盖处移动；A/B 或 MTE/Fixpipe event id 不要无理由共用。
- UnitFlag 用于 MMAD -> Fixpipe 这类硬件单元交接时，必须保留最终累加和输出顺序。
- MatMul MTE2 preload candidate 同步改 L1 ping/pong offset、`stepK/kL1`、tail K 和 CopyL0C/Fixpipe drain。
- StreamK candidate 同步改 AIC partial 写 workspace、AIV reduce+cast、cross-core flag 和 DP/DP+SK preload。

## Required Evidence

- CopyIn、Compute、CopyOut、Fixpipe、workspace 读写调用顺序。
- Queue/TBuf/TQue depth、buffer bytes、UB 预算。
- trace/timeline 中 stage overlap、wait、gap、PING/PONG 空窗。
- `PipeUtilization.csv` 中各 pipe ratio/time；simulator trace 只能作为 proxy。

## Abort Conditions

- 只改 `bufferNum=2` 而没有循环结构变化。
- UB 预算不够、tileNum 太少或 queue 生命周期不清。
- `SyncAll` 是跨核算法语义必需且没有替代 event contract。
- StreamK/AIC-AIV 同步缺少 workspace slot 或 partial 完成证明。

## Metric Delta

- stage overlap 上升，pipeline gap / wait time 下降。
- 各 pipe ratio 更符合 workload model，不再同时低活跃。
- duration 下降且 GM bytes 不增加。
- MatMul/FA 中 PING/PONG gap 或 AIC/AIV wait 缩短。
