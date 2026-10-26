# 1.3.1 开发材料归档索引

以下材料用于开发验收、离线回归和历史审计，不参与日常工作流加载。材料位于同一仓库的 `scaffolding/curation/graph-base-1.3.1-development/`，不包含在独立技能包中。包内仍保留全部运行时来源、许可证、路由/条件快照、历史知识正文和迁移依赖。

仓库归档的 `README.md` 提供报告链接、回归命令和检查结果；`relocation.json` 保存原路径及迁移前后文件 hash。原 1.3.0 保留，历史报告中的版本、命令和验收范围不改写为 1.3.1 的新结果。

## source-regression-15

开发材料路径：`scaffolding/curation/graph-base-1.3.1-development/source-regression-15/`。

## selection-regression-15

开发材料路径：`scaffolding/curation/graph-base-1.3.1-development/selection-regression-15/`。

## code-understanding-1.3.0

开发材料路径：`scaffolding/curation/graph-base-1.3.1-development/code-understanding-1.3.0/`。

## optimization-schemes-1.3.0

开发材料路径：`scaffolding/curation/graph-base-1.3.1-development/optimization-schemes-1.3.0/`。

## execution-cost-1.3.0

开发材料路径：`scaffolding/curation/graph-base-1.3.1-development/execution-cost-1.3.0/`。

## selection-reassessment-1.3.0

开发材料路径：`scaffolding/curation/graph-base-1.3.1-development/selection-reassessment-1.3.0/`。

## median-timing-1.3.0

开发材料路径：`scaffolding/curation/graph-base-1.3.1-development/median-timing-1.3.0/`。


<a id="skills-1-3-2"></a>
## 1.3.2 技能开发材料

221 个文件已归档到仓库 `scaffolding/curation/graph-base-1.3.2-development/materials/`，其中保留原来的包内相对路径。包含 197 个旧种子、8 个旧构建输入及元数据、4 个纸面 JSON、3 个 pending 提案、3 个审阅报告、3 个初始化报告和 3 个历史计时说明。原知识正文、sources、许可、历史 provenance 和版本快照仍随包保存。

开发归档的 README 提供完整导航，`audit.py --root <1.3.2完整包>` 验证迁移分区、全部归档材料、195 个旧节点、四份纸面案例和两项提案。安装器和 release.py 只检查技能包及其保留的全部运行时来源，不需要开发归档。完整开发测试需要仓库中的归档。

当前 `knowledge build` 默认不在技能目录生成 INITIALIZATION.md；如需开发报告，显式传入 `--report-dir /absolute/external/report-directory`，建议使用 scaffolding 开发归档下的 `generated/`。冻结编译器保留在 runtime 的 `_knowledge_v1.py`，其字节与旧编译身份一致；外层入口只管理报告输出。
