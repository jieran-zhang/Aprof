---
name: ops-simulator
description: 使用本地工具分析 Ascend simulator 的指令与流水间隙，保留代理证据标识及目标能力边界。
---

# AProf 模拟器证据

确认配置目标及已安装 `cannsim` 或 `msprof op simulator` 的参数支持。以小规模、正确性已通过的输入和明确超时运行，保留版本、命令与 trace。模拟指标只代表指令/流水代理证据，不能当作硬件延迟或生产收益。

已有 Chrome trace 可用本地分析器：

```bash
python3 scripts/trace_bubble_analyzer.py <trace-or-directory> --json -o <report.json>
```

结合源码依赖分析间隙，区分预热、收尾和稳态。搬运、事件、缓冲问题见 [执行机制](../ascendc-aprof-optimization/knowledge/branches/pipeline-sync/ROUTER.md)；确认支持的架构与 SDK 后才读 [RegBase/SIMT](../npu-arch/references/regbase-simt.md)。这些本地资料已承接此前 simulator 的外部 regbase/direct-invoke 依赖。trace 不能补出硬件计数器，也不能验证目标 SDK 没有的 API。
