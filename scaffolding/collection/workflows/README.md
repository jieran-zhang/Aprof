# Trace 采集 workflow

> 历史采集入口。1.1.0 新批次使用 [新脚手架](../../README.md) 的两个高层 skill；
> 本页及其下游保留旧运行的实验、计时与恢复语义，不作为新统一计时和 memory v3 的定义。

此处负责实验组织，不重新定义 skill 的优化算法流程。

1. 显式选择已冻结的 skill release，声明算子、split、预算与测量策略。
2. 冻结 baseline、workload、skill/runtime/graph 身份及独立的 collector producer。
3. 使用选定 skill 的诊断、规划和候选能力；由采集执行器运行协议规定的验证和测量。
4. 优化阶段使用任务本地临时文件，完成完整正确性、Task CSV 解析、A/A 控制和在线准入；
   这些工作仍计入优化预算。返回代码、小报告与本地证据索引，保留失败和 partial。
5. 任务结束后由 trace/training collector 按需复制、CAS 登记、归档、独立审计并生成
   memory/lesson；归档成本单独报告。没有兼容 gate 时保持未准入，后采集不能改写
   原失败、超时或原预算结果。

1.0.0 的离线 Teacher→Wiki→skill 筛选与硬件发布门禁见
[训练路线](../../docs/training_roadmap.md)和[审计清单](../../curation/README.md)。
`shared_buffer_msprof_task_window_v4` / `local_profile_only` 已完成 exp、sigmoid
全量资格确认与独立安装回放，0.5.1 已封存并成为默认版本。
优化 skill 不承担完整 profile 永久复制或 CAS 归档；
`policy train` 的 EpisodeStore 准入规则不变，未归档的小报告不能直接成为训练数据。

当前流程入口：

- [实验组织](optimization_experiment_playbook.md)
- [Level2 轻量搜索](level2_search_lite.md)与[搜索/最终测量边界](search-measurement.md)
- [Level2 完整测量](level2_msprof_protocol_v2.md)
- [memory/lesson v2](optimization_trace_collection_v2.md)
- [精简证据](../../evidence/README.md)

从仓库根目录设置 `APROF_SKILL_LIB` 为具体版本路径。新 campaign 使用：

```bash
python3 scaffolding/collection/scripts/level2_campaign.py prepare \
  --skill-lib "$APROF_SKILL_LIB" --run <new-run-directory>
```

此命令只准备源码和 CPU 输入。设备预检、基线测量、候选及最终测量仍是独立
操作。创建时写入 `skill-lib.json`，后续 CLI 使用该绑定；显式选择另一版本会失败。
运行时 imports 和工具路径来自该版本，不读取 catalog 的默认指针。

配置中的算子、采集器与 producer 路径相对仓库根；pilot 的 graph 路径相对
选定 release。通用 runtime contract 在 release 内，采集专用 contract 在
`../contracts/`。

旧运行没有新 release 绑定，且冻结了原 producer 的绝对路径。旧记录保持原字节；
使用原 checkout 回放，后续迁移执行必须建立显式 continuation/handoff epoch。
不得给一个已经存在的历史运行补写新 release 绑定后直接续跑。
