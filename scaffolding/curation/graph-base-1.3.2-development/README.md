# graph-base 1.3.2 技能开发归档

本目录承接从 1.3.1 技能目录迁出的 221 个文件。原 1.3.1 保留，新技能包位于 [1.3.2](../../../skill-libs/graph-base/1.3.2/README.md)，runtime 为 0.8.3。冻结知识、快照和编译器身份保持原义，不改变计时、正确性或 Action/P/O 准入。

| 开发材料 | 文件数 | 入口 |
| --- | ---: | --- |
| v0003 种子 | 197 | [身份清单](materials/skills/ascendc-aprof-diagnosis/graph/history/seed-v0003/files.json) |
| 旧构建输入及元数据 | 8 | [迁移分区](migration-files.json) |
| 四份诊断纸面 JSON | 4 | [教学说明](../../../skill-libs/graph-base/1.3.2/skills/ascendc-aprof-diagnosis/examples/README.md) |
| pending 提案 | 3 | [说明](materials/skills/ascendc-aprof-diagnosis/proposals/README.md) |
| 诊断审阅及检查报告 | 3 | [检查记录](materials/skills/ascendc-aprof-diagnosis/knowledge-validation.json) |
| 三棵知识区初始化报告 | 3 | [诊断](materials/skills/ascendc-aprof-diagnosis/graph/INITIALIZATION.md)、[规划](materials/skills/ascendc-aprof-parallel-planning/knowledge/INITIALIZATION.md)、[优化](materials/skills/ascendc-aprof-optimization/knowledge/INITIALIZATION.md) |
| 历史计时说明 | 3 | [A/A](materials/skills/ascendc-aprof-profiling/references/history/aa-controls.md)、[范围](materials/skills/ascendc-aprof-profiling/references/history/measurement-scope.md)、[父本](materials/skills/ascendc-aprof-profiling/references/history/parent-baseline.md) |

`materials/` 保留原包内路径。机器记录、种子和旧构建输入保持原字节，六份 Markdown 只修正导航。逐文件原始及当前 hash 见 [relocation.json](relocation.json)。历史报告中的版本、路径与结论仍代表原实验；当前导航及审计通过该清单解析其位置。

安装检查继续验证所有保留的知识、raw 来源/许可、历史 provenance、版本快照、路由、迁移节点及字节一致性。开发审计补充验证全部 221 个归档、196 个种子文件与 195 个旧节点的对应、四个案例及两个提案的合同；安装和开发迁移清单须完整重组 [原始迁移清单](migration-baseline.json)，不能静默遗漏八项历史输入。

从仓库根目录运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B skill-libs/graph-base/1.3.2/tools/release.py --allow-unsealed
PYTHONDONTWRITEBYTECODE=1 python3 -B scaffolding/curation/graph-base-1.3.2-development/audit.py
PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest scaffolding/curation/graph-base-1.3.2-development/tests -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 APROF_SKILL_LIB="$PWD/skill-libs/graph-base/1.3.2" python3 -B -m pytest -c skill-libs/graph-base/1.3.2/runtime/pyproject.toml skill-libs/graph-base/1.3.2/runtime/tests -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 python3 -B scaffolding/curation/graph-base-1.3.1-development/tools/replay_source_regression.py --root "$PWD/skill-libs/graph-base/1.3.2"
PYTHONDONTWRITEBYTECODE=1 python3 -B scaffolding/curation/graph-base-1.3.1-development/tools/replay_selection_regression.py --root "$PWD/skill-libs/graph-base/1.3.2"
```

知识构建默认不留下 INITIALIZATION.md。如需新的开发报告，显式指定包外目录（不能覆盖已有报告）：

```bash
PYTHONDONTWRITEBYTECODE=1 skill-libs/graph-base/1.3.2/tools/aprofctl knowledge build --root "$PWD/skill-libs/graph-base/1.3.2" --owner parallel-planning --report-dir "$PWD/scaffolding/curation/graph-base-1.3.2-development/generated/planning"
```

新的报告属于构建产物，不覆盖本次迁入的初始化记录。源编译器保存在 `_knowledge_v1.py`，新 `knowledge.py` 只管理报告输出和兼容 API；这样不会改变已有知识快照的编译器 hash。

检查结果及完整文件统计见 [CHECKS.md](CHECKS.md)，机器结果见 [CHECKS.json](CHECKS.json)。1.3.2 共 1,299 个文件，skills 为 770 个，本开发归档共 230 个文件。
