---
name: ascendc-crash-debug
description: 利用保留的 AProf 执行证据，排查 Ascend C 超时、非法访问、AIC 异常和同步挂起。
---

# AProf 崩溃与挂起排查

保留首次失败的启动命令、device/key、超时、source/binary/tiling hash 和日志，停止该候选的性能采集。复现前检查 Host/Kernel 参数、逐核有效范围、尾块、workspace 和缓冲区复用。

挂起时梳理真实的生产、等待、消费依赖：EnQue/DeQue 配对、末次使用后的 FreeTensor、SetFlag/WaitFlag 顺序、barrier 参与者和跨核所有权。任意插入 sleep 不能修复缺失参与者或先等后产的问题。

仅在当前 SDK/目标支持时使用已安装的 `msSanitizer` 或 simulator，先看工具帮助。其计时标为诊断或代理证据。保留首次失败；修复作为新候选，重新构建并通过完整正确性后，按主工作流验证性能。
