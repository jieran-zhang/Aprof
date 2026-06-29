# API 与算法实现低效诊断矩阵

本文用于诊断 Ascend C 算子中的 API 与算法实现低效问题，包括 Scalar 循环过多、Vector / Cube API 使用不充分、Cast 冗余、Reduce / Matmul 实现低效、算子融合不足等。

使用时应交叉参考：

- `/ascendc-api-best-practices`：API 选型、参数约束、黑名单、流水线和 Buffer 用法。
- [AI Core 利用率低诊断矩阵](ai-core-utilization-diagnosis-metrics.md)：Vector / Cube 利用率、Scalar 占比、AIC/AIV 配比。
- [数据搬运瓶颈诊断矩阵](data-movement-diagnosis-metrics.md)：融合不足导致的 GM 往返。
- [流水并行不足诊断矩阵](pipeline-parallel-diagnosis-metrics.md)：API 顺序、同步、queue 对性能的影响。

## 证据等级

- **直接**：msprof 字段或 API 黑名单可直接支持判断。
- **派生**：需要结合代码 API 调用、shape、dtype、TilingData 和 profiling 指标判断。
- **Trace/对比**：需要替换实现、关闭某分支、不同 dtype/shape 或 timeline 对比确认。

## 核心 Metric

### 1. Scalar 与控制开销

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| Scalar 占比 | `ai*_scalar_ratio` | `PipeUtilization.csv` | >30% 通常说明标量控制或小 shape 头开销明显 | 直接 |
| Scalar 时间 | `ai*_scalar_time(us)` | `PipeUtilization.csv` | 判断标量循环/分支对总耗时的绝对影响 | 直接 |
| 头开销占比 | `(Task Duration - max(ai*_time)) / Task Duration` | `OpBasicInfo.csv` + `PipeUtilization.csv` | 小 shape、TilingData 大、TPipe 初始化多时升高 | 派生 |
| ICache miss | `ai*_icache_miss_rate` | `PipeUtilization.csv` | 代码路径复杂、模板/分支过多时需关注 | 直接 |

### 2. Vector / Cube API 利用

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| Vector 占比 | `aiv_vec_ratio` | `PipeUtilization.csv` | 判断 Vector 是否主导或是否被 Scalar/MTE 掩盖 | 直接 |
| Vector 理论利用率 | `aiv_vec_fops / (aiv_time * vector_peak_flops)` | `ArithmeticUtilization.csv` + `/npu-arch` | 判断 Vector API 是否有效利用算力 | 派生 |
| Cube 占比 | `aic_cube_ratio` | `PipeUtilization.csv` | MatMul/FA 判断 Cube 是否有效工作 | 直接 |
| Cube 理论利用率 | `aic_cube_fops / (aic_time * cube_peak_flops)` | `ArithmeticUtilization.csv` + `/npu-arch` | 判断 Cube API / Matmul 分块是否有效 | 派生 |
| 指令类型占比 | `aiv_vec_fp32_ratio`、`aiv_vec_fp16_ratio`、`aiv_vec_misc_ratio`、`aic_cube_fp16_ratio` 等 | `ArithmeticUtilization.csv` | 判断 Cast、misc、dtype 路径是否异常 | 直接 |

### 3. Cast 与 dtype 开销

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| FP32 Vector 占比异常 | `aiv_vec_fp32_ratio` 高于预期 | `ArithmeticUtilization.csv` + dtype 需求 | FP16/BF16 输入下可能存在过多升精度或 Cast | 派生 |
| Cast 链路次数 | `Cast` API 调用次数 / tile 或 / 元素 | 代码审查 | 判断是否多次往返 Cast | 派生 |
| Cast buffer 占用 | `Cast 输入/输出/中间 buffer bytes / UB` | TilingData + 代码 | Cast 冗余会压缩 tileLength、增加搬运 | 派生 |
| dtype 分支性能差异 | 同 shape 不同 dtype 的 Duration / Vec ratio 对比 | profiling 对比 | 判断 dtype 分支是否实现不对称 | Trace/对比 |

