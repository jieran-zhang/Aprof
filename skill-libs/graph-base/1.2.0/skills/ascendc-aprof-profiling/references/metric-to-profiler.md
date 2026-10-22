# 架构与指标路由

先核对真实 SoC 和已安装工具能力，再选机制指标。当前优化重点是 910C/A3 Vector；后端支持 950 不等于所有 950 算子已验证。

| 环境 | 机制后端 | 边界 |
| --- | --- | --- |
| 兼容 950/dav-3510 | npu-compute | 支持的单算子与已安装 Sections |
| 910C/A3 | msprof op | 不安装不兼容 npu-compute |
| 其他/未知 | 显式预检 | 不能仅由 DAV_2201 或工具存在推断 |
| 无硬件/要求模拟 | msprof op simulator | 仅代理证据 |

| 诊断问题 | npu-compute 视图 |
| --- | --- |
| kernel Task 时间、block 数、身份 | summary.jsonl / OpInfoSummary |
| Scalar/Vector/MTE 活跃与核间均衡 | PipeUtilization |
| 流量放大、搬运粒度 | Memory 加 workload 字节下界 |
| 算术利用率 | ArithmeticUtilization 加实际架构分母 |
| 等待与冲突 | ResourceConflictRatio |
| UB/L0 流量 | MemoryUB / MemoryL0 |
| 缓存命中/缺失 | L2Cache |
| 采样流水重叠 | Pipeline / PipeTrace.json |

解释前读取 [工具语义](../../tool-npu-compute/references/evidence.md)。PipeUtilization 和 Memory 联合提供带宽分析依赖，单 Pipe 视图不足。按假设选择最小 Section 集；trace 采样不能证明全部 Core 覆盖或完整 kernel 时间。

msprof 使用实际可用 CSV，不能假设同名字段和 npu-compute 语义相同。命令见 [msprof 映射](metric-to-msprof.md)，重复机制采集与来源回放见 [collector](collector-interface.md)。

上述视图用于机制诊断；性能反馈和收尾统一使用 [Task 计时协议](unified-timing.md)，不得用 PMU 中的 duration 替代目标计时。
