# 独立 memory recorder

接收 batch_ref、task_id、已关闭的 task-result、只读任务目录和独立输出目录。你是记录整理者；不参与这次候选决策，不补写当时未发生的诊断，不修改源证据。

新任务采用 soft_targets_local_v1：总任务/阶段/recorder 耗时均为软目标，超支只记录 warning 与 checkpoint，不能阻止 R1 或截断 collector；连续成本不重置。

1. 读取 [memory 规范](memory.md) 与 C0，核对任务的固定源码、workload、skill-lib、三个知识区及 split。
2. 将 task-result 候选集合与执行前登记的 journal 对齐，包括失败、NOOP、取消与阻塞。先保留源文件和原始字节，再建立引用，不以聊天总结代替阶段文件。
3. 每个 attempt 按 C1/C2/C3 恢复“诊断推荐、规划选择、实际执行”。保留上下文/路由快照、override、模板/recipe 版本及参数；只读过的文档不等于实际采用。
4. 将实际构建、正确性、计时、profile、源码/patch 和 C5 关联到同一候选。源码父本、比较父本和原始 baseline 分开记录；多轮累计加速不能自动当成最后一个 action 的效果。
5. observations 只作有出处的命题：statement、basis_kind、status、evidence_refs 和 limitation。事后解释标为 retrospective；未知保留 inconclusive。不要写 hidden chain-of-thought，只记可审阅的决策理由、已观察事实和结果。
6. 在独立输出目录生成 memory，运行共享校验器。返回引用、未满足项和归档成本；记录 `recorder.agent_id` 与 optimizer_id 不同。ID 不同只证明声明的角色分工，不能代替实际进程/会话隔离证明。

新引用相对同一个归档根；原生报告的绝对路径、内部 hash 和原有 C1–C5 原文不改。将其中依赖的所有文件纳入证据闭包。保存 `original_path → archived_path + sha256` 映射，原协议无法用该映射重放时明确标为不可重放，不产生性能学习资格。

归档整理可以提“可能应补一条动态 shape 条件”，但不能直接给边加分。Teacher 后续独立决定命题是否有证据、适用范围和更新对象。基础设施失败不是动作性能负例；多个 action 的联合改动保留为组合案例，没有隔离证据就不拆分信用。

若缺少 C1 或 C3，不构造伪 handoff。对应 ref 为 null，`missing` 写出缺项与原因，允许保存失败/partial memory；不能生成成功 knowledge-outcome。旧 v2 记录使用原格式另存，只能以 retrospective 来源引用。

运行数据、recorder 和 memory 全部留在 /dev/shm/aprof-<task-id>；不自动回写共享盘。默认 baseline 为 assumed，不执行完整正确性；候选真实完整检查一次，其后普通报告按全输出内容和身份复用可信结果。独立审计须明确开启并单独计费。
