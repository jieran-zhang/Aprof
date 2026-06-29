# 片上内存利用不足诊断矩阵

本文用于诊断 Ascend C 算子中的片上内存利用不足问题，包括 UB / L1 / L2 数据复用不足、临时 Tensor 占用过高、workspace 使用不合理、中间结果频繁落 GM 等。

使用时应交叉参考：

- [tiling 诊断矩阵](tiling-diagnosis-metrics.md)：UB 切分、Buffer 规划、L1/L0 容量、workspace slot。
- [数据搬运瓶颈诊断矩阵](data-movement-diagnosis-metrics.md)：GM 访问频繁、读写流量放大、L2 hit、CopyIn/CopyOut。
- [流水并行不足诊断矩阵](pipeline-parallel-diagnosis-metrics.md)：queue depth、stage 份数、workspace 轮转。

## 证据等级

- **直接**：msprof 字段或运行时硬件参数可直接支持判断。
- **派生**：需要结合 shape、dtype、TilingData、buffer 公式、理论读写量共同判断。
- **Trace/对比**：CSV 不足以确认，需要 timeline、不同配置、不同 shape 或代码插桩对比。

## 核心 Metric

### 1. 片上容量与占用

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| UB 占用率 | `Σ(UB buffer bytes * depth) / GetCoreMemSize(UB)` | TilingData、代码、`/npu-arch` | 判断临时 Tensor / queue / stage buffer 是否挤占 UB | 派生 |
| UB 有效载荷率 | `有效数据字节 / 实际UB占用字节` | shape、dtype、对齐长度、buffer 公式 | 判断 padding、对齐、tmp 过多是否浪费 UB | 派生 |
| L1 占用率 | `Σ(L1 buffer bytes * rotation) / GetCoreMemSize(L1)` | TilingData、代码、`/npu-arch` | MatMul / FA 判断 L1 驻留与分块是否合理 | 派生 |
| L0 占用率 | `L0A/L0B/L0C buffer bytes / 对应容量` | TilingData、代码、`/npu-arch` | 判断 K/M/N 基本块是否匹配 L0 容量 | 派生 |
| workspace 膨胀率 | `workspace bytes / 理论必要中间状态 bytes` | workspace size API、shape、算法公式 | 判断 workspace 是否按最大 shape 或过多 slot 预留 | 派生 |

### 2. 复用与 GM 流量

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| 读流量放大 | `read_main_memory_datas / 理论必需读数据量` | `Memory.csv` + shape/dtype/算法公式 | 判断本应片上复用的数据是否反复从 GM 读 | 派生 |
| 写流量放大 | `write_main_memory_datas / 理论必需写数据量` | `Memory.csv` + 输出/中间状态公式 | 判断中间结果或 workspace 是否频繁落 GM | 派生 |
| GM→UB 数据量 | `GM_to_UB_datas(KB)` | `Memory.csv` | Vector 路径判断 UB 复用不足或重复搬入 | 直接 |
| GM→L1 数据量 | `GM_to_L1_datas(KB)` | `Memory.csv` | Cube 路径判断 L1 复用不足 | 直接 |
| L0C→GM 数据量 | `L0C_to_GM_datas(KB)` | `Memory.csv` | MatMul/FA 判断结果是否绕过片上后处理直接落 GM | 直接 |
| L2 命中率 | `ai*_total_hit_rate(%)` | `L2Cache.csv` | <50% 时关注 CacheMode、数据局部性和切分顺序 | 直接 |

