# AI Core 利用率低诊断矩阵

本文用于诊断 Ascend C 算子中的 AI Core 利用率低问题，包括 Vector / Cube 计算单元利用率不足、多核负载不均、部分 core 空闲、尾核拖尾明显等。

使用时应交叉参考：

- [tiling 诊断矩阵](tiling-diagnosis-metrics.md)：`blockDim`、`totalTiles`、tail、动态 shape、AIC/AIV 配比。
- [流水并行不足诊断矩阵](pipeline-parallel-diagnosis-metrics.md)：流水线气泡、AIC/AIV 节拍不匹配、wait ratio。
- [数据搬运瓶颈诊断矩阵](data-movement-diagnosis-metrics.md)：MTE 主导导致计算单元闲置。

## 证据等级

- **直接**：msprof 字段或运行时硬件参数可直接支持判断。
- **派生**：需要结合 shape、TilingData、理论任务数或各核时间计算。
- **Trace/对比**：CSV 不足以确认，需要 timeline、不同 shape 或不同 blockDim 配置对比。

## 核心 Metric

### 1. 核数利用

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| AIV 核利用率 | `Block Dim / GetCoreNumAiv()` | `OpBasicInfo.csv` + `/npu-arch` | Vector 算子判断是否用满可用 Vector Core | 直接 |
| AIC 核利用率 | `Block Dim / GetCoreNumAic()` | `OpBasicInfo.csv` + `/npu-arch` | Cube 算子判断是否用满可用 Cube Core | 直接 |
| 有效核数 | `min(Block Dim, totalTasks 或 totalTiles)` | TilingData + shape | 判断是否存在空核或过开核 | 派生 |
| 空闲核比例 | `(Block Dim - effectiveActiveCores) / Block Dim` | TilingData + `PipeUtilization.csv` | 判断启动了但没有有效工作的 core 比例 | 派生 |
| 任务覆盖率 | `totalTasks / coreNum` 或 `totalTiles / coreNum` | TilingData + `/npu-arch` | 判断任务数是否足够喂满核 | 派生 |

### 2. 核间负载均衡

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| 核间耗时不均衡 | `(max(ai*_time) - min(ai*_time)) / max(ai*_time)` | `PipeUtilization.csv` | >10% 需关注，>30% 通常严重不均 | 派生 |
| 最慢核定位 | `argmax(ai*_time)` / `block_id` | `PipeUtilization.csv` | 最后 block 最慢时优先怀疑 tail 集中 | 派生 |
| 最快核闲置迹象 | `min(ai*_time) << median(ai*_time)` | `PipeUtilization.csv` | 判断是否有部分 core 工作量过少 | 派生 |
| 分 pipe 不均衡 | 各核 `aiv_vec_time`、`aic_cube_time`、`ai*_mte2_time` 分别计算 max/min | `PipeUtilization.csv` | 判断不均来自计算、搬运还是写回 | 派生 |

### 3. 计算单元利用

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| Vector 占比 | `aiv_vec_ratio` | `PipeUtilization.csv` | 判断 Vector 是否主导或是否被其它 pipe 掩盖 | 直接 |
| Cube 占比 | `aic_cube_ratio` | `PipeUtilization.csv` | MatMul/FA 判断 Cube 是否有效工作 | 直接 |
| Vector 理论利用率 | `aiv_vec_fops / (aiv_time * vector_peak_flops)` | `ArithmeticUtilization.csv` + `/npu-arch` | 判断 Vector 算力利用是否接近理论 | 派生 |
| Cube 理论利用率 | `aic_cube_fops / (aic_time * cube_peak_flops)` | `ArithmeticUtilization.csv` + `/npu-arch` | 判断 Cube 算力利用是否接近理论 | 派生 |
| 计算/搬运占比差 | `aiv_vec_ratio 或 aic_cube_ratio` vs `MTE2/MTE3 ratio` | `PipeUtilization.csv` | MTE 主导时计算单元可能空等 | 派生 |

