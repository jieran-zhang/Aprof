---
name: aprof-optimize-batch
description: 接收多个 Ascend C 算子优化任务，编排固定版本 APROF coordinator，并让独立 agent 将全部尝试整理成可供离线知识学习的 memory。
---

# 多算子优化与 memory 采集

读取 [批次执行契约](references/batch.md)。使用仓库中显式指定的完整 skill-lib；新知识采集要求支持 `aprof.handoff/v2` 和 `aprof.knowledge-route/v1`，当前为 graph-base/1.2.0。不能从 catalog 默认值推断版本。

1. 先按 [批次启动检查](references/batch.md#批次启动检查) 验证共用 runtime/oracle/采集能力，避免将同一已知缺项重复派发给各算子。冻结任务清单、原始源码、workload/oracle、split、模型、知识区快照/覆盖参数和每任务预算，写 `aprof.optimization-batch/v1`。训练任务和留出评估使用分开的 agent 上下文。
2. 每个任务调用所选包的 `skills/ascendc-aprof-coordinator/SKILL.md`，传入任务工作区、预算与批次绑定。该 coordinator 串联 C0→C5；不在脚手架再定义诊断矩阵、并行策略或计时 gate。
3. 优化过程中只要求及时落盘既有阶段 contract、候选登记、实际源码和原始证据。每次尝试在执行前登记；成功、失败、NOOP、取消和基础设施阻塞全部闭合到任务结果。所有优化与在线验证消耗同一任务预算。
4. **为每个任务分派一个不同于优化 agent 的 memory recorder**，使用 [recorder 指令](references/recorder.md) 和 [memory 规范](references/memory.md)。可以在只读阶段快照产生后整理，最终以 coordinator 关闭的候选清单核对。recorder 不能修改候选、补测或替原任务追认成功。
5. 分别交付各算子的代码/结果、task-result、memory 和批次索引；报告优化成本与归档成本。校验失败的 memory 保留为待补材料，原算子结果不被改写。

1.1.0 Vector 验收的新批次采用 [软目标策略 v4](references/vector-acceptance-soft-targets-v4.json)，在首个 seed 交付前冻结；各字段如何传到 coordinator、阶段检查和 recorder 见 [预算绑定](references/batch.md#预算恢复和收尾)。其他任务沿用用户明确指定的预算；新策略不延长已派发任务。

主机/设备可并行程度由实际可用资源决定；同一物理设备的计时独占。CPU 整理可以并行，任务 workspace、模型上下文和输出目录隔离。不能用并发计时混淆候选性能。

先让一个正式任务走通完整正确性、R0 和真实候选反馈，再派发其余依赖同一能力的任务。候选被性能收益门槛拒绝仍是有效反馈；无需优化获胜才能证明链路可执行。共同测量条件导致 inconclusive 时先解决条件缺口，不能直接扩批。只有能力检查通过、memory 已归档或任务已收尾，都不能写成优化已完成。

性能反馈和收尾都调用所选包的统一计时协议：基线 A 在有效范围内复用，候选通过完整正确性后采 B。新任务预声明包内有界异常统计策略，原始数据与剔除明细保留；最终 A/B 计时前准备好baseline 信任声明与候选完整正确性和存储条件。额外机制 profile 按需采；不调用旧 collection 的配对计时来替代新流程。

此 skill 负责采集。任务内不修改被使用的 graph/knowledge，也不向其他任务注入本批次刚生成的 lesson。需要离线学习时交给 [aprof-train-knowledge](../aprof-train-knowledge/SKILL.md)。

运行数据、recorder 和 memory 全部留在 /dev/shm/aprof-<task-id>；不自动回写共享盘。默认 baseline 为 assumed，不执行完整正确性；候选真实完整检查一次，其后普通报告按全输出内容和身份复用可信结果。独立审计须明确开启并单独计费。
