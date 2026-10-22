# mish 自主无硬件回归

R1：Host连续分块；每tile CopyIn→Compute→CopyOut单槽链。FP32路径Adds拷贝输入，stable softplus、额外Exp负尾修正、Tanh、两次Select与Mul，再Adds拷贝输出；16位Cast进出。Compare对齐64元素。

工作量：每输出2s字节GM；每tile 2次DMA和15次Vector API（包含输入/输出Adds或Cast）；mask按256B向上对齐。静态UB=(2s+12)T+align256(ceil(T/8))。

首选 action.coalesce_contiguous_transfers（problem.tiny_transfer_setup_amplification）。保留所有负尾修正、Compare对齐与舍入，先比较单槽T=2048→4096的连续tile合并，若容量及API上界允许，原任务数不变，减少DMA和整条Vector链的发射次数。T未测最优。

比较理由：15步Vector链使纯流水不会减少主要计算工作；T翻倍将各长核的DMA及整条链接口发射约减半，且可参数化，不改算法和owner。双槽仍有价值但需要新增槽和事件，待发射/稳态时间证据再比较。

覆盖与残余：稳定softplus的Exp/Ln/Tanh和两次Select、每输出2sGM均保留；FP32 Adds(identity)可能涉及±0，不能套coalesce_cast直接删除。

R2新增静态证据：逐条核算Compute为15个API，两个dtype分支各只执行一次输入/输出转换；T=2048的UB分别41216B(float)、33024B(16位)，T=4096分别82432B/66048B。Compare仍每64元素向上取整，不得将有效输出长度也对齐扩写。

R1和R2均未实施、未编译、未测量、未运行正确性；无KEEP/晋升/收益声明。P提取原有owner计划，尚未形成可实施C2。

知识实际采用：

- diagnosis skills/ascendc-aprof-diagnosis/graph/problems/problem.tiny_transfer_setup_amplification.md @ lines:276-428 sha256:fe588d08566865b0b3a47cd32214235a2d572ec54d4bf356ba9a4f0cdd767b05；partial：机制推导适用，尚无目标profile因果证明；同owner连续tile从T扩大到2T可将每核ceil(Nc/T)降为ceil(Nc/(2T))，减少接口发射；有效字节和逐元素算术保留；正文要求把性能与容量/依赖合法性分开

- optimization skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/coalesce.md @ lines:69-108 sha256:ae97f3a0b11ed80146830606cd1cdd15eff6088336d43c639611ac5af7b4d96c；partial：正文给方法与完成边，具体SDK支持和资源未确认；保持原分核，扩大合法连续tile，保留有效尾长和数值顺序；tile加倍使全部buffer近似加倍；单核最后余数不同，API内部预留和最大count必须核验

- diagnosis skills/ascendc-aprof-diagnosis/graph/problems/problem.pipeline_serialization.md @ lines:271-407 sha256:4cacb553cd1af278ad9d2513e21cd70f968767b0eac3ef28ae42a90eb4e70d74；partial：机制推导适用，尚无目标profile因果证明；减少跨tile可避免的串行等待窗口；源算法字节、算术及DMA次数不减少；仅多tile核有稳态机会；正文要求把性能与容量/依赖合法性分开

- optimization skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md @ lines:89-207 sha256:44a68a5b982eb4107ad17d4a133a9b4786646609ef41484c0dd68e7533124b01；partial：正文给方法与完成边，具体SDK支持和资源未确认；原owner下将raw输入输出物理槽变2，计算scratch单份并明确最后消费者；容量不足返回C2；新增输入/输出物理槽、prolog/drain和回卷事件；若容量导致T缩小，tile和API次数增加

- parallel-planning skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md @ lines:83-188 sha256:0a602958e66a719ea6d7a959a6d447ac684f2ef53a22fc1fe3dc838bde06edd4；full：连续同形逐元素独占输出所有权适用；容量/API实例化仍待确认；提取现有owner区间；区分分核粒度与UB tile，保留原核数公式；所有物理分配按字节计入，不能仅Free就从UB账上删除

机读结果：[{"schema_version": "aprof.action-decision-validation/v2", "task_id": "case-02", "decision_hash": "sha256:2f6c40dd54fc87c4bfc9197639963bb2767154aee93a4105410513192b91a704", "selection_mode": "conditional_plan", "opportunity_count": 2, "status": "conditional", "missing_safety": ["constraint.capacity", "constraint.capacity"], "failed_safety": [], "pending_required_evidence": ["check-merge-safe-0"], "performance_claim": false, "semantic_review_required": true, "C1_valid": true}, {"schema_version": "aprof.action-decision-validation/v2", "task_id": "case-02", "decision_hash": "sha256:f1c3f34ae5af5813e006d37c8a84d9c1f2122ff6e7b5eea4e5937193d3a732d8", "selection_mode": "conditional_plan", "opportunity_count": 2, "status": "conditional", "missing_safety": ["constraint.capacity", "constraint.capacity"], "failed_safety": [], "pending_required_evidence": ["check-merge-safe-0"], "performance_claim": false, "semantic_review_required": true, "C1_valid": true}]
