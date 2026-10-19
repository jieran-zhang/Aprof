# 批次执行与角色 contract

## 绑定与输入

batch 的严格结构见 [batch schema](../../../contracts/optimization-batch.schema.json)。每任务给 `task_id`、operator、group_id、split、source_ref、workload_ref、optimizer_id、budget_seconds、max_attempts。原始 workload 文件包含完整 case、oracle/精度、布局及特殊值要求；不得只留下计时代表集。

`group_id` 表示共享源码/语义近邻的防泄漏分组。同一算子、同一 baseline 派生的所有 case、candidate、重测和 seed 必须同组；不能给换名副本另分一个组。split 由冻结的 CANNBench 三个 manifest 核对，沿用其 active_operators；新外部算子先建立显式有版本的 split，不能临时塞进 test。历史已经暴露的 test 另标披露，不声称未见过。

`skill_lib_ref` 指向包的冻结文件清单：精确版本、每个源文件相对路径/hash、runtime/schema/工具、生成器和使用的 prompt。1.1.0 尚未 seal 时也必须冻结这些字节；commit ID 单独不足以代表脏工作区。`knowledge_refs` 保存三个编译产物，`override_refs` 保存实际加载的覆盖或 null。采集期间任一项改变，创建新批次，不改原 manifest。

`prompt_ref` 指向包含实际指令、模型/provider 版本、采样配置及各 task 的 run_id/可用 seed 的快照；不只写模型昵称。采样配置无法固定或 seed 不受支持时如实记 unknown，不宣称严格可重复。

冻结完整包使用现有包校验器的薄封装，不需要先 seal 开发版：

```bash
python3 scaffolding/tools/snapshot_skill_lib.py --skill-lib skill-libs/graph-base/1.2.0 --output /absolute/new-archive-root
```

工具调用所选包的 verify/verify_unsealed，复制它认定的文件集合并逐个核对原字节；不会执行 NPU 或发布版本。输出 `skill-lib/` 和最后写入的 `skill-lib.snapshot.json`，打印可填入 batch 的 skill_lib_ref。复制中断的目录不算完成，不能拿来续写新 manifest 掩盖变化。之后在同一归档根保存 prompt、split、batch 和任务；知识引用指向其中 skill-lib 下的真实编译产物。

缺少实际任务预算、模型配置或必要输入时，先交付 intake/缺项说明和离线计划。可以冻结已有源码字节供审阅，但不能把演练假设当成正式运行配置；用户补齐后另建正式 batch。尚未发生优化时，不把准备动作写成已经使用的优化会话或合规的优化成本。

## 批次启动检查

在交付任何 seed、启动单算子预算或分派 recorder 前，统一核对本批次全部 oracle 家族、dtype、特殊值、输出数量、native/清 L2 接口及实际 Python 依赖。使用所选包的 `single_role_task.py --preflight-only` 检查全部 case 配置；对于 BF16/MERE/MARE 等，使用支持该模式的冻结 runtime 的 `original_python_v1`，让冻结原程序参与 live 与离线判定。必要的 CPU 正/反例仅证明契约能力，不能冒充 NPU 正确性。

同时核对持久卷、native profiler 本地 scratch 和 oracle TMPDIR 各自的可用容量/配额。按实际输入、快照、全部输出/profile 与一次 oracle 副本估算峰值，不能只检查目录可写。oracle 临时副本可放任务私有持久卷；已关闭的本地证据经完整转存和 hash 校验后可释放本任务副本，并保留路径映射。不得清理其他任务，磁盘/配额错误单列 storage_unavailable，不算精度失败。

同一 runtime/adapter/环境缺项只形成一份批次级证据和成本记录；尚未派发的相关条目在索引中标 `not_started` 并引用它，不启动多个 optimizer/recorder 重复调查，也不伪造独立 memory。已启动任务仍按原规则关闭 task-result 和 memory。不依赖该缺项的任务可继续。再次尝试前核对包/adapter/环境的相关 hash 确已改变；单纯延长 C0 不构成修复。

能力检查通过后，先运行一个正式任务的完整原始 case 正确性、R0、一个有实际源码改动的候选及统一计时反馈，再扩展派发。此任务使用正常预算和候选计数，不另给免费试跑；真实结果和 memory 可直接进入批次。性能 verdict 为 rejected 仍可证明有效链路；inconclusive 保留真实反馈，但不能当作测量条件已就绪。共同噪声、设备状态或复用时限问题先处理，再按预声明规则复验后扩批；缺有效采集或尚未进入候选阶段不能证明就绪。不同精度契约仍需分别检查。新任务由所选 runtime 预声明 `bounded_outlier_v1`；少量异常的剔除、原始样本保留和稳定性判定只按包内统一计时规则执行。构建、完整正确性和存储准备在最终 A/B 计时前就绪，避免中间修复或归档拖过复用窗口。

在共享开发包中修复是独立维护工作；修后创建新输入锁/新批次。不能在已经冻结的任务内补丁 runtime、替换 workload 或覆盖旧失败。`oracle_adapter_unsupported`、`oracle_environment_unavailable`、`oracle_execution_failed`、`numerical_mismatch`、`oracle_timeout` 分别保存；基础设施缺项不作为优化动作的性能负例。

## 调用链