### 4. 等待与气泡

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| Vector wait | `aiv_vec_wait_ratio` | `ResourceConflictRatio.csv` | Vector 等待搬运、同步或资源时升高 | 直接 |
| Cube wait | `aic_cube_wait_ratio` | `ResourceConflictRatio.csv` | Cube 等待 AIV、MTE 或同步时升高 | 直接 |
| MTE wait | `ai*_mte2_wait_ratio`、`ai*_mte3_wait_ratio` | `ResourceConflictRatio.csv` | 计算单元可能因搬运等待而空闲 | 直接 |
| 流水线气泡 | 多个 pipe 比例均在 30%-50%，无明显主导单元 | `PipeUtilization.csv` + trace | 利用率低但不是单一瓶颈时重点检查流水 | 派生/Trace |
| 头开销占比 | `(Task Duration - max(ai*_time)) / Task Duration` | `OpBasicInfo.csv` + `PipeUtilization.csv` | 小 shape 或过多核启动导致有效计算占比低 | 派生 |

## 问题矩阵

| 问题 | 常见触发 | 适用算子族 | 诊断 Metric | 归因与处理 | 证据 |
| ------ | ---------- | ------------ | ------------- | ------------ | ------ |
| `blockDim` 过小 | Tiling 固定核数，任务数够但没有用满硬件 | 全部 | AIV/AIC 核利用率低；`Block Dim < coreNum`；Duration 高 | 动态使用 `min(coreNum, totalTasks)`，必要时减小 tile 增加任务数 | 直接/派生 |
| 任务数少于核数 | tileLength 过大、shape 小、task 维度构造不足 | Elementwise、Broadcast、Sort、Transpose、FA | `totalTiles/totalTasks < coreNum`；有效核数低 | 调整 tileLength、任务维度或小 shape 减核 | 派生 |
| 过开核导致有效利用低 | 小 shape 仍开满核，单核数据量太少 | 全部 | 头开销占比高；`ai*_scalar_ratio` 高；空闲核比例高 | 小 shape 动态减少 usedCoreNum，合并小任务 | 派生 |
| 部分 core 空闲 | 启动核数大于 totalTasks/totalTiles，或入口没有正确早返回 | 全部 | 有些 block 的 `ai*_time` 极低或无有效 pipe 时间 | `usedCoreNum = min(coreNum, totalTasks)`，空闲核入口直接返回 | 派生 |
| 核间负载不均 | `N % blockDim`、`totalTiles % blockDim`、分组 shape 差异 | 全部 | 核间耗时不均衡 >10%；分 pipe 不均衡 | 均匀分配 tile，分散 tail，GMM/FA 按实际任务量调度 | 派生 |
| 尾核拖尾明显 | tail 全落最后一个 block，尾块走慢分支 | 全部 | 最慢核为最后 block；tail case 慢；MTE/Scalar 异常 | tail 分散到多个核，tail 复用主路径，避免标量/小 copy 分支 | 派生/Trace |
| Vector 利用不足 | MTE/Scalar/同步主导，或 Vector API 粒度太小 | Vector-heavy 全部 | `aiv_vec_ratio` 低；MTE2/MTE3/Scalar 高；Vector wait 高 | 增大 vector 粒度，减少搬运/同步，检查 UB conflict | 直接/派生 |
| Cube 利用不足 | M/N/K 分块不合理，L1/L0 复用不足，AIC 等 AIV | MatMul、GMM、FA | `aic_cube_ratio` 低；MTE1/MTE2 或 Cube wait 高；Cube 理论利用低 | 调整 baseM/baseN/baseK、L1/L0 复用、AIC/AIV 节拍 | 直接/派生 |
| AIC/AIV 配比不匹配 | Cube 阶段和 Vector 后处理耗时差异大 | MatMul、GMM、FA | AIC/AIV time 差大；Cube/Vector wait 高；流水线气泡 | 调整 mix kernel 配比、stage/workspace 份数或后处理融合策略 | 派生/Trace |
| 搬运瓶颈导致计算单元空等 | MTE2/MTE3 主导，计算 pipe 占比低 | 全部 | MTE ratio 高；Vector/Cube ratio 低；MTE wait 或 bandwidth 异常 | 参考 [数据搬运瓶颈诊断矩阵](data-movement-diagnosis-metrics.md) 减少搬运或掩盖搬运 | 直接/派生 |
| 流水气泡导致利用率低 | DB 未生效、queue depth 不足、同步等待多 | 全部 | 多 pipe 都不满；wait ratio 高；trace 有空洞 | 参考 [流水并行不足诊断矩阵](pipeline-parallel-diagnosis-metrics.md) 修复 DB、queue、同步 | 派生/Trace |
| 动态 shape 下策略不适配 | 固定 blockDim/tile/task 规则覆盖大小 shape | 全部 | 不同 shape 下核利用率、负载均衡波动大 | Host Tiling 按 shape 重算 usedCoreNum、tile 和分支策略 | 派生/对比 |
| Reduction A 维任务不足 | 外层 A 太小，R 轴单核串行 | Reduction | 核利用率低；少数核 `aiv_time` 长 | A 不足时评估 Group Reduce 或跨 R 分段并行 | 派生 |
| Sort 归并阶段串行拖尾 | 归并轮次多，跨核同步后部分核等待 | Sort/TopK | trace SyncAll 等待；后期 active core 下降 | 先核内归并再跨核归并，调整 tileSize 和归并路数 | Trace |
| FA decode 任务数不足 | Sq=1、大 Sk、batch/head 少，默认 task 级吃不满核 | FlashAttention | `totalTasks << aicNum`；少数核长时间执行 s2 loop | 评估 split-KV reduce，并补 partial workspace + cross-core combine | 派生 |

