---
name: ascendc-runtime-debug
description: 根据准确命令、二进制身份、日志和 SDK/设备兼容性排查 AProf 候选运行失败。
---

# AProf 运行失败排查

保留退出码、stdout/stderr、首次运行错误、device/key、binary/source hash 及 SDK/runtime 版本。区分构建、加载、启动、同步和正确性失败；错误码含义以安装 SDK 的定义为准。

检查工具链与 runtime 目标、陈旧二进制路径、动态库搜索路径、启动签名、tiling ABI、workspace 分配和输出同步。环境问题用 `ascendc-env-check`；在同一目标以最小合法输入复现，保留原失败记录。

超时、非法访问、AIC 错误或死锁交给 `ascendc-crash-debug`。修复作为子候选，不能覆盖失败证据。不要把重置共享设备或结束他人任务当作通用恢复手段。
