# Data Movement Optimization Strategies

本文用于 `problem_family=data_movement` 的 candidate 设计。核心目标是减少无效 GM 往返、小块 MTE、
stride 低效、对齐损失和可复用数据重复搬运。

## True / False Memory Bound

| 类型 | 判别 | 首选 candidate |
| --- | --- | --- |
| 真 bandwidth bound | 带宽接近平台上限，copy 大且连续，实际流量接近理论最小 | 算法降流量、片上复用；单纯 coalesce 收益有限 |
| 假 MTE bound | MTE ratio 高但带宽低，MTE 指令密度高，单次 copy 小 | 合并小块、连续化 stride、增大 tile、DataCopyPad valid path |
| GM round-trip | 实际 GM bytes 明显超过理论最小，Vector/Reduce/Cast 中间结果落 GM | UB fusion、延迟 CopyOut、resident small params |
| Pipeline memory wait | MTE time 高但 trace 显示 Copy/Compute 串行 | 路由到 `pipeline_parallel`，先修 overlap |

## Candidate Templates

| 场景 | Structural patch shape | Capacity / semantic proof |
| --- | --- | --- |
| 小块 DataCopy | 合并 row/tile copy，重写 loop 和 offset，减少 blockCount | valid length、alignment、tail 不越界 |
| stride 搬运低效 | 改连续轴 tiling、转置/reshape staging 或 UB reorder | stride 变换不改变输出顺序 |
| DataCopyPad tail | 只在 non-aligned tail 使用 pad，CopyOut 写有效长度 | pad value 不进入 compute/compare/reduce |
| L2 复用 | 相邻核/相邻 tile 处理相邻数据，增大复用窗口 | L2 hit 目标只在有重复读取时成立 |
| UB resident chain | Vector/Reduce/Cast 中间结果留 UB | live range、UB bytes、dtype 精度 |
| MatMul scale/bias/LUT | 小参数合并载入或 L1/UB resident | scale group、bias 对齐、失效条件 |

## Traffic Lower Bound

- Elementwise：`min_read = sum(input_bytes)`，`min_write = output_bytes`；多次读写说明中间结果落 GM。
- Reduction/Softmax：理论最小要区分 full-load、two-pass、online；不能把必要的两遍读误判为冗余。
- MatMul：分别估算 A/B/scale/bias/C/Fixpipe traffic，FullLoad/StreamK 另算 workspace partial。
- Sort/TopK：GM traffic 包括 input、workspace proposal、merge rounds 和 final value/index output。

## Required Evidence

- 所有 `DataCopy` / `DataCopyPad` / `LoadData` / `Fixpipe` call site、blockLen、blockCount、stride、valid count。
- GM/UB 地址对齐、row stride、tail length、dtype bytes。
- `Memory.csv` 或 profiling 中 GM_to_UB、UB_to_GM、MTE 指令数、带宽利用率。
- L2 hit 与复用关系；一次性流式访问低 hit 不自动构成问题。

## Abort Conditions

- padding 会进入 ReduceMax、sum、variance、Sort compare、Softmax exp 或 MatMul accumulate。
- DataCopyPad overload、repeat/stride 或有效长度语义不确定。
- copy 小块是 workspace/streaming 正确性的一部分，合并会破坏阶段边界。
- 带宽已经接近上限且实际流量接近理论最小，coalesce 不应作为主 candidate。

## Metric Delta

- useful bytes / MTE instruction 上升。
- GM read/write bytes 更接近理论最小流量。
- MTE2/MTE3 time 或 instruction count 下降，VEC/CUBE 不因等待回退。
- L2 hit 只在重复读场景中作为改善目标。