## 按算子族诊断重点

### Elementwise / Broadcast / Transpose

- 以 AIV 核利用率、totalTiles、单核元素数为主线。
- tile 太大时核数吃不满；tile 太小时 MTE/Scalar 开销抬高，利用率仍低。
- Broadcast 还要检查合轴和 `ubSplitAxis` 是否导致任务维度不足或搬运不均。

### Reduction

- A 维提供天然并行度，A 太小时需考虑 Group Reduce 或 R 维分段。
- RowSplit / ColSplit 的 chunk 太小会提升并行度但增加搬运与合并开销，需要同时看 MTE 和负载均衡。
- 尾行/尾列不要集中到最后一个核。

### Sort / TopK

- Pattern A 天然单核，不能误判为 blockDim 问题；只有 N 足够大时才期待多核。
- Pattern B/C 要看 totalTiles、归并轮次和 SyncAll 等待。
- 归并后期活跃核减少是算法阶段特征，但可通过两级归并减少等待。

### MatMul / GMM

- 先看 `usedCoreNum = ceil(M/singleCoreM) * ceil(N/singleCoreN)` 是否足够。
- Cube 利用低时同时检查 L1/L0 复用、K-axis 迭代和 Fixpipe 后处理。
- GMM 需要按 group 统计任务量，避免大组拖尾、小组核空闲。

### FlashAttention

- 默认 task 维通常来自 batch、kvHead、Sq 分块、G 分块；s2 默认不进入 taskIdx。
- decode 场景若任务数远小于 AIC 核数，应评估 split-KV reduce。
- AIC/AIV wait 和 workspace slot 问题常同时影响性能与正确性，需 trace + 精度 case 共同确认。

## 快速排查顺序

1. 看 `OpBasicInfo.csv`：`Block Dim`、`Task Duration`、频率是否正常。
2. 用 `/npu-arch` 获取 AIV/AIC 核数，计算核利用率。
3. 从 TilingData / shape 计算 `totalTasks` 或 `totalTiles`，确认任务覆盖率。
4. 用 `PipeUtilization.csv` 计算各核 `ai*_time` 不均衡和最慢核。
5. 看 Vector/Cube/MTE/Scalar ratio，判断计算不足是因为搬运、同步、标量还是算法本身。
6. 看 wait ratio 和 trace，确认是否流水气泡或 AIC/AIV 互等。
7. 对 tail、小 shape、动态 shape 分别采样，避免把单个边界 case 误判为整体利用率问题。
