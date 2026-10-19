---
name: ascendc-env-check
description: 在 AProf 构建或测量前检查本地 CANN 工具链、设备可见性、采集工具和目标身份。
---

# AProf 环境预检

记录 device、原始 SoC 名、CANN/编译器版本、构建目标和准确命令。检查 `ASCEND_HOME_PATH`、`command -v bisheng`、`command -v npu-compute`、`command -v msprof`、`command -v cannsim` 和 `npu-smi info`。缺失工具只表示能力缺失，不能据此推断型号；预检不安装工具、不重置设备。

用本地 `npu-arch` 建立架构档案。交叉编译或模拟环境须区分配置目标与执行设备；INI 只能证明 SDK 配置。启动前核对编译目标、实际二进制与 runtime SoC。

采集前要求隔离候选已构建、完整正确性已通过；复用同源有效记录，不在每个采集视图重复执行。用阶段记录保存 stdout/stderr、退出码、超时和 hash。沿用已有执行授权，dry-run 仅用于检查。

机制采集按架构路由：已核实的 npu-compute 支持范围是 950/dav-3510，910C/A3 用 msprof。实际能力以可执行文件和匹配 CANN 版本为准；不在预检中升级系统 CANN/driver。性能计时统一遵循 [主工作流](../ascendc-aprof-coordinator/SKILL.md)。
