# masked_scale 自主无硬件回归

R1：同形x/mask按输出连续切块，两个输入一个输出；x扩位、mask扩位（int8/uint8经half再float），先Mul(x,mask)后Muls(scale)，再输出转换。mask是数值乘数，127/255非布尔。

工作量：每输出(2s_x+s_m)字节GM；每tile 3次DMA和5次Vector API，整数mask为6次。UB=(2s_x+s_m+12+2I_intmask)T。

首选 action.software_pipeline_stages（problem.pipeline_serialization）。两个输入队列和输出队列使用两物理槽，FP32计算缓冲保持单份；原Mul后Muls顺序及整数mask两段Cast保留。预算(2*(2s_x+s_m)+12+2I_intmask)T+API<=可用UB。

比较理由：所有输入一次读取，无广播复用，计算链较短而有三路搬运；流水比一味放大tile更直接检验隐藏MTE延迟。T=4096的转换区已较大，放大tile的容量成本须与新增原始槽比较。

覆盖与残余：整数mask两次Cast、FP32拷贝Muls和必要三路GM保留。后续可在确证目标Cast重载后单独比较转换路径，不按case ID分派。

R2新增静态证据：int8/uint8的所有整数[-128,255]可被half精确表示，但不因此证明目标SDK支持直接int8→float Cast。原两步转换是API适用候选问题，不能宣告冗余。scale=0/1仍不删除乘法以保留NaN/Inf和乘法次序。

R1和R2均未实施、未编译、未测量、未运行正确性；无KEEP/晋升/收益声明。P提取原有owner计划，尚未形成可实施C2。

知识实际采用：

- diagnosis skills/ascendc-aprof-diagnosis/graph/problems/problem.pipeline_serialization.md @ lines:271-407 sha256:4cacb553cd1af278ad9d2513e21cd70f968767b0eac3ef28ae42a90eb4e70d74；partial：机制推导适用，尚无目标profile因果证明；减少跨tile可避免的串行等待窗口；源算法字节、算术及DMA次数不减少；仅多tile核有稳态机会；正文要求把性能与容量/依赖合法性分开

- optimization skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md @ lines:89-207 sha256:44a68a5b982eb4107ad17d4a133a9b4786646609ef41484c0dd68e7533124b01；partial：正文给方法与完成边，具体SDK支持和资源未确认；原owner下将raw输入输出物理槽变2，计算scratch单份并明确最后消费者；容量不足返回C2；新增输入/输出物理槽、prolog/drain和回卷事件；若容量导致T缩小，tile和API次数增加

- diagnosis skills/ascendc-aprof-diagnosis/graph/problems/problem.tiny_transfer_setup_amplification.md @ lines:276-428 sha256:fe588d08566865b0b3a47cd32214235a2d572ec54d4bf356ba9a4f0cdd767b05；partial：机制推导适用，尚无目标profile因果证明；同owner连续tile从T扩大到2T可将每核ceil(Nc/T)降为ceil(Nc/(2T))，减少接口发射；有效字节和逐元素算术保留；正文要求把性能与容量/依赖合法性分开

- optimization skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/coalesce.md @ lines:69-108 sha256:ae97f3a0b11ed80146830606cd1cdd15eff6088336d43c639611ac5af7b4d96c；partial：正文给方法与完成边，具体SDK支持和资源未确认；保持原分核，扩大合法连续tile，保留有效尾长和数值顺序；tile加倍使全部buffer近似加倍；单核最后余数不同，API内部预留和最大count必须核验

- parallel-planning skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md @ lines:83-188 sha256:0a602958e66a719ea6d7a959a6d447ac684f2ef53a22fc1fe3dc838bde06edd4；full：连续同形逐元素独占输出所有权适用；容量/API实例化仍待确认；提取现有owner区间；区分分核粒度与UB tile，保留原核数公式；所有物理分配按字节计入，不能仅Free就从UB账上删除

机读结果：[{"schema_version": "aprof.action-decision-validation/v2", "task_id": "case-03", "decision_hash": "sha256:d21726d4fff571a9e3e44a28fa93fa7fdad1e5d75ec300a2fdbf853357225a56", "selection_mode": "conditional_plan", "opportunity_count": 2, "status": "conditional", "missing_safety": ["constraint.capacity", "constraint.capacity", "constraint.dependency_lifetime", "constraint.dependency_lifetime"], "failed_safety": [], "pending_required_evidence": ["check-pipe-safe-0", "check-pipe-safe-1"], "performance_claim": false, "semantic_review_required": true, "C1_valid": true}, {"schema_version": "aprof.action-decision-validation/v2", "task_id": "case-03", "decision_hash": "sha256:2403bd1041693eb6fd61f84629408539580aa0901a433913ef5e8cde868e7467", "selection_mode": "conditional_plan", "opportunity_count": 2, "status": "conditional", "missing_safety": ["constraint.capacity", "constraint.capacity", "constraint.dependency_lifetime", "constraint.dependency_lifetime"], "failed_safety": [], "pending_required_evidence": ["check-pipe-safe-0", "check-pipe-safe-1"], "performance_claim": false, "semantic_review_required": true, "C1_valid": true}]