| 生产者 → 消费者 | 内容及落盘时机 |
| --- | --- |
| batch coordinator → 单任务 coordinator | batch_ref、task_id、workspace、预算、设备资源、固定 skill-lib；开始前写 C0 并核对 source/workload |
| diagnosis → planning | C1 中图版本、证据、排序、缺项和 action 快照，由 skill-lib 定义 |
| planning → optimization | C2 中模板路径/版本、比较、动作、参数与实现自由度 |
| optimization → profiling/coordinator | C3 中实际条目、源码 hash、参数调整、计划符合性；构建/完整正确性及 C4 计时证据 |
| 单任务 coordinator → recorder | 每次尝试的登记记录、C0–C5、冻结源码/patch、执行日志、完整证据索引；任务关闭时给 task-result |
| recorder → batch coordinator | memory_ref、校验结果、未归档文件/缺项、归档成本；不得替换优化结果 |
| batch coordinator → Teacher | 冻结批次、逐任务 memory 引用、全部任务状态与覆盖清单；训练和评估数据分目录交付 |

单任务 coordinator 在 C0 核对原 oracle 的 dtype、误差定义、特殊值和完整输出能否由选定 runtime 重放，以及 native 采集入口是否具备。缺能力时返回 blocked 和具体缺项，交 recorder 保留；不能通过删除 BF16 case、把 mean/max-relative 偷换成 allclose、放宽精度或调用旧计时 gate 来闭合任务。这是调用现有准备阶段的能力检查，不另写一套 oracle。

给优化 agent 的提示可以写为：

```text
任务绑定见 <batch_ref> 的 <task_id>。在 <workspace> 使用 <skill-lib>/skills/ascendc-aprof-coordinator/SKILL.md 完成优化。
新任务采用 soft_targets_local_v1：总任务/阶段/recorder 耗时均为软目标，超支只记录 warning 与 checkpoint，不能阻止 R1 或截断 collector；连续成本不重置。
结束写 task-result，保留失败和未完成项。不要整理训练 lesson 或修改所选知识区。
```

任务执行前创建 append-only 的 `attempts.jsonl`，每次登记保存 attempt_id、父 ID、意图文件 hash、时刻，闭合时追加结果引用；不能重写前一次失败。task-result 的 `attempts` 必须与登记集合一致，记录每项 C5 收尾文档、状态及最终 selected_attempt_id。没有候选的 blocked/cancelled 任务也写 task-result，说明阻塞阶段。

journal 每行仅含 `seq`（从 1 连续增长）、`event`（registered/closed）、`task_id`、`attempt_id`、`ref`。registered.ref 指向包含父 ID、意图和时刻的原始登记文件；closed.ref 指向本候选的 C5 收尾文件，必须与 task-result.terminal_ref 相同。已经登记但未执行完的候选也以 blocked/cancelled 收尾，保存缺项，不能从候选集合消失。

## 预算、恢复和收尾

预算覆盖准备、模型决策、构建、完整正确性、计时、按需 profile 与在线结果判定；归档另计。失败不返还已消耗预算。中断后用冻结 manifest 和最后闭合阶段恢复，不偷偷换版本、扩大预算或丢弃慢候选。

新任务采用 soft_targets_local_v1：总任务/阶段/recorder 耗时均为软目标，超支只记录 warning 与 checkpoint，不能阻止 R1 或截断 collector；连续成本不重置。

首个 seed 交付前，将 policy 复制到本批次归档并以外层 manifest 的 `budget_policy_ref` 绑定其相对路径/hash，不向严格 batch/Context/runtime schema 添加字段。生成和检查任务时统一使用该副本：

新任务采用 soft_targets_local_v1：总任务/阶段/recorder 耗时均为软目标，超支只记录 warning 与 checkpoint，不能阻止 R1 或截断 collector；连续成本不重置。
新任务采用 soft_targets_local_v1：总任务/阶段/recorder 耗时均为软目标，超支只记录 warning 与 checkpoint，不能阻止 R1 或截断 collector；连续成本不重置。
- `memory_separate_budget_seconds` → recorder 请求和原始软目标时刻，整理与真实 validator 共用这份独立预算；校验耗时另列，不重复加总。
新任务采用 soft_targets_local_v1：总任务/阶段/recorder 耗时均为软目标，超支只记录 warning 与 checkpoint，不能阻止 R1 或截断 collector；连续成本不重置。

先确认会话容量再交付 seed／recorder 请求。交付前等待计入批次准备；交付后的排队、模型和工具等待计入原连续预算，拒绝启动不产生新期限。历史执行脚本及旧 run 的预算/超限标记保持原样；未来执行副本须从 policy 取值，不能把历史 180/2700 常量带入新任务。已证实的 oracle/adapter 硬阻塞仍及时关闭，不耗尽新增额度。

recorder 可以报告证据丢失，但不能通过事后补测改写原状态。确需补采时建立新 observation/任务，保留原 failure、cost 和两者关系。优化终止不等于 memory 整理终止，batch coordinator 等 recorder 输出或明确 partial 后汇总。

批次索引逐任务列 task-result_ref、memory_ref、status、selected_attempt_id、optimization_seconds、memory_seconds、missing。所有任务都有记录；不只列最终成功算子。索引是导航视图，task-result 与 memory 才是有版本的记录。

运行数据、recorder 和 memory 全部留在 /dev/shm/aprof-<task-id>；不自动回写共享盘。默认 baseline 为 assumed，不执行完整正确性；候选真实完整检查一次，其后普通报告按全输出内容和身份复用可信结果。独立审计须明确开启并单独计费。
