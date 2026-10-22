# exp 自主无硬件回归

R1：Host预计算multiplier/shift，按ceil(N/4096)和可用核上限分连续块；每tile一次读一次写，float执行Muls/Adds/Exp，16位先Cast FP32再三步计算及Cast回原dtype。无归约、广播、跨核同步或重复输入。

工作量：每输出2s字节GM；每tile 2次DMA、3次Vector算术；16位另2次Cast。静态UB float=8T，16位=12T，另API预留未知。

首选 action.software_pipeline_stages（problem.pipeline_serialization）。在原分核/原精度下比较两物理输入/输出槽，保持T=4096为首候选；若容量不允许则先返回C2比较T而非强行减半。单份FP32临时区仍按Vector顺序复用，输入/输出槽分别以最后读完成为回卷边。

比较理由：连续大域已有三步Vector链，无重复GM流量可删；流水可覆盖每个多tile核的读/计算/写串行间隙，两物理槽在16位路径新增16384B，小于T加倍新增49152B；float32路径两者均新增32768B，因此float32不能以容量优势排序，仍须比较重叠机会与接口发射减少。更大tile虽然少接口，但固定4096已非逐元素小包且不减少Exp必要算术。

覆盖与残余：Exp及Cast算术、每输出2s有效GM字节、尾部和host启动保留；base=1不能仅凭样例值域把0*x改成常量，因为原API仍允许NaN/Inf。

R2新增静态证据：核验4096对应float单槽32768B、双槽65536B；16位单槽49152B、双槽65536B，均未计API预留。16位双槽只增加16384B而将tile翻倍增加49152B，因此保留流水首选；实际可用UB和稳态占比仍未知。

R1和R2均未实施、未编译、未测量、未运行正确性；无KEEP/晋升/收益声明。P提取原有owner计划，尚未形成可实施C2。

知识实际采用：

- diagnosis skills/ascendc-aprof-diagnosis/graph/problems/problem.pipeline_serialization.md @ lines:271-407 sha256:4cacb553cd1af278ad9d2513e21cd70f968767b0eac3ef28ae42a90eb4e70d74；partial：机制推导适用，尚无目标profile因果证明；减少跨tile可避免的串行等待窗口；源算法字节、算术及DMA次数不减少；仅多tile核有稳态机会；正文要求把性能与容量/依赖合法性分开

- optimization skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md @ lines:89-207 sha256:44a68a5b982eb4107ad17d4a133a9b4786646609ef41484c0dd68e7533124b01；partial：正文给方法与完成边，具体SDK支持和资源未确认；原owner下将raw输入输出物理槽变2，计算scratch单份并明确最后消费者；容量不足返回C2；新增输入/输出物理槽、prolog/drain和回卷事件；若容量导致T缩小，tile和API次数增加

- diagnosis skills/ascendc-aprof-diagnosis/graph/problems/problem.tiny_transfer_setup_amplification.md @ lines:276-428 sha256:fe588d08566865b0b3a47cd32214235a2d572ec54d4bf356ba9a4f0cdd767b05；partial：机制推导适用，尚无目标profile因果证明；同owner连续tile从T扩大到2T可将每核ceil(Nc/T)降为ceil(Nc/(2T))，减少接口发射；有效字节和逐元素算术保留；正文要求把性能与容量/依赖合法性分开

- optimization skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/coalesce.md @ lines:69-108 sha256:ae97f3a0b11ed80146830606cd1cdd15eff6088336d43c639611ac5af7b4d96c；partial：正文给方法与完成边，具体SDK支持和资源未确认；保持原分核，扩大合法连续tile，保留有效尾长和数值顺序；tile加倍使全部buffer近似加倍；单核最后余数不同，API内部预留和最大count必须核验

- parallel-planning skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md @ lines:83-188 sha256:0a602958e66a719ea6d7a959a6d447ac684f2ef53a22fc1fe3dc838bde06edd4；full：连续同形逐元素独占输出所有权适用；容量/API实例化仍待确认；提取现有owner区间；区分分核粒度与UB tile，保留原核数公式；所有物理分配按字节计入，不能仅Free就从UB账上删除

机读结果：[{"schema_version": "aprof.action-decision-validation/v2", "task_id": "case-01", "decision_hash": "sha256:1083344249d980f4658388f0a87881029b412f17000214d6166f5c2f5fe0f0c7", "selection_mode": "conditional_plan", "opportunity_count": 2, "status": "conditional", "missing_safety": ["constraint.capacity", "constraint.capacity", "constraint.dependency_lifetime", "constraint.dependency_lifetime"], "failed_safety": [], "pending_required_evidence": ["check-pipe-safe-0", "check-pipe-safe-1"], "performance_claim": false, "semantic_review_required": true, "C1_valid": true}, {"schema_version": "aprof.action-decision-validation/v2", "task_id": "case-01", "decision_hash": "sha256:94586e1faa9d91b1b5f2ed0db3b78b5625ef9d1794e68069d18f851f41ff8ef9", "selection_mode": "conditional_plan", "opportunity_count": 2, "status": "conditional", "missing_safety": ["constraint.capacity", "constraint.capacity", "constraint.dependency_lifetime", "constraint.dependency_lifetime"], "failed_safety": [], "pending_required_evidence": ["check-pipe-safe-0", "check-pipe-safe-1"], "performance_claim": false, "semantic_review_required": true, "C1_valid": true}]

独立语义复核更正：原文将16位路径的UB优势泛化到了float32；已按dtype分别描述，两轮选择保持不变，decision/C1及所有受影响引用已重验。详见review-correction.json。