### 4. 融合与 GM 往返

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| 读流量放大 | `read_main_memory_datas / 理论必需读数据量` | `Memory.csv` + 算法公式 | 未融合导致反复 GM 读时升高 | 派生 |
| 写流量放大 | `write_main_memory_datas / 理论必需写数据量` | `Memory.csv` + 输出公式 | 中间结果多次落 GM 时升高 | 派生 |
| GM 往返次数 | 计算图中 `GM→UB→Compute→GM` 段数 | 代码/图结构 | 判断是否可 UB 融合 | 派生 |
| MTE2/MTE3 占比 | `ai*_mte2_ratio`、`ai*_mte3_ratio` | `PipeUtilization.csv` | 融合不足常表现为搬运占比高 | 直接 |

## 问题矩阵

| 问题 | 常见触发 | 适用算子族 | 诊断 Metric | 归因与处理 | 证据 |
| ------ | ---------- | ------------ | ------------- | ------------ | ------ |
| Scalar 循环过多 | 用 for 循环逐元素处理、GetValue/SetValue、复杂 if 分支 | 全部 | `ai*_scalar_ratio >30%`；Scalar time 高；ICache miss 高 | 改用 Vector API、DataCopyPad、批量处理；循环不变量移到 Host | 直接/派生 |
| GlobalTensor GetValue/SetValue | 生产代码中单点读写 GM | 全部 | Scalar 高；MTE 粒度小；代码命中 API 黑名单 | 用 DataCopy/DataCopyPad 批量搬运，调试外禁止使用 | 直接 |
| Vector API 粒度过小 | count/repeat 太小，tile 切分过细，tail 走小分支 | Vector-heavy 全部 | Vector 理论利用率低；Scalar/MTE 高；单次搬运粒度小 | 增大 tileLength，合并连续 Vector 调用，tail 复用主路径 | 派生 |
| Vector API 参数未充分利用 | 未使用 repeat/stride/broadcast 参数，手写循环调用 API | Elementwise、Broadcast、Reduction 后处理 | Scalar 高；API 调用次数多；Vector ratio 不高 | 用 BinaryRepeatParams、Adds/Muls、repeatStride/blockStride 等批量能力 | 派生 |
| Cast 冗余 | FP16/BF16 与 FP32 之间多次往返，Cast buffer 不复用 | Elementwise、Reduction、MatMul 后处理 | `aiv_vec_fp32_ratio` 异常；Cast 调用多；UB 占用高 | 合并 Cast，批量一次转换；精度允许时减少升精度 | 派生/对比 |
| dtype 分支实现不对称 | 某 dtype 走标量或额外 Cast，另一个 dtype 走向量化 | 全部 | 同 shape 不同 dtype 性能差异异常 | 对齐各 dtype 分支 API 路径，必要时拆 target 或 Tiling 分支 | Trace/对比 |
| Reduce 实现低效 | 未用 Reduce API / Pattern::Reduce，手写循环或跨 chunk 合并过多 | Reduction、Softmax、LayerNorm | Scalar 高；VEC/MTE 都高；partial workspace 多 | 按 AR/ARA/Group Reduce 选择算法，使用低延迟归约和正确 tmp buffer | 派生 |
| Reduce 后广播低效 | Duplicate 标量再逐元素运算，未使用 Adds/Muls 或 stride=0 参数 | Reduction 后处理、Norm | Scalar 或 VEC misc 高；UB tmp 多 | 使用 Adds/Muls 或 BinaryRepeatParams 的广播能力 | 派生 |
| Matmul 实现低效 | 未用合适 Matmul/GMM API，baseM/N/K 不合理，Cube 不饱和 | MatMul、GMM、FA | `aic_cube_ratio` 低；Cube 理论利用率低；MTE1/MTE2 高 | 按平台选择 MatmulImpl/GMM/Blaze 路径，调整 tiling 与 L1/L0 复用 | 派生 |
| MatMul 后处理拆分低效 | Cube 结果先落 GM，再由 Vector 读回做后处理 | MatMul 融合、GMM、FA | `L0C_to_GM_datas`、GM→UB、UB→GM 同时升高；MTE 高 | 尽量用 Fixpipe / UB epilogue 融合后处理，延迟最终写回 | 派生 |
| 算子融合不足 | 多个 elementwise/reduce/cast kernel 分开执行 | Elementwise 链、Norm、MatMul 后处理 | 读/写流量放大；MTE2/MTE3 高；Task Duration 多段累加 | 做 UB 融合，减少 GM 往返；融合后重新评估 UB bufferNum | 派生 |
| API repeat 上限处理低效 | repeatTimes 超限后退化为标量或过多小循环 | Transpose、Elementwise、Broadcast | Scalar 高；API 调用次数多；tail/大 shape 慢 | 按 repeat 上限分批，保持每批向量化，不退化到逐元素 | 派生 |
| 复杂通用算法覆盖所有 shape | 单一路径包含大量分支和保守 buffer | 全部 | ICache miss 高；Scalar 高；小 shape 头开销高 | 按关键 shape/dtype 分支，移出运行期不变量，缩小 TilingData | 派生 |
| API 使用导致 UB 冲突 | LocalTensor offset/stride 不合理，repeatStride 触发 bank conflict | Vector-heavy 全部 | `aiv_vec_total_cflt_ratio`、bank/bankgroup 高 | 调整 UB 地址、padding、stride 参数，避免多操作数同 bank | 直接 |

