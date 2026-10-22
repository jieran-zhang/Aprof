# swi_glu 自主无硬件回归

R1：Host将split轴之后的连续积乘半轴得到segment S；输出N=input/2。核按连续输出块切分，每次count=min(remaining,4096,S-inSegment)，x0=out+floor(out/S)*S，x1=x0+S，两个输入片对应一个输出片。Vector执行sigmoid门链，16位三次Cast。

工作量：每输出3s字节GM；每段3次DMA；float每段5个算术API，16位另3次Cast。UB float=12T，16位=18T。短S使主循环不是ceil(N/4096)，而每核切开的segment片计数。

首选 action.coalesce_contiguous_transfers（problem.tiny_transfer_setup_amplification）。先仅在同owner的短segment内组成h行批次，以blockCount/stride搬运x0和x1并批量计算，输出按连续有效行写回；物理行跨度A=align32(S*s)/s须与S分开。长segment维持原路径；不新增Tiling Key，参数由连续性/API和容量决定。

比较理由：短segment时增加流水仍保持每段三次小DMA和整条Vector发射；规则多行批量可直接减少这类发射。输入不是跨segment连续，不能简单count扩大；需合法strided API或UB行拼接，短行padding成本计入。

覆盖与残余：长segment原有单槽链仍未优化；短segment中的Exp/Div和3s有效GM仍保留。若多段API因跨度不合法退回逐行搬运，批量Vector仍需独立核算，不能声称DMA必然减少。

R2新增静态证据：从全部shape/dim计算S发现存在S远大于4096的连续域与短S域；批量方法只改善短S，长S不得标全覆盖。奇数S行padding需按A=ceil(S*s/32)*32/s预算：若批量Vector读取padding，应显式初始化h*(A-S)元素而不清零有效区；输出用每行S有效元素的多段DataCopyPad丢弃dummy。A3无mode重载输入srcStride=S*s字节、dstStride=0，输出srcStride=0 DataBlock、dstStride=0字节，blockCount=h<=4095；待目标SDK确认。禁止把输入两半连读为同一operand。

R1和R2均未实施、未编译、未测量、未运行正确性；无KEEP/晋升/收益声明。P提取原有owner计划，尚未形成可实施C2。

知识实际采用：

- diagnosis skills/ascendc-aprof-diagnosis/graph/problems/problem.tiny_transfer_setup_amplification.md @ lines:276-428 sha256:fe588d08566865b0b3a47cd32214235a2d572ec54d4bf356ba9a4f0cdd767b05；partial：机制推导适用，尚无目标profile因果证明；短segment的h行批量使每h行的2次输入和1次输出批量API以及整条Vector链取代h组，理想发射减少到1/h；stride非法时DMA减少不成立；正文要求把性能与容量/依赖合法性分开

- optimization skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/coalesce.md @ lines:69-108 sha256:ae97f3a0b11ed80146830606cd1cdd15eff6088336d43c639611ac5af7b4d96c；partial：正文给方法与完成边，具体SDK支持和资源未确认；先仅在同owner的短segment内组成h行批次，以blockCount/stride搬运x0和x1并批量计算，输出按连续有效行写回；物理行跨度A=align32(S*s)/s须与S分开。长segment维持原路径；不新增Tiling Key，参数由连续性/API和容量决定。；tile放大增加已分配UB和最后读前存活时间；SwiGLU还可能增加行padding与mask处理

- diagnosis skills/ascendc-aprof-diagnosis/graph/problems/problem.pipeline_serialization.md @ lines:271-407 sha256:4cacb553cd1af278ad9d2513e21cd70f968767b0eac3ef28ae42a90eb4e70d74；partial：机制推导适用，尚无目标profile因果证明；减少跨tile可避免的串行等待窗口；源算法字节、算术及DMA次数不减少；仅多tile核有稳态机会；正文要求把性能与容量/依赖合法性分开

- optimization skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md @ lines:89-207 sha256:44a68a5b982eb4107ad17d4a133a9b4786646609ef41484c0dd68e7533124b01；partial：正文给方法与完成边，具体SDK支持和资源未确认；原owner下将raw输入输出物理槽变2，计算scratch单份并明确最后消费者；容量不足返回C2；新增输入/输出物理槽、prolog/drain和回卷事件；若容量导致T缩小，tile和API次数增加

- parallel-planning skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md @ lines:83-188 sha256:0a602958e66a719ea6d7a959a6d447ac684f2ef53a22fc1fe3dc838bde06edd4；partial：SwiGLU仅输出owner连续，其输入两半地址仍须保留segment映射；提取现有owner区间；区分分核粒度与UB tile，保留原核数公式；所有物理分配按字节计入，不能仅Free就从UB账上删除

- optimization skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/strided-pad.md @ lines:77-138 sha256:dbd61eaa8bb85b89b10ae445f1cff983baaaf8aa7a707b07900c18ac60262403；partial：910C/A3任务配置与A2/A3无mode重载正文对应；实际SDK未检查，blockCount/stride/容量及输出有效长度需逐参数闭合；从全部shape/dim计算S发现存在S远大于4096的连续域与短S域；批量方法只改善短S，长S不得标全覆盖。奇数S行padding需按A=ceil(S*s/32)*32/s预算：若批量Vector读取padding，应显式初始化h*(A-S)元素而不清零有效区；输出用每行S有效元素的多段DataCopyPad丢弃dummy。A3无mode重载输入srcStride=S*s字节、dstStride=0，输出srcStride=0 DataBlock、dstStride=0字节，blockCount=h<=4095；待目标SDK确认。禁止把输入两半连读为同一operand。

机读结果：[{"schema_version": "aprof.action-decision-validation/v2", "task_id": "case-04", "decision_hash": "sha256:ecc8dbaa9b245c9c78f0d84c26489e24ca0e2529d64aca2f072d04cf18d0e96d", "selection_mode": "conditional_plan", "opportunity_count": 2, "status": "conditional", "missing_safety": ["constraint.capacity", "constraint.capacity"], "failed_safety": [], "pending_required_evidence": ["check-merge-safe-0"], "performance_claim": false, "semantic_review_required": true, "C1_valid": true}, {"schema_version": "aprof.action-decision-validation/v2", "task_id": "case-04", "decision_hash": "sha256:55df3696a8c61c1e45586c6b160c40f6cc8ffdeb5ca067d558e0170aad31127f", "selection_mode": "conditional_plan", "opportunity_count": 2, "status": "conditional", "missing_safety": ["constraint.capacity", "constraint.capacity"], "failed_safety": [], "pending_required_evidence": ["check-merge-safe-0"], "performance_claim": false, "semantic_review_required": true, "C1_valid": true}]
