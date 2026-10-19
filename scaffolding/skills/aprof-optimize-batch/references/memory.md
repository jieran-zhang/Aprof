# Memory v3：保存什么以及怎样关联

一个 memory 描述一个固定任务及其全部尝试。Schema 为 `aprof.optimization-memory/v3`，与旧 `schema_version=2.0.0` 分开。严格字段见 [memory schema](../../../contracts/optimization-memory.schema.json)。

## 建议目录

```text
<archive-root>/
  batch.json                         固定任务、split、预算与版本
  snapshots/                         skill-lib 文件清单、图/树、override、split 原文
  tasks/<task_id>/
    C0.md
    attempts.jsonl                   执行前登记，闭合时追加
    task-result.json                 coordinator 的全部候选清单及最终选择
    attempts/<attempt_id>/
      C1.json C2.json C3.json         1.1.0 的原始 handoff；没发生则缺省并记原因
      C4.md C5.md
      source/ patch/ build/ correctness/ timing/ profile/
      knowledge-outcome.json         有完整链和真实计时才生成
    memory/0001.json                 recorder 的第一版
    memory/0002.json                 修正时 previous_ref 指向上一版
  evidence-map.json                  原始路径到归档对象的显式映射
  index.json                         所有任务的导航与缺项
```

真实运行目录留在 Git 外。内容可以用既有 CAS 去重；每个新 ref 都是 `{path, sha256}`，path 相对 archive-root，sha256 绑定**文件原字节**。runtime 的 canonical content hash 与文件 hash 含义不同，不能互换。模型说明、图 MD、raw Task CSV、构建和 oracle 报告都按字节保存；大型原件若只留外部位置，该位置及校验状态必须可追溯，缺原件就标缺，不能宣称完整闭包。

batch.source_hash、attempt.parent_source_hash/candidate_source_hash 是 APROF 冻结源码的身份，分别关联 C0、C3 与计时请求。source_ref 指向保存该源码的 manifest/archive 文件，其文件 hash 与源码身份可以不同；两者必须都保存，不拿压缩包字节 hash 代替 implementation_source_hash。

## 最小信息

| 内容 | 保存位置与作用 |
| --- | --- |
| 任务/版本/数据边界 | batch_ref、task_id、C0_ref；含 baseline、全部 workload、架构/toolchain、预算、模型、split、三个知识区及实际 override |
| 完整候选集合 | task_result_ref + journal_ref，不能只留下 winner |
| 源码谱系 | parent_attempt_id、parent_source_ref、candidate_source_ref、patch_ref；父本不等于原始 baseline |
| 诊断推荐 | C1 原文：symptom 证据、机制排序、反证/缺项、action 排序和必要内容快照 |
| 规划选择 | C2 原文：知识路径、模板、备选比较、selected_actions、所有权/同步、实例参数 |
| 实际执行 | C3 原文：executed_actions、recipe/example、真实源码 hash、计划符合性、实际参数调整 |
| 结果与原件 | C4_ref、C5_ref、execution_refs、timing_ref、outcome_ref；包括失败日志及 profile 的代理标记 |
| 条件性观察 | observations：所属 owner/target_id、命题、证据类型、支持/反驳/未知、出处与限制 |
| 成本与缺项 | 每尝试优化秒数/token、首个失败、missing；任务结果与归档成本分别计 |

C1–C3 是 skill-lib 的唯一阶段结构来源；memory 用引用封装，不再复制一套字段来制造不同的事实版本。C4/C5 保留原阶段文档。执行未走到的阶段允许 null，并在 missing 写明；失败尝试可以成为实现调试材料，不能冒充完整性能记录。

任务级 status 与 stop_reason 以 task_result_ref 为唯一事实来源，memory 不复制一份可漂移的状态。C0 就阻塞的任务允许 attempts=[]，journal 为空，仍保存任务结果和 memory；recorder 在 limitations 写归档缺项及其影响。不同 agent ID 只是声明；没有实际优化会话的离线准备也必须写明，不能伪称完成了角色隔离的实测优化。

完整尝试用选定包生成关联记录：

```bash
<skill-lib>/tools/aprofctl knowledge link-result --help
<skill-lib>/tools/aprofctl timing verify --result <unified-timing-result.json>
```

`link-result` 关联推荐/选择/执行及源码；`timing verify` 才从原始计时证据重放工程判定。不能用关联成功替代完整重放。结果继续为 `performance_engineering_only`，不变成旧 `production_safe_gain` 或旧 policy episode。

## 整理与更正

1. 先冻结原始阶段文件，再写新 memory。每版 immutable，修正解释或补档生成新 revision 与 previous_ref；不更改原候选状态。
2. `observations` 允许 retrospective，但需显式标记 basis_kind，事实和推测分开。claim_id 在任务内唯一，来源可定位到文件中的 case、CSV 行或源码位置（statement/limitation 记录定位说明）。
3. 一个训练支持单位是独立 task/operator group；一个任务中的 20 个 case、20 次计时轮次、同源重测、多个文档、多个 memory revision 都不增加独立支持数。
4. 一个 candidate 同时做融合、分块和流水调整时，结果先归整个候选。只有独立消融或同条件单一变换比较，才支持单条 action/recipe 的性能排序。
5. `validate_learning_records.py` 校验严格结构、引用字节、批次 split、角色、候选覆盖、父子与阶段身份；不证明候选登记没有被人为隐瞒，不重放硬件、不判定命题真实。Teacher 另核对原始 journal、runtime 回放和证据闭包。

运行数据、recorder 和 memory 全部留在 /dev/shm/aprof-<task-id>；不自动回写共享盘。默认 baseline 为 assumed，不执行完整正确性；候选真实完整检查一次，其后普通报告按全输出内容和身份复用可信结果。独立审计须明确开启并单独计费。
