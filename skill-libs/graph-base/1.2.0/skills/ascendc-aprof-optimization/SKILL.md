---
name: ascendc-aprof-optimization
description: 按 C2 的算法、所有权和实现自由度，在隔离工程实施 Ascend C 候选，完成审查、构建与完整正确性，并用执行知识树记录 C3。
---

# AProf 候选实现

职责见 [optimization 角色](../../workflows/agents/optimization.md)，输入输出见 [C3](../../workflows/contracts/candidate.md)。输入包含 C0、C2 的 action/模板快照、具体参数、自由度和实际父版本；无需重新读取诊断图或规划知识目录。

从 [执行知识树](knowledge/ROUTER.md) 选择 tiling/tail、搬运、存活期、流水同步、Vector/API、精度边界方法。一次变换可引用多个分支。格式、来源和初值见 [知识规范](knowledge/FORMAT.md)。

1. 在隔离工程按选定 action 实现一个可检验意图。记录实际方法 ID/版本、源码差异、参数调整和 C2 符合性；未知硬前提不能靠模板自动补足。
2. 修改算法、任务/输出所有权、归约顺序或 workspace 所有权时，先交 coordinator 重规划。只在 C2 已授权自由度内调 tile、buffer、局部 API。
3. 构建前调用 ascendc-code-review；API/单位不明调用 ascendc-api-best-practices 或 ascendc-docs-search。只有裸 kernel 时使用 ascendc-kernel-direct-invoke。
4. 保留命令、退出码、冻结源码/binary 与完整 correctness。同一候选源变化后不得沿用旧正确性。失败先返回，精度问题用 ascendc-precision-debug，异常/超时/挂起用 ascendc-runtime-debug 或 ascendc-crash-debug。
5. 只有审查、构建和原 oracle 完整正确性通过，计时配置、输入与完整 kernel 序列齐备，才返回 C3 completed 供 profiling 采 B。

使用 `knowledge route --root <包> --owner optimization --context <evidence.json>`，features 按执行问题命中多个分支。C3 记录实际采用的知识条目，不把命中的全部条目当作已执行。历史案例的原协议、失败与适用域必须保留；没有新协议下的性能承诺。

新候选使用 aprof.handoff/v2，不伪造旧 candidate_draft/RouteDecision/episode。明确授权的图外实验保留 unadmitted 与授权来源；不自动变成图训练样本。性能比较、继续父版本和最终裁决由 coordinator 推进。
