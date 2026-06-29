# 数据搬运瓶颈诊断矩阵

本文用于诊断 Ascend C 算子中的数据搬运瓶颈，包括 GM 访问频繁、DataCopy 粒度过小、重复搬运、搬运与计算未重叠、CopyIn / CopyOut 占比过高等问题。

使用时必须同时参考 [tiling 诊断矩阵](tiling-diagnosis-metrics.md)，尤其是其中的搬运粒度、带宽效率、tileLength、DoubleBuffer、L2 命中率、核间不均衡和 Buffer 规划问题。

## 证据等级

- **直接**：msprof 字段或运行时硬件参数可直接支持判断。
- **派生**：需要由多个字段、shape、TilingData 或理论数据量计算得到。
- **Trace/对比**：CSV 不能直接确认，需要 timeline、trace、不同 shape 或代码插桩对比。

## 核心 Metric

### 1. 搬运占比

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| 搬入占比 | `ai*_mte2_ratio` | `PipeUtilization.csv` / `Memory.csv` | 判断 GM→UB / GM→L1 搬入是否主导 | 直接 |
| 搬出占比 | `ai*_mte3_ratio` | `PipeUtilization.csv` / `Memory.csv` | 判断 UB→GM / L1→GM 写回是否主导 | 直接 |
| 总搬运占比 | `ai*_mte2_ratio + ai*_mte3_ratio`，Cube 场景再加 `aic_mte1_ratio` | `PipeUtilization.csv` | 判断 CopyIn/CopyOut/LoadData 是否整体压过计算 | 派生 |
| CopyIn/CopyOut 阶段占比 | `CopyIn_time / Task Duration`、`CopyOut_time / Task Duration` | trace、timeline、代码插桩 | CSV 无阶段名时，用于确认代码阶段级瓶颈 | Trace/对比 |

### 2. 搬运粒度

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| 单次搬入字节数 | `GM_to_UB_datas(KB) * 1024 / ai*_mte2_instructions` | `Memory.csv` | 识别 DataCopy 粒度过小，参考阈值：单次 <16KB 需关注 | 派生 |
| 单次搬出字节数 | `UB_to_GM_datas(KB) * 1024 / ai*_mte3_instructions` | `Memory.csv` | 识别 tail 小块写回、频繁 DataCopyPad 或拆 tile 过细 | 派生 |
| MTE 指令密度 | `ai*_mte2_instructions / GM_to_UB_datas(KB)`、`ai*_mte3_instructions / UB_to_GM_datas(KB)` | `Memory.csv` | 同数据量下指令数越高，越可能是小粒度搬运 | 派生 |
| tail 搬运放大 | tail case 的单次搬运字节数与主 case 对比 | 多 shape profiling | 判断尾块是否退化为小块 copy 或标量处理 | Trace/对比 |

### 3. 带宽与理论上限

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| GM→UB 带宽利用率 | `GM_to_UB_bw_usage_rate(%)` 或 active BW / 理论带宽 | `Memory.csv` / `PipeUtilization.csv` + `/npu-arch` | 判断搬入是否接近硬件上限 | 直接/派生 |
| UB→GM 带宽利用率 | `UB_to_GM_bw_usage_rate(%)` 或 active BW / 理论带宽 | `Memory.csv` / `PipeUtilization.csv` + `/npu-arch` | 判断搬出是否接近硬件上限 | 直接/派生 |
| 理论搬运耗时 | `搬运字节数 / 理论带宽` | `Memory.csv` + `/npu-arch` | 区分“已到带宽上限”和“搬运效率差” | 派生 |
| 实际/理论搬运耗时比 | `ai*_mte2_time / 理论MTE2耗时`、`ai*_mte3_time / 理论MTE3耗时` | `PipeUtilization.csv` + 理论耗时 | 比值明显偏高时，优先查粒度、对齐、Cache、冲突、流水 | 派生 |

### 4. 重复搬运与局部性

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| 读流量放大 | `read_main_memory_datas / 理论必需读数据量` | `Memory.csv` + shape/dtype/算法公式 | 判断 GM 访问是否明显超过必要量 | 派生 |
| 写流量放大 | `write_main_memory_datas / 理论必需写数据量` | `Memory.csv` + shape/dtype/输出公式 | 判断 workspace 往返或中间结果落 GM 是否过多 | 派生 |
| L2 命中率 | `ai*_total_hit_rate(%)` | `L2Cache.csv` | <50% 时关注重复读、CacheMode、切分局部性 | 直接 |
| 各核 MTE 时间差 | `(max(ai*_mte2_time) - min(ai*_mte2_time)) / max(ai*_mte2_time)` | `PipeUtilization.csv` | 多核访问模式不均、同地址争用或 tail 集中时会升高 | 派生 |

