# graph-base 1.3.1：开发材料外移

本版从 1.3.0 新建，将七组开发回归、评测和历史审阅材料移至 [scaffolding 开发归档](scaffolding/curation/graph-base-1.3.1-development/README.md)。技能库版本为 1.3.1，runtime 沿用 0.8.2；D v0007、P v0004、O v0007、routing v0006 和条件策略 v0002 保持原身份。原 1.3.0 与默认版本保留，本版未封版。

完整技能包位于 [skill-libs/graph-base/1.3.1](skill-libs/graph-base/1.3.1/README.md)。包内文档通过[开发材料索引](skill-libs/graph-base/1.3.1/workflows/references/development-records.md)说明归档位置，不依赖包外本地链接。运行时源码、知识正文与版本、knowledge-history、路由快照、条件策略、迁移档案、实际来源及许可证继续随包保存。

两个离线回归脚本迁入归档的 `tools/`，默认使用同仓库的 1.3.1；`--root` 可指定独立完整包，案例数据固定从归档读取。CLI 测试夹具改为从归档中的 `optimization-schemes-1.3.0/examples/` 读取。安装、知识构建、诊断和日常运行无需 scaffolding；完整开发测试需要仓库归档。

CPU 检查发现并同步修正两处继承的历史夹具：D4 合同测试显式读取冻结 v0001 路由及条件策略，不再混用活跃 D7 的新增 Action。运行时源码和冻结快照保持原字节。

归档的 D6 纸面链使用其原冻结 bundle 显式回放；公开 CLI 测试重新生成当前 D7 的完整 workload 映射，避免将旧样例作为新准入。另补齐 workload 反馈测试 helper 的计时版本参数。隔离安装测试的临时目录位于被禁读的原仓库之外。

迁移排除 `__pycache__`、`.pytest_cache`、`.pyc` 等生成缓存。归档导航按新位置更新，机器回归案例、来源、历史日志和冻结身份不改写为新实验。逐文件迁移前后 hash 和检查结果保存在 [relocation.json](scaffolding/curation/graph-base-1.3.1-development/relocation.json) 与 [检查报告](scaffolding/curation/graph-base-1.3.1-development/CHECKS.md)。

验证命令见归档 README；本轮只进行 CPU 和离线检查。

按磁盘文件递归统计，1.3.1 共 **1,518** 个文件，其中 workflows 为 **165** 个（含新增归档索引）。1.3.0 保持 **3,941** 个文件；排除其 93 个缓存后，可比基数为 3,848 个。七组归档材料共 2,329 个文件，另有两个回放脚本；未复制其中 3 个生成缓存。
