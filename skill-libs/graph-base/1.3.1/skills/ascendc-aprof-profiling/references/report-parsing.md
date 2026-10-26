# 原始报告解析与证据交接

新性能时间按 [统一协议](unified-timing.md)重建完整调用。机制指标通过 [collector](collector-interface.md)采集并归一化到 source-bound 1.1 profile。两类数据不能互相代替。

## 先核验身份，再解释数值

每份机制 manifest 明确 workload、实现角色、设备、kernel 和 collection。npu-compute 对照该 collection 的 OpInfoSummary；msprof 对照已记录 OpBasicInfo 与 kernel 目录。不能把 JSONL 转 CSV 后声称是原始来源。

runtime 核验原始文件、选择器、独立 capture 清单、聚合及比较身份。保留准确文件名、hash、字段、单位、NA 和缺证据。schema 只验结构，来源回放验证引用内容。

| 后端 | 原始视图 | 解释范围 |
| --- | --- | --- |
| npu-compute | Section CSV、summary.jsonl、HardwareInfo.jsonl、PipeTrace.json | 见 [工具证据](../../tool-npu-compute/references/evidence.md)，Task 与 Core 行聚合范围不同 |
| msprof op | OpBasicInfo、PipeUtilization、Memory、ArithmeticUtilization、ResourceConflictRatio、L2Cache、MemoryUB、MemoryL0 | 核对真实字段、kernel/Core 身份及带时间戳文件名 |
| 辅助 msprof | PROF_GROUP/PROF CSV 与人工摘要 | 摘要仅供导航，值来自原始 CSV |
| simulator | trace.json、指令/代码执行 CSV | 可行性和 trace 代理，不是实际硬件收益 |

搬运粒度或流量放大假设要记录理论字节下界、Core/Task 聚合及公式。利用率必须有实际硬件分母，缺分母保持未知。

## 机制样本与比较

先按声明规则聚合单次 capture 内的行，再按 capture 顺序构成 samples 并执行外层聚合。Core 行、Section 记录和内部 replay 数不是独立重复数。即使归因使用聚合值，也保留逐 Core 数据供不均衡诊断。

JSONL Section 均值与 CSV Core 中位数是不同指标。比较必须同后端、选择器语义、单位、聚合、workload 及兼容环境。不得把机制 profile duration 填入统一性能结果或旧配对数组。

归一化器报告缺失与不稳定；runtime 决定机制证据是否充分。单 capture 仍是探索观察，增加 Core 行不能使它变成独立复现。策略不满足机制要求时标记 `measurement_limited`，保留原始数据。

## 症状草稿

旧 msprof 报告可用：

```bash
python3 scripts/compress_msprof.py --input <report-root> --op-name <exact-kernel-name> --output <symptoms.json>
```

只有具备硬件/workload 证据时才提供 `--available-cores` 或 `--theoretical-gm-bytes`。保留 extractor 版本、阈值、未知谓词和候选机制集合。不要把 npu-compute 报告交给旧 compressor，同名 CSV 不具备相同身份和字段契约。

模拟 Chrome trace 使用 ops-simulator 分析器，npu-compute Pipeline 使用其 inspector 与采样组规则；二者都不能把重叠忙区间的和当作整体延迟。

当前 Agent 交接使用 [profiling contract](../../../workflows/contracts/profiling.md)，标明单 capture、代理或不稳定结论。工具若已生成 profiling_results.json，则直接引用，不额外复制同义摘要；它不是机器判决。机器接口见 [契约说明](../../../workflows/references/runtime-contracts.md)。