### 5. 搬运与计算重叠

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| MTE/Compute 串行 | MTE2、VEC/CUBE、MTE3 在 trace 上几乎不重叠 | trace / timeline | 判断 DoubleBuffer 或流水编排是否失效 | Trace |
| 重叠率 | `overlap(MTE2, VEC或CUBE) / min(MTE2_time, Compute_time)` | trace / timeline | <5% 通常说明未重叠，10%-30% 为部分重叠 | Trace |
| MTE wait | `ai*_mte2_wait_ratio`、`ai*_mte3_wait_ratio` | `ResourceConflictRatio.csv` | 搬运 pipe 等待高，需查队列、同步和资源竞争 | 直接 |
| MTE 冲突 | `aiv_vec_mte_cflt_ratio` | `ResourceConflictRatio.csv` | Vector 与 MTE 竞争共享资源时升高 | 直接 |

## 问题矩阵

| 问题 | 常见触发 | 适用算子族 | 诊断 Metric | 归因与处理 | 证据 |
| ------ | ---------- | ------------ | ------------- | ------------ | ------ |
| GM 访问频繁 | 中间结果反复落 GM、未做 UB 融合、workspace 自读自写过多 | Elementwise、Broadcast、Reduction、MatMul、FA | 读/写流量放大；`read_main_memory_datas` / `write_main_memory_datas` 高；MTE2/MTE3 占比高 | 优先检查是否能 UB 融合、L1/L0 复用或减少中间结果落 GM | 派生 |
| DataCopy 粒度过小 | tileLength 过小、tail 小块、按元素/短 row 搬运 | 全部 | 单次搬入/搬出字节数 <16KB；MTE 指令密度高；`ai*_scalar_ratio` 可能升高 | 增大 tileLength，合并连续 copy，tail 保持向量化路径 | 派生 |
| 搬运次数过多 | `tileNum` 过大、split 过细、循环内重复 CopyIn | Elementwise、Broadcast、Reduction、Sort、Transpose | `ai*_mte2_instructions` / `ai*_mte3_instructions` 高；Task Duration 随 tileNum 线性升高 | 结合 [tiling 诊断矩阵](tiling-diagnosis-metrics.md) 调整 tileLength / chunk 粒度 | 派生 |
| 重复搬入同一输入 | 多核切分维度不合理、Broadcast/Reduction 未利用局部性、MatMul B 矩阵未驻留 | Broadcast、Reduction、MatMul、FA | 读流量放大；L2 hit 低；各核 MTE2 时间差大 | 调整切分维度、CacheMode、L1 驻留或预取策略 | 派生 |
| CopyOut 过多 | 中间结果多次写回、workspace 反复落盘、输出 tail 小块写 | Elementwise 融合、Reduction、MatMul 后处理、FA | `ai*_mte3_ratio` 高；`UB_to_GM_datas` / `ai*_mte3_instructions` 异常；写流量放大 | 融合后处理，减少中间输出，合并写回，tail 使用 DataCopyPad 控制有效 count | 派生 |
| 搬运与计算未重叠 | DoubleBuffer 未生效、队列配对错误、同步过强、跨 tile 依赖 | 全部 | trace 显示 MTE2/VEC/CUBE/MTE3 串行；重叠率低；MTE wait 高 | 检查 `bufNum=2`、EnQue/DeQue、Sync/WaitFlag、跨 tile 数据依赖 | Trace |
| MTE2 Bound 但带宽未达标 | DataCopy 粒度小、非连续搬运、L2 miss、MTE 冲突 | Vector-heavy、Broadcast、Reduction、Transpose | `ai*_mte2_ratio` 高但 BW usage 低；单次搬入小；L2 hit 低；MTE conflict 高 | 先查粒度与连续性，再查 CacheMode 和流水编排 | 直接/派生 |
| MTE2 Bound 且接近带宽上限 | 算子本身读流量大，搬入已接近理论带宽 | Memory-bound 全部 | 实际 MTE2 耗时接近理论搬运耗时；BW usage 高 | 优化方向转为减少数据量、提高复用或用计算掩盖搬运 | 派生 |
| MTE3 Bound | 输出或中间写回主导，workspace 往返多 | Reduction、Sort、MatMul、FA | `ai*_mte3_ratio` 高；写流量放大；单次搬出粒度小 | 减少写回次数、合并输出、调整 workspace 生命周期 | 直接/派生 |
| 非连续搬运 | stride 访问、broadcast 轴选择错误、transpose 逐像素 DMA | Broadcast、Transpose、Conversion | MTE 指令密度高；带宽利用率低；L2 hit 低 | 先合轴，优先连续维搬运；必要时使用 NDDMA 或 UB Broadcast | 派生 |
| 地址/行宽未对齐 | GM 地址、row stride、Fixpipe 写回不满足对齐 | MatMul、FA、Transpose | `aic_fixpipe_ratio` 高；MTE 带宽低；尾块性能差 | 按 API 要求补齐 row stride，CopyOut 只写有效数据 | 直接/派生 |
| 多核搬运不均 | tail 集中、任务分配不均、部分核重复搬运更多 | 全部 | 各核 `ai*_mte2_time` / `ai*_mte3_time` 差异 >10% | 均衡 tile 分配，分散 tail，动态计算 usedCoreNum | 派生 |
| CacheMode 不适配 | 可复用数据未缓存，一次性数据污染 L2 | Broadcast、MatMul、FA、Reduction | `ai*_total_hit_rate < 50%`；MTE2 高；读流量放大 | 根据复用程度设置 CacheMode，优化访问顺序和切分 | 直接/派生 |
| MTE 与 Vector 资源冲突 | 搬运与计算时序过密，DB 编排不合理 | Vector-heavy 全部 | `aiv_vec_mte_cflt_ratio` 高；`aiv_vec_wait_ratio` / MTE wait 高 | 错开 MTE2/MTE3 与 Vector API，必要时调整流水节拍 | 直接/Trace |

