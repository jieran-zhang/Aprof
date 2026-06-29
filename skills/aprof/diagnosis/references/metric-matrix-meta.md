# 性能问题与 Metric 诊断矩阵生成方法

本文用于指导新增性能问题族的诊断矩阵。目标是把“性能现象”稳定映射到算子分类、msprof 可观测字段、派生指标、NPU 架构参数和证据等级。

## 输入信息

生成矩阵前先收集以下信息：

| 输入 | 内容 | 来源 |
| ------ | ------ | ------ |
| 问题族 | 例如 Tiling、搬运、同步、Cache、Bank Conflict、MatMul 后处理、Workspace 等 | 用户问题、代码审查、profiling 现象 |
| 算子分类 | Elementwise、Broadcast、Reduction、Sort/TopK、Conversion、MatMul、FlashAttention 等 | `/ascendc-tiling-design` 或对应设计 Skill |
| 可观测字段 | `OpBasicInfo.csv`、`PipeUtilization.csv`、`Memory.csv`、`L2Cache.csv`、`ResourceConflictRatio.csv` 等字段 | `/ops-profiling` |
| 架构分母 | AIC/AIV 核数、UB/L1/L0/L2/BT 容量、频率、理论带宽、理论算力 | `/npu-arch`、运行时 `PlatformAscendC` |
| 上下文 | shape、dtype、TilingData、workspace size、blockDim、tile 参数、buffer 公式 | 算子代码、Host Tiling、日志 |
| 辅助证据 | trace、timeline、不同 shape 对比、基线实现对比、精度失败模式 | profiling 归档、测试结果 |

## 生成步骤

1. 定义问题边界。
   - 明确这是一类性能问题，而不是泛化的“所有优化建议”。
   - 写清适用算子族和不适用范围。
   - 规划中或未验证的算子族只保留通用判断，不写专属规则。

2. 枚举可观测字段。
   - 先列 msprof 直接字段，例如 `Block Dim`、`Task Duration(us)`、`ai*_mte2_ratio`、`aiv_vec_total_cflt_ratio`。
   - 字段名必须来自已有文档、采集文件或用户提供材料。
   - 如果字段是否存在依赖工具版本或采集模式，必须标注条件。

3. 构造派生 metric。
   - 用硬件分母归一化，例如 `Block Dim / GetCoreNumAiv()`。
   - 用数据量和指令数构造效率指标，例如 `GM_to_UB_datas / ai*_mte2_instructions`。
   - 用各核时间构造负载指标，例如 `(max(ai*_time) - min(ai*_time)) / max(ai*_time)`。
   - 派生公式中涉及硬件容量、核数、频率时，必须使用运行时查询值或明确来源。

4. 标注证据等级。
   - **直接**：单个字段或运行时硬件查询即可支持判断。
   - **派生**：需要多个字段、shape、TilingData 或代码公式共同判断。
   - **Trace/对比**：CSV 不足以确认，需要 timeline、trace、不同 shape 或基线对比。

5. 建立诊断矩阵。
   - 推荐列：`问题 | 常见触发 | 适用算子族 | 诊断 Metric | 归因与处理 | 证据`。
   - 每一行只描述一个可复用问题，不把多个根因混在一起。
   - “归因与处理”应给出下一步验证或修正方向，不只写结论。

6. 补充快速排查顺序。
   - 从全局字段开始：`Task Duration`、`Block Dim`、频率。
   - 再看主瓶颈：VEC、CUBE、SCALAR、MTE、Fixpipe、UB conflict、L2。
   - 最后处理 CSV 难确认的问题：同步、DB、slot、PipeBarrier、跨核 race。

## 矩阵模板

```markdown
## <问题族> 问题

| 问题 | 常见触发 | 适用算子族 | 诊断 Metric | 归因与处理 | 证据 |
| ------ | ---------- | ------------ | ------------- | ------------ | ------ |
| <单一问题> | <触发条件> | <算子族> | <字段或派生公式> | <根因判断与下一步> | 直接/派生/Trace |
```

## 质量门禁

- 不编造 API、CSV 字段、硬件参数或阈值。
- 不确定的信息必须标注“需用户验证”或“需 trace/对比确认”。
- 硬件容量、核数和频率禁止写死，必须以 `PlatformAscendC` 或实际采集字段为准。
- 阈值只能来自 `/ops-profiling`、`/npu-arch`、官方文档、采集数据或用户提供资料。
- 对无直接硬件计数器的问题，必须明确写成派生证据或 Trace/对比证据。
- reference 文档保持一层链接，避免让主 `SKILL.md` 承载过多细节。

## 输出要求

给用户诊断时按以下顺序组织：

1. 先给最可能的问题和证据等级。
2. 再列关键 metric 与计算方式。
3. 再说明适用算子族和可能例外。
4. 最后给下一步采集、对比或代码检查建议。
