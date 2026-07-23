# Vector / Scalar / Pipeline Playbook

用于 Elementwise、Broadcast、Conversion、Transpose、Cast、轻量融合链，以及无法归入 MatMul/Softmax/Reduction/Sort
的通用 Ascend C kernel。它把 single-core pipeline 知识压缩成 candidate 生成门禁。

## Bound Routing

- **Memory/MTE**：MTE ratio 高但带宽低、copy 粒度小、stride 多、DataCopy 指令密集，优先 coalesce / DataCopyPad / L2 reuse。
- **VEC**：VEC 占比 50-65% 可先看 DB+UB fusion；65-80% 看 Cast/fusion instruction；>80% 且 transcendental 多时收益有限。
- **Scalar**：小 case、IPC 低、Scalar/ScalarLDST 高，优先减少循环轴、分支、对象/TPipe/TBuffer 封装和 GetValue/SetValue。
- **No-bound bubble**：各 pipe 都不高且 trace 有空窗，优先 pingpong、UnitFlag、preload、early issue、Vec fusion 消泡。

## Candidate Templates

| 模板 | Decision gate | Structural patch shape |
| --- | --- | --- |
| UB fusion chain | VECTOR 段之间夹着 MTE3+MTE2，中间结果落 GM | 将连续 Cast/arith/reduce 留在 UB，延迟 CopyOut，重算 lifetime |
| Cast reduction | Cast 指令占比 >20% 或 fp16/fp32 往返密集 | 合并 Cast，统一 compute dtype，减少往返；保留 RoundMode |
| Fused vector instruction | Mul+Add/Sub/Acc 模式明显且 API 支持 | 替换为 VMULA/VMULS/VMADD 类融合指令，检查 repeat/mask |
| Repeat batching | `repeatTime` 可能超过 API 上限或行数接近 255 | Host 限制 tileRows 或 Kernel 分批 repeat，恢复 tail mask |
| Scalar hot-loop rewrite | 热循环内分支、动态下标、对象构造、GetValue/SetValue | 提前计算 invariant，合并分支，批量化或换 LocalTensor/API |
| Real DB | MTE2 和 VECTOR 串行、tileNum 足够、UB 可容纳 depth=2 | 改 prolog/steady/drain，不只改 `bufferNum=2` |
| Broadcast/Conversion layout | stride/transpose/cast 导致小块或 repeat 低效 | 改连续轴、row batch、NDDMA/UB broadcast 或 transpose fusion |

## Capacity Formula

- UB fusion：`sum(live tensors aligned bytes) * bufferDepth + temp <= UB`；融合后若 tile 变小需重新估算收益。
- Repeat：`repeatTime <= API limit`，超过时 `loop_batches = ceil(repeat/limit)` 并重新计算 mask/stride。
- DataCopy coalesce：`useful_bytes_per_mte = useful_bytes / instruction_count`，目标是增大粒度而不让 padding 进入 math。
- DB：`2 * (input_queue + output_queue + temp) <= UB`，并要求 `tileNum >= 2` 且 compute/copy 时间可 overlap。

## Metric Delta

- Scalar/ICache/ScalarLDST 指标下降，VECTOR repeat efficiency 上升。
- Cast 或 misc vector 指令占比下降，GM round trip 减少。
- MTE useful bytes/instruction 上升，copy/compute overlap 增强。
- Broadcast/Conversion 不因新 stride 或 padding 造成边界回退。

## Abort Conditions

- API overload、Counter mode、repeat/mask 或 DataCopyPad 语义不确定。
- padding 值可能进入比较、归约、exp、sort 或输出。
- Scalar rewrite 改变稀疏输出、TopK/NonZero 等必须逐元素处理的语义。
- DB/fusion 后 UB 超容、lifetime alias 不清或 tail mask 无法恢复。
