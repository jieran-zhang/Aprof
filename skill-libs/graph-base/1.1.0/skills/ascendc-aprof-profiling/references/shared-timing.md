# 历史 Task v5 配对协议

本页仅说明历史兼容边界。1.1.0 新会话统一使用 [L2 清理 Task 计时](unified-timing.md)，不再将本协议用于反馈、收尾或缺少新 adapter 时的隐式回退。

`shared_buffer_msprof_task_window_v5` 曾在同一进程内让 A/B 共用 context 和 buffers，以基线 pilot 冻结约 10 ms 调用窗口，再使用六个新进程、每阶段五对及前后 A/A。正式样本共 30 对，旧门槛使用配对对数加速比的 bootstrap 下界。其缓存与提交条件不同，不能与新协议拼接样本或直接换用绝对时间。

历史实现保留在 `scripts/device_task_window_timing.py`、`assets/device_shared_timing.h`、`assets/device_task_profile.h` 和 runtime Task-window 回放模块中。v4/v5 回执按原版本与协议解释，不能重写旧判决或把历史失败改为通过。

旧共享 buffer 契约要求输入只读、输出每次完整写入，scratch 初始化与全部 kernel/依赖属于完整 callback；重叠 Task 总和不等于整体延迟。旧 oracle、原始 Task、源码/二进制身份及独立进程/控制记录仍需保留。

重现历史实验时选择对应历史包和原始请求，详细规则以冻结发布包及回执为准。这里保留历史实现不代表它仍是 1.1.0 当前正式入口。
