# graph-base/1.2.0 / runtime 0.3.0（未封版）

新任务入口为 `skill-libs/graph-base/1.2.0/workflows/aprof-performance-workflow.md`，执行策略 `soft_targets_local_v1`。1.1.0 与原历史协议不变；当前推送分支 `maintenance/soft-targets-20261019-push` 继承原仓库 `c8d1609`，纳入 1.2.0 及其所需 batch/memory 契约、校验器和脚手架；未带入原工作树中其他 1.1.0 修改。旧的完整工作区快照保留在本地 `maintenance/soft-targets-20261019` 分支，仅用于追溯，不应使用 `git push --all` 推送。不要将本版冒充 stability-v4 输入锁。

- task_budget_v2、runner、oracle、collector、report 使用软目标，记录超支并继续。v1 仅保留历史回放语义。真实退出错误与用户取消仍生效。
- baseline 默认 assumed，绑定源码/二进制身份，无数值检查；候选必须完整验证。实际全部输出内容一致才复用带任务认证的验证记录。独立审计显式 `APROF_ORACLE_AUDIT=1`。
- workspace、临时数据、快照/归档和报告在 `/dev/shm/aprof-<task-id>`，不自动回写共享盘。目录仍在时可恢复；易失存储不保证重启后恢复。
- `single_role_task.collect_pair` 两侧准备完毕后连续执行所有 native，再串行导出；`finish_case` 从 pending 恢复。共享设备探针会话保留动态查询，native 核对物理设备。
- 20 cases、5/20、逐轮清 L2、Task Duration、bounded_outlier_v1、A/B 间隔和有效期均不变。

下一批使用 `scaffolding/prompts/vector-acceptance-1.2.0.machine-{a,b}.prompt.txt` 和同目录新输入锁；先运行：

```bash
python scaffolding/tools/verify_input_lock.py --repo "$PWD" --lock scaffolding/prompts/vector-acceptance-1.2.0.inputs.json
python skill-libs/graph-base/1.2.0/tools/release.py --allow-unsealed
```

`scaffolding/tools/task_controller.py` 复用 runtime 启动/终态机制，依赖失败不会阻止独立后续工作。`hap_report.py` 明确区分 assumed 条件评分与已验证正确性。`cost_breakdown.py` 只读回执，用时间区间并集防止重复累加父子成本，不执行数值回放。`compare_profile_exports.py` 对本地冷原始 trace 做旧/新顺序交替对照，不能将历史共享盘时间当成受控收益。

测试使用 `/dev/shm` 下 basetemp 和 TMPDIR。实际设备验证及测试日志默认留本地任务目录，未纳入此源码交付。本版未 seal、未发布、未训练知识、未修改全局技能或系统 CANN/驱动。历史采集脚本仅供旧协议解释；系统内部 watchdog 和可选 simulator 期限不由本 runtime 控制。
