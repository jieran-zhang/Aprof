# Softmax / FlashAttention Optimization Playbook

用于 Softmax、LogSoftmax、FlashAttention、paged/sparse attention 与含 Softmax 的融合算子。只在 operator family
或源码锚点指向 Softmax/FA 时加载。

## Decision Gate

- **普通 Softmax**：先判断行/列方向、是否可 FullLoad、是否有两遍 max/sum、padding 是否会进入 `exp/sum`。
- **Online Softmax**：当完整 `QK^T` / prob 矩阵导致 `O(S^2)` workspace 或 GM 往返时，改为 S2 tile + running state。
- **State resident**：running max、running sum、O_acc 或 LSE 被反复分配/回写时，优先保持 UB/workspace resident。
- **FA decode split-KV**：batch/head/MN 任务不足但 KV/S2 很长时，考虑 split-KV；必须配套 partial O/LSE combine。
- **S2/D tile**：S2 tile 受 score tile、K/V tile、running state 与 `D` 维输出累加共同约束，不按单个 tensor 最大化。

## Capacity Formula

- running state：`state_bytes = B * (max + sum) * sizeof(compute) + B * D * sizeof(compute)`。
- score tile：`score_bytes = Bq * Bk * sizeof(compute)`；还要加 Q/K/V tile、mask/dropout/bias 临时区。
- online workspace：跨 tile 需要保存 LSE 或 partial O 时，按 `split_count * Bq * (D + state)` 计算并 32B 对齐。
- split-KV：`partial_O_bytes = splitNum * Bq * D * sizeof(float)`，`partial_lse_bytes = splitNum * Bq * sizeof(float)`。
- DB/pipeline：如果 Q resident + K/V pingpong，UB 预算需除以 queue depth，再判断 tile 是否仍有足够算术强度。

## Structural Patch Shape

- Naive softmax 改 online：删除完整 score/prob GM staging，增加 `m_old/l_old/O_acc` 初始化、S2 tile 循环和 final normalize。
- FA S2 tiling：Host Tiling 增加 `Bq/Bk/D/s2TileNum/preLoadNum/workspace`，Kernel 调整 Q resident、K/V streaming 与 state 更新。
- split-KV：增加 per-split partial workspace、AIV combine、LSE 数值稳定公式和同步边界。
- state resident：把 running max/sum/O_acc 的 TBuf 生命周期延长到 S2 loop 外，避免每 tile 分配/回写。

## Metric Delta

- GM bytes 从完整 score/prob staging 转向 `O(S)` state；workspace 读写下降。
- VEC `exp/reduce` 时间可能仍高，但 MTE 往返和 Sync 下降，长序列 duration 改善。
- FA decode 的 active core 数上升，partial combine overhead 小于 split-KV 并行收益。
- accuracy gate 覆盖 mask、causal、padding、tail S2 和极值输入。

## Abort Conditions

- padding/mask 可能进入 max/sum/exp，或 `-inf`/valid count 策略不明确。
- online update 改变数值稳定性、舍入、dtype accumulate 或输出顺序且未获许可。
- split-KV 缺少 LSE/partial O combine 公式、workspace slot 或跨核同步证明。
- S2/D tile 缩到过小，MTE setup 或 VEC scalar loop 成为新瓶颈。