### 3. 片上带宽与冲突

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| UB Vector 带宽 | `aiv_ub_read_bw_vector`、`aiv_ub_write_bw_vector` | `MemoryUB.csv` | 判断 UB 内读写是否成为瓶颈或复用是否有效 | 直接 |
| UB Scalar 带宽 | `aiv_ub_read_bw_scalar`、`aiv_ub_write_bw_scalar` | `MemoryUB.csv` | Scalar 访问高时，常见于小 shape 或临时状态管理过多 | 直接 |
| L0/L1 带宽 | `aic_l0a/l0b/l0c_*_bw`、`aic_l1_*_bw` | `MemoryL0.csv`、`Memory.csv` | MatMul/FA 判断 L1/L0 分块和复用效率 | 直接 |
| UB bank conflict | `aiv_vec_total_cflt_ratio` 及 bank/bankgroup 子项 | `ResourceConflictRatio.csv` | 临时 Tensor 地址/stride 不合理会降低 UB 利用 | 直接 |
| MTE conflict | `aiv_vec_mte_cflt_ratio` | `ResourceConflictRatio.csv` | 片上搬运与计算争资源，常伴随流水编排不合理 | 直接 |

## 问题矩阵

| 问题 | 常见触发 | 适用算子族 | 诊断 Metric | 归因与处理 | 证据 |
| ------ | ---------- | ------------ | ------------- | ------------ | ------ |
| UB 数据复用不足 | 多步计算中间结果落 GM、未做 UB 融合、tile 太小 | Elementwise、Broadcast、Reduction、Transpose | GM→UB 数据量高；读流量放大；MTE2 高；UB 占用率低或有效载荷率低 | 合并 UB 内计算链，增加 tile 粒度，减少中间 GM 往返 | 派生 |
| UB 临时 Tensor 占用过高 | dtype 升精度、融合分支、tmp buffer、queue depth 全部按最大值预留 | Elementwise、Broadcast、Reduction、MatMul 后处理 | UB 占用率高；tileLength 被迫变小；MTE 指令密度高 | 按存活期复用 buffer，拆分互斥分支，减少不必要 stageNum | 派生 |
| UB 对齐/padding 浪费 | 对齐长度远大于有效长度，tail 使用完整 tile buffer | Reduction、Transpose、MatMul、FA | UB 有效载荷率低；tail case 慢；单次搬运粒度异常 | 区分有效长度与对齐长度，tail 用有效 count 写回 | 派生/对比 |
| UB bank conflict | 临时 Tensor 起始地址、blockStride、repeatStride 不合理 | Vector-heavy 全部 | `aiv_vec_total_cflt_ratio`、bank/bankgroup 子项高 | 调整 UB offset、padding、stride，让操作数错开 bank | 直接 |
| L1 数据复用不足 | MatMul B 矩阵/FA K/V 未驻留或 L1 rotation 不合理 | MatMul、GMM、FA | GM→L1 数据量高；MTE1/MTE2 高；L1 带宽利用异常 | 重新规划 L1_A/L1_B、rotation slots、K/M/N 分块 | 派生 |
| L0 复用不足 | K-axis 迭代或 L0C 累加策略不合理 | MatMul、FA | L0A/L0B/L0C 带宽低或频繁 GM/L1 往返；Cube 利用不稳 | 调整 baseM/baseN/baseK、L0C 累加、K-axis 分块 | 派生 |
| L2 命中率低 | 可复用数据未设置 CacheMode，或切分破坏局部性 | Broadcast、Reduction、MatMul、FA | `ai*_total_hit_rate < 50%`；MTE2 高；读流量放大 | 按复用模式设置 CacheMode，调整访问顺序和切分维度 | 直接/派生 |
| L2 被一次性数据污染 | 一次性读写也启用缓存，占用可复用数据空间 | Broadcast、MatMul、FA | L2 hit 低；不同 shape/顺序下波动大 | 对一次性数据禁用缓存，对复用数据保留缓存 | 派生/对比 |
| workspace 过度预留 | 按最大 shape / Sk_max / max batch 静态分配 | FA、Sort、Reduction、复杂融合 | workspace 膨胀率高；小 shape 内存占用异常 | workspace size 按运行时 shape 返回，不按最大上限预留 | 派生 |
| workspace slot 过多 | handshake/self-ref/task-state 统一用大 slot 数 | FA、复杂 mix kernel | workspace 膨胀率高；MTE3/MTE2 往返增加 | 按语义拆分 slot，分别使用独立槽数和取模公式 | 派生/Trace |
| workspace slot 不足 | 多 stage 共用同一段，互等或覆盖 | FA、MatMul/GMM、复杂融合 | trace 等待；周期性慢或精度漂移 | 增加必要轮转份数，区分跨 stage / 自读自写 / task-state | Trace/对比 |
| 中间结果频繁落 GM | 缺少 UB/L1/L0 融合，后处理拆成多 kernel 或多次写回 | Elementwise 融合、MatMul 后处理、FA | 写流量放大；MTE3 高；`L0C_to_GM_datas` 或 `UB_to_GM_datas` 高 | 融合后处理，延迟写回，尽量在片上完成连续阶段 | 派生 |
| 小 shape 片上资源过度配置 | queue、tmp、workspace 仍按大 shape 配置 | 全部 | 头开销占比高；UB 占用率高但有效载荷低；Scalar 高 | 小 shape 下减少 usedCoreNum、queue depth、workspace 份数 | 派生 |
| 动态 shape 下缓存策略不适配 | 固定 tile/cache/workspace 策略覆盖全部 shape | 全部 | 不同 shape 下 L2 hit、MTE、workspace 膨胀率波动 | Host Tiling 按 shape 重新决策 tile、CacheMode、workspace | 派生/对比 |

