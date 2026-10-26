# 来源与兼容范围

本技能由 CANNBot npu-compute 算子指导在 AProf 本地提炼，运行时不加载上游 skill。

- 来源：[cann/cannbot-skills tool-npu-compute](https://gitcode.com/cann/cannbot-skills/tree/1fd7ec9770ecde574be5888c992997ffff910e71/tools/tool-npu-compute)。
- 固定版本：`1fd7ec9770ecde574be5888c992997ffff910e71`；本地检查日期 2026-10-10。
- 提炼范围：采集/CLI、指标基础、summary、数据可用性、硬件身份与 Pipeline 解释。
- 原样保留：`cli_support.py`、`scripts/inspect_pipe_trace.py`、`assets/pipe-trace-catalog.json`。
- Copyright (c) 2026 Huawei Technologies Co., Ltd. 分发条款与版权声明见 [LICENSE](LICENSE)。

硬件支持依据 asc-tools `8b15e97b18375f12e90884eee052d09ca36dcac7` 的 [官方 npu-compute 文档](https://gitcode.com/cann/asc-tools/blob/8b15e97b18375f12e90884eee052d09ca36dcac7/docs/zh/06_npu_compute.md) 核对。文档范围是 Ascend 950 / dav-3510、Ascend C kernel、单次算子调用，不证明 910C/A3 支持。执行前查询安装版本能力，不把 master 描述泛化到其他工具链。

上游实采 fixture 来自 Ascend950PR_9599 / 3510；离线 fixture 验证只证明解析兼容，不代表当前 A3 机器执行过 950 采集。AProf 的 A3 路由保持 msprof，不修改系统 CANN/driver；真实机器结果以发布验证报告为准。
