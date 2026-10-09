# Trace 采集 workflow

此处负责实验组织，不重新定义 skill 的优化算法流程。

1. 显式选择已冻结的 skill release，声明算子、split、预算与测量策略。
2. 冻结 baseline、workload、skill/runtime/graph 身份及独立的 collector producer。
3. 使用选定 skill 的诊断、规划和候选能力；由采集执行器运行协议规定的验证和测量。
4. 保存每次尝试、失败、父本、反馈和原始证据；没有兼容 gate 时保持未正式准入。
5. 完成测量后生成研究 memory/lesson、归档和索引；经验证的知识进入下一版 skill。

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