## 按算子族诊断重点

### Elementwise

- 先检查是否存在 GM 往返的多步计算。若多段 elementwise 每段都写回 GM，优先考虑 UB 融合。
- DataCopy 粒度过小通常来自 tileLength 过小或小 shape 开核过多，交叉参考 [tiling 诊断矩阵](tiling-diagnosis-metrics.md) 的 `blockDim` 与 `tileLength` 问题。
- CopyOut 高时检查是否可以延迟写回到最终输出。

### Broadcast

- 重复搬运常来自合轴错误或 `ubSplitAxis` 选择不当。
- DAV_3510 上需要区分 NDDMA 与 UB Broadcast。NLast 且尾轴大时，NDDMA 反复读可能导致 L2 hit 低和 MTE2 高。
- 对标不同 broadcast shape，若同元素量但某些 rank/axis 明显慢，优先查非连续搬运和 CacheMode。

### Reduction

- RowSplit / ColSplit 会天然增加跨 chunk 搬入和 partial 合并，chunk 过小会导致 MTE 指令数和 workspace 往返增加。
- A 小 R 大时，单核串行归约会表现为单核 MTE/VEC 时间长；Group Reduce 可提高并行度，但会引入 partial workspace 写回，需要权衡 MTE3。
- `rLength` 和 `rLengthAlign` 混用会导致尾块非对齐搬运或错误写回。

### Sort / TopK

- tileSize 过小会放大 Sort/MrgSort 的搬运和归并次数。
- Pattern C 中应先核内归并再跨核归并，避免所有 tile 直接跨核归并带来大量 SyncAll 和 GM 往返。
- 重点看 Task Duration 随 N 的增长曲线、MTE 指令数和 trace 中同步等待。

### Conversion / Transpose

- small-channel transpose 避免逐像素 DMA 或标量 gather。优先按通道连续搬入，再在 UB 内重排。
- `tileN` / `tileNA` 混用会造成 tail 写回异常和小粒度 CopyOut。
- `repeats` 受 API 上限约束，不能为了减少搬运次数无限增大 tile。

### MatMul / GMM

- 搬运瓶颈通常来自 B 矩阵或 scale/bias 未复用、L1/L0 分块不合理、后处理写回过多。
- CUBE Bound 时不一定是坏事；若 MTE2 高且 L1/L0 带宽低，优先查 L1 驻留和 K-axis 滚动。
- GMM 组间 shape 差异会导致不同核搬运量不均。

### FlashAttention

- 默认 task 级模式下，KV 分块会重复经过 C1/V1/C2/V2。若 workspace 段设计不当，GM 自读自写会显著放大 MTE2/MTE3。
- 大 D 场景必须使用 streaming UB，避免常驻 `m × D` buffer。
- V1/V2 chunk loop 不对称或跨 loop 自读自写 slot 错误，CSV 可能只表现为 MTE 异常或性能波动，需 trace/精度对比确认。

## 快速排查顺序

1. 看 `PipeUtilization.csv`：确认是否 MTE2/MTE3/MTE1 主导。
2. 看 `Memory.csv`：计算单次搬运粒度和 MTE 指令密度。
3. 看带宽利用率：区分已接近硬件上限还是搬运效率差。
4. 算读写流量放大：与理论必要读写量对比，判断重复搬运和中间结果落 GM。
5. 看 `L2Cache.csv`：确认复用数据是否命中。
6. 看 `ResourceConflictRatio.csv`：确认 MTE wait 或 Vector-MTE 冲突。
7. 对搬运与计算未重叠、CopyIn/CopyOut 阶段占比、Sync/DB 问题，追加 trace 或代码阶段计时。
