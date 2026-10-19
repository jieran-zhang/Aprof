# 新脚手架共享契约

此目录负责 batch、task-result、memory v3 和离线知识修订提案。1.1.0 的 C0–C5 与 C1/C2/C3 JSON handoff 仍由选定 skill-lib 管理；旧 collection/contracts/v2 保留原语义。

| Schema | 生产者 → 消费者 |
| --- | --- |
| [optimization-batch](optimization-batch.schema.json) | 批量编排 → 单算子 coordinator、recorder、Teacher |
| [task-result](task-result.schema.json) | 单算子 coordinator → recorder；全部候选集合及最终选择的事实来源 |
| [optimization-memory](optimization-memory.schema.json) | 独立 recorder → Teacher；全部尝试、版本、契约、证据与观察 |
| [knowledge-update](knowledge-update.schema.json) | Teacher → evaluator/审阅者；逐项更新、训练来源、候选与评估引用 |

每条新 artifact ref 为 `{path, sha256}`。path 相对显式 archive-root，不允许越界、绝对路径或 symlink；hash 为 `sha256:` 加 64 位十六进制，作用于原文件字节。跨包共用材料先复制或登记为归档根下的内容对象，不能让可变工作目录成为唯一依据。所有记录的 ref 共用同一个 root，不相对 JSON 所在子目录。

新包快照使用 `aprof.skill-lib-snapshot/v1`：release_id、runtime_version、source_status、source_path（仅 provenance）、files（归档根相对路径→文件 hash）及 publication_performed=false。由 [snapshot_skill_lib.py](../tools/snapshot_skill_lib.py) 调用原包校验器生成；batch 校验会核对 files 的每一个字节摘要。旧来源包的原始 manifest 可以保留，但不能把单个 commit ID 或不完整文件清单说成完整冻结。

缺失阶段用 null 与 missing 表达；已有但 hash 错的文件是损坏，不能降格为未知后通过。memory 修订保留 memory_id，revision 加一，previous_ref 指向上一版，batch/task 不变。task-result 不由 recorder 重写。

校验器使用标准 JSON Schema（jsonschema 依赖显式声明），拒绝重复 JSON key、NaN/Infinity 和额外字段。它只做可重复的记录完整性、角色、split、候选覆盖、父本及阶段关联检查。完整 runtime 回放、来源语义、优化预算和训练 gate 是相应 skill 的职责；`integrity_valid=true` 永远不等于晋升。

```bash
python3 scaffolding/tools/validate_learning_records.py --root <archive-root> --kind batch --input batch.json
python3 scaffolding/tools/validate_learning_records.py --root <archive-root> --kind memory --input tasks/exp/memory/0001.json
python3 scaffolding/tools/validate_learning_records.py --root <archive-root> --kind update --input teacher/proposal.json
```

校验器不导入全局默认 runtime。阶段深度校验使用该任务冻结包的 `contract validate`、`knowledge link-result`、`timing verify`；正文/结构候选使用该包的 `knowledge build/validate/route`，不改旧 policy 或 episode。
