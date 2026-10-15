# Task Duration 采集接口（待资格验证）

本文件约束实现接口，不是硬件准入或发布回执。协议为
`shared_buffer_msprof_task_v1`，主指标为
`msprof.op_summary.Task_Duration`。既有 v2 原生 header/wire 保留原名；
不得把历史 Event 样本重新标为 Task Duration。

## 固定采集

- 每 case 六个新进程、共享 context/stream/input/output/workspace；每周期依次
  `aa_before / formal / aa_after`，各五对，沿用原 AB/BA 顺序。
- 固定 repeat=100、每侧 warmup=10、每阶段四组 prime=100；无 pilot。
  单 kernel 周期共 4222 个任务，正式样本为 30 对/case。
- 每个角色样本对 100 次完整调用的全部登记任务时长求和，再除以 100。
  预热、prime、最终两次快照单独核对；全部原 CSV 保留。
- 只采 `--task-time=l1 --ai-core=off --ascendcl=off --runtime-api=off
  --ge-api=off --aicpu=off --type=text`。PMU 机制证据另采。
- 一个周期一次 msprof direct application；命令文件驱动 19 个原生命令。
  只接受唯一完整 op_summary；若没有表且仅有一个 PROF 目录，允许一次预定 export。
  失败停止，无重新采样、续跑、改变 flags 或删点。
- 每周期退出后验证两份完整输出。持久 oracle 仅复用 import，逐输出验证不减少。
  所有写盘、解析与 oracle 在该周期采样结束后执行。
- CV 5%、A/A 角色偏差及跨阶段漂移 2%、收益下界 1.03、逐 case 回退 3%
  和正确性合同保持不变。baseline-only 不要求收益。
- Event、任务首末跨度、间隙与 Host wall 独立报告，不加入 Task Duration 平均。
  kernel 加速不自动解释为端到端调用加速。

## 可复用工具的接口

`device_task_timing.py` 配置沿用 `device_shared_timing.py` 的 12 个字段，新增：

```json
{"task_profile": {"profiler": "/absolute/path/to/msprof",
                  "role_kernel_names": {"baseline": ["exp_kernel"],
                                        "candidate": ["exp_kernel"]}}}
```

名称序列在采集前冻结，长度必须等于对应 `launches_per_operator`。首轮资格验证
只覆盖 exp/sigmoid 的完整单 kernel 调用。串行多 kernel 必须登记完整序列；
未知任务、重复任务、重叠或缺失任务不能静默忽略，也不能只取最大耗时任务。
存在并行重叠的算子须另行定义完整设备范围与完成跨度后才能准入。

registration 保存 `protocol, created_at, config_ref, identity, inventory,
producer_files, attempt_policy, cycles, pairs_per_phase, warmup, prime_repeat,
repeat, cpu_affinity, hardware_ref, verifier_request_plan_ref, profiler_ref,
task_profile`。固定值分别为 `exactly_once_no_resume_no_resampling, 6, 5, 10,
100, 100`；没有 calibration 字段。

raw 保存 `protocol, registration_ref, verifier_worker_ref, started_at,
finished_at, complete, sessions, host, environment`；失败追加 error 并保留已尝试周期。

session 保存 `case_id, cycle, mode, cycle_dir, started_at, finished_at,
identity_before, identity_after, capture, export, commands_ref, task_table_ref,
native_messages_ref, partition_ref, capture_files_ref, profile_files_ref,
output_hashes, verifications, control_summary`。
`mode=confirmation`；export 未发生时为 null。capture/export 是带真实 argv、cwd、
起止时间、退出码、日志 CAS、环境覆盖和超时预算的执行回执。原生 PID 来自原 stdout，
与 msprof 外层 PID 分开。不得构造交互请求/应答回执。
`capture_files_ref` 与 `profile_files_ref` 分别绑定 capture 完成时、可能的 export
完成后 profile 目录内全部 regular files 的相对路径与 CAS；未 export 时两者相同。

admission receipt 沿用原身份字段与 config/registration/raw/report 四个 CAS 引用，
但必须标明新协议。独立回放从原 stdout 与完整 CSV 重算 partition、控制和报告，
核对源码、二进制、工具、输入、任务序列、命令文件、环境、执行顺序和全部 oracle。
解析器摘要中的 passed/stable 不能代替这些检查。

## 历史和发布

既有 v2 实验、失败样本及部分通过的 sigmoid 结果按原指标保存。
历史 producer 只能按“原路径 + 旧哈希”解析归档；原始数据不可替换。
历史完整回放须显式返回不可发布，不能用于新 Task 协议的准入。

新接口完成负测、独立控制和全量方法资格验证后，才允许封存 0.5.1。
当前默认仍为 0.5.0。