## 按算子族诊断重点

### Elementwise / Broadcast

- 优先检查多步计算是否能在 UB 内融合，避免每一步都 `UB→GM→UB`。
- Broadcast 重复读常来自合轴或 `ubSplitAxis` 错误，先看读流量放大和 L2 hit。
- UB tmp 过多会迫使 tileLength 变小，间接造成 DataCopy 粒度过小。

### Reduction

- RowSplit / ColSplit 的 partial 状态应尽量在 UB 内合并，避免每个 chunk 都落 GM。
- 多输出或 with-index 变体要显式列出 buffer 存活期，避免 result/index/tmp 全部常驻。
- Group Reduce 的 workspace 是必要成本，但要按实际 core/out size 分配。

### Sort / TopK

- Sort tmp 和 proposal buffer 会显著占用 UB，必须用 API 查询 tmp size。
- tileSize 过小会增加 GM 往返和归并 workspace；tileSize 过大则降低并行度。
- 跨核归并 workspace 应按实际 tile/core 数计算。

### MatMul / GMM

- 片上复用核心是 L1/L0/L0C：B 矩阵驻留、K-axis 迭代、L0C 累加和 Fixpipe 后处理。
- 若后处理拆出 GM，再由 AIV 读回，会表现为 `L0C_to_GM_datas`、GM→UB、UB→GM 同时升高。
- GMM 组间 shape 不均时，应按组评估 L1/L0 复用与 workspace 分配。

### FlashAttention

- 大 D 场景禁止常驻 `m × D` UB buffer，必须使用 streaming UB。
- GM workspace 用于跨 stage handshake 和 self-ref 状态时，要按运行时 Sk / D / task 数精确分配。
- slot 语义混用可能同时导致 workspace 膨胀、片上复用失败和精度漂移。

## 快速排查顺序

1. 先看 `Memory.csv`：读写主存量、GM→UB、UB→GM、GM→L1、L0C→GM 是否异常。
2. 计算读/写流量放大：与理论必要读写量对比。
3. 看 `L2Cache.csv`：确认 L2 hit 是否低于 50%。
4. 看 `MemoryUB.csv` / `MemoryL0.csv`：判断 UB/L0/L1 片上带宽是否合理。
5. 根据 TilingData / 代码计算 UB/L1/L0 占用率和 workspace 膨胀率。
6. 若中间结果落 GM，检查是否能 UB/L1/L0 融合或延迟写回。
7. 对 workspace slot、动态 shape、缓存策略问题，用不同 shape / 不同配置对比确认。
