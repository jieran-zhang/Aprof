# graph-base/1.3.0 / runtime 0.5.0（未封版）

本版完整包位于 `skill-libs/graph-base/1.3.0`，实验必须显式指定此路径及其任务内冻结副本。现有默认版本、1.2.0、旧 schema 和冻结快照保留；本次提交不代表封版、发布或硬件性能验收。

- 诊断知识 v0004：机制检索、证据比较、Problem 正文按需展开与精确回放；Action 实例通过 `aprof.handoff/v3` 请求 P/O。
- 规划知识 v0002、优化知识 v0004，路由配置 v0003；L2 组合门禁、输入驻留的作用域与生命周期分别判断。KEEP 必须有有效计划，unknown 不授权 C3。
- runtime 0.5.0 增加严格展开 contract 与观测算术检查；`knowledge.py`、`diagnosis.py`、`bindings.py` 保留旧身份。
- 中文知识与必要来源、修订、许可随完整包保存，使用不依赖上游仓库或下载目录。

现有 CPU 回归为 261 通过、1 跳过；7 个合成原始输入由 3 个独立 Agent 自主回放，3 个交接在合成合同内 ready、4 个 conditional。完整包独立目录检查通过，未生成实施 C3，未证明硬件收益。范围及遗留缺口见[逐例报告](skill-libs/graph-base/1.3.0/workflows/references/autonomous-diagnosis-1.3.0.md)与[检查记录](skill-libs/graph-base/1.3.0/workflows/references/autonomous-diagnosis-validation.json)。

本次提交前只校正活动文档中的版本称谓，并补上当前诊断校验示例；不改变计时、预算或正确性规则。结构检查使用：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B skill-libs/graph-base/1.3.0/tools/release.py --allow-unsealed
```

后续硬件批次使用独立任务副本，保留完整原始 20 cases、统一 5/20 与逐轮清 L2、原 oracle 和有效性门禁。批量 prompt 的编写或校验不启动硬件；本次拟运行的两轮优化不包含 memory recorder、知识提案晋升、边权或模型训练。优化结果与技能库维护分开，不在实验期间修改本包。
