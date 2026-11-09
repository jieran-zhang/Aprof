---
name: tool-ops-optimize
description: AProf graph-base 1.3.2 入口，按角色和阶段契约组织 Ascend C 代码理解、机制诊断、并行规划、优化与统一计时。
license: CANN-2.0
---

# AProf graph-base 1.3.2

从[协调者技能](skills/ascendc-aprof-coordinator/SKILL.md)和[主工作流](workflows/aprof-performance-workflow.md)开始。
保留完整目录；安装与独立验证见 [README](README.md)，接入范围见 [IMPORT](IMPORT.md)。
本包未封版，历史实验结果不作为本版本新增硬件验证。

## 使用参考

从[参考索引](references/README.md)读取分阶段说明。当前设备收益证据覆盖 910C/A3 Vector。Cube 或混合 kernel 分别采用 AIC/AIV 指标并核对 SDK 与同步条件，见[指标边界](skills/ascendc-aprof-profiling/references/metrics.md)。