## 按算子族诊断重点

### Elementwise / Broadcast

- 重点查是否手写逐元素循环，是否没有使用 repeat / stride / broadcast 参数。
- Add/Sub 半精度链路需区分精度要求：必要时升精度，但避免多次 Cast 往返。
- 多步 elementwise 应优先 UB 融合，避免每步写 GM。

### Reduction / Norm / Softmax

- 先按 AR / ARA / 多轴 / Group Reduce 判断算法，不要默认手写循环。
- Reduce 后标量或向量广播优先用 Adds/Muls 或 BinaryRepeatParams。
- Welford、二分累加等算法选择应服务于精度与性能，不应无条件套用。

### Sort / TopK

- Sort / Concat / MrgSort tmp size 必须用 API 查询，不要手估。
- 若 TopK 小而 N 大，检查是否仍做了全量排序或过多归并。
- 归并阶段的 API 调用粒度和 SyncAll 轮次需要结合 trace 判断。

### MatMul / GMM

- A2/A3 通用 MatMul / GMM 优先参考 `/ascendc-api-best-practices` 的 Matmul/GMM 高阶 API。
- 950 路径不要直接套 A2/A3 MatmulImpl 经验，需按平台 skill 选择实现。
- 后处理尽量与 Fixpipe / UB epilogue 融合，避免 C 矩阵 GM 往返。

### FlashAttention

- FA 是算法结构主导的多 stage 算子，不能把 Reduction/MatMul/Elementwise 模式简单拼接。
- Softmax、P·V、V2 累积的 API 顺序和 workspace 设计会同时影响性能与正确性。
- MX 类格式和量化路径必须遵守 reduction 轴量化约束，不可只按连续维直觉实现。

## 快速排查顺序

1. 看 `PipeUtilization.csv`：Scalar、VEC、CUBE 谁主导。
2. 看 `ArithmeticUtilization.csv`：Vector/Cube 指令类型、fops、fp32/fp16/misc 占比是否异常。
3. 看 `Memory.csv`：是否因为 API/融合不足造成 GM 往返。
4. 审查代码 API：是否命中 GetValue/SetValue、手写逐元素循环、重复 Cast、未用 Reduce/Matmul 高阶 API。
5. 对比 dtype / shape / 融合前后版本，确认是否某条 API 路径导致性能断崖。
6. 若 Scalar 高且数据量小，先排除小 shape 头开销，再判断 API 实现问题。
7. 若 Vector/Cube 利用率低，交叉参考 [AI Core 利用率低诊断矩阵](ai-core-utilization-diagnosis-metrics.md)。
