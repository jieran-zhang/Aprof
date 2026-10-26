# graph-base 1.3.1 开发材料归档

从 1.3.0 复制新建 1.3.1 时，将七组开发材料和两个离线回放脚本迁入本目录。原 1.3.0 保留；回归数据、回答、原始来源及历史验收结论保持原身份，导航链接按新位置修正。迁移前后文件身份见 [relocation.json](relocation.json)。

日常入口位于 [1.3.1 技能包](../../../skill-libs/graph-base/1.3.1/README.md)，不依赖本归档。CLI 回归测试使用这里的纸面交接夹具；开发者运行完整测试时需要仓库及本目录。

本次检查结果和最终文件统计见 [CHECKS.md](CHECKS.md)，机器结果见 [CHECKS.json](CHECKS.json)。

| 材料 | 入口 |
| --- | --- |
| 源码回归 15 例 | [报告](source-regression-15/README.md) |
| 选择回归 15 例及修正前快照 | [报告](selection-regression-15/README.md) |
| 代码理解评测 | [报告](code-understanding-1.3.0/README.md) |
| 完整优化方案验收 | [报告](optimization-schemes-1.3.0/REPORT.md) |
| 执行事实与完整代价验收 | [报告](execution-cost-1.3.0/REPORT.md) |
| 选择与复盘维护 | [报告](selection-reassessment-1.3.0/README.md) |
| 中位数计时离线比较 | [报告](median-timing-1.3.0/REPORT.md) |

从仓库根目录执行，均只做 CPU/offline 检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B skill-libs/graph-base/1.3.1/tools/release.py --allow-unsealed
PYTHONDONTWRITEBYTECODE=1 python3 -B scaffolding/curation/graph-base-1.3.1-development/tools/replay_source_regression.py
PYTHONDONTWRITEBYTECODE=1 python3 -B scaffolding/curation/graph-base-1.3.1-development/tools/replay_selection_regression.py
PYTHONDONTWRITEBYTECODE=1 APROF_SKILL_LIB="$PWD/skill-libs/graph-base/1.3.1" python3 -B -m pytest -c skill-libs/graph-base/1.3.1/runtime/pyproject.toml skill-libs/graph-base/1.3.1/runtime/tests -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest scaffolding/curation/graph-base-1.3.1-development/tests -q -p no:cacheprovider
```

两个回放脚本默认核验同仓库的 1.3.1，可用 `--root /absolute/package` 显式指定另一份兼容的完整技能包；材料总是从本归档读取。历史报告中的原命令是当时的运行记录，当前入口以上述命令为准。

来源原文、日志及冻结实验记录中的历史路径保留为来源身份；导航修正不表示重做历史实验。运行时的 knowledge-history、路由快照、条件策略、来源/许可和迁移档案继续随包保存。
