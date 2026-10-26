# graph-base 1.3.2：技能开发审计外移

从 1.3.1 新建 [1.3.2 完整包](skill-libs/graph-base/1.3.2/README.md)，将 221 个技能开发材料移入 [scaffolding 归档](scaffolding/curation/graph-base-1.3.2-development/README.md)。原 1.3.1 和默认版本保留，本版未封版。runtime 为 0.8.3；D v0007、P v0004、O v0007、routing v0006、条件策略 v0002 及冻结 schema/快照保持原身份。

独立安装不需要 scaffolding。安装检查保留当前知识和全部运行时来源、许可、父版本链、路由快照、迁移目标与身份校验。历史种子和八项旧构建输入的原字节审计、四份诊断纸面 JSON 和两项 pending 提案的合同校验改由开发归档 `audit.py` 执行；两份迁移清单必须完整重组原基准，审计不允许通过空目录跳过案例或提案。

源码、原始来源、许可证、当前知识树的教学 examples、history/provenance、版本快照、迁移台账和 source-review.json 继续随包保存。诊断四份案例的五个教学 Markdown 保留，机器 JSON 与提案归档。包内导航统一指向[开发索引](skill-libs/graph-base/1.3.2/workflows/references/development-records.md#skills-1-3-2)。

冻结编译器原字节保存在 `_knowledge_v1.py`，新 `knowledge.py` 保留既有公共/私有 API，管理构建报告输出。默认构建不把 INITIALIZATION.md 重新写回技能目录；显式 `--report-dir` 可输出到包外的开发目录，并拒绝覆盖已有报告。原 1.3.1 编译器与现有快照的生成器 hash 不变，历史构建和路由仍按原格式回放。

完整开发测试需要本归档及 1.3.1 已归档的回归样例。独立目录演练阻断原仓库、开发归档和网络，再验证知识重建、安装检查与交接。验证仅使用 CPU，未启动硬件实验或发布版本。

最终包为 1,299 个文件（原 1,518），其中 skills 为 770（原 991）。runtime 全套 563 通过、1 个既有可选项跳过，开发审计测试 9 项通过，两组回归各 15 例/30 轮通过。详细统计、校验范围与限制见 [检查报告](scaffolding/curation/graph-base-1.3.2-development/CHECKS.md)。
