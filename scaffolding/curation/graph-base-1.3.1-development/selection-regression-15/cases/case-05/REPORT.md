# apply_adam_w 自主无硬件回归

R1：Host查询核数/UB并以20T(float)或30T(16位)+mask+8192+2048预算最大合法64对齐tile；四输入一输出。float原地复用五队列，16位四输入Cast到A-D后释放raw输入，再A-E工作及输出Cast。SafeSqrt/SafeDiv保留异常数处理，weightDecay按属性分支。

工作量：每输出5s字节GM，5次DMA/tile；float无Cast，16位5次Cast。算术及Compare/Select安全链每tile固定发射，weightDecay非零增加2次。UB float=20T+mask+10240，16位=30T+mask+10240。

首选 action.reuse_disjoint_onchip_buffers（problem.onchip_capacity_pressure）。仅对16位路径比较四个raw输入8T字节arena与FP32 scratch E的4T字节分时共享，CastInputs最后读完成后才把arena当E；A-D与rawOut仍独立。静态分配从30T降为26T，再在64对齐和相同API预留下扩大T。float维持原路径。

比较理由：Host已按容量取大tile；把五个raw队列改双槽会从30T升40T(float从20T升40T)并迫使缩tile，增加安全链发射。16位raw输入在Cast后死亡，E在CastInputs后首用有明确可分析的非重叠机会，可降低容量而保持数值链。异步完成和arena API仍需闭合。

覆盖与残余：float全路径保持不变；16位5次Cast、异常数Select链和5sGM不减。若新增barrier阻塞原来跨引擎重叠，则省容量可能不值，需要与单槽原T和双槽Tprime实际比较。

R2新增静态证据：进一步查CastOne逐输入DeQue/Cast/Free与E首用Muls的边：词法Free并非物理内存自动共享，必须显式arena且Cast完成→E写入。单个raw槽仅2T不能冒充4T；四槽统一8T arena才容纳E。理论30→26是分配模型，实际收益未测，API不可表达时撤回。

R1和R2均未实施、未编译、未测量、未运行正确性；无KEEP/晋升/收益声明。P提取原有owner计划，尚未形成可实施C2。

知识实际采用：

- diagnosis skills/ascendc-aprof-diagnosis/graph/problems/problem.onchip_capacity_pressure.md @ lines:307-448 sha256:5a891db1219586ba9e282be035c81a632479d37de9b281c3f51156b1a0927a96；partial：机制推导适用，尚无目标profile因果证明；16位raw输入arena与E分时共享：30T→26T字节（不含mask及预留），同容量允许更大64对齐T，减少整条链的tile发射；正文要求把性能与容量/依赖合法性分开

- optimization skills/ascendc-aprof-optimization/knowledge/branches/buffer-lifetime/recipes/reuse.md @ lines:109-171 sha256:956301b3e9b43f9f4e8fd8074811f5723f43478b3b82c3591af1aef8aafabce4；partial：正文给方法与完成边，具体SDK支持和资源未确认；仅对16位路径比较四个raw输入8T字节arena与FP32 scratch E的4T字节分时共享，CastInputs最后读完成后才把arena当E；A-D与rawOut仍独立。静态分配从30T降为26T，再在64对齐和相同API预留下扩大T。float维持原路径。；新增显式arena、alias证明与Cast完成到E首次写入事件；屏障可能丢失重叠；float域不收益

- diagnosis skills/ascendc-aprof-diagnosis/graph/problems/problem.pipeline_serialization.md @ lines:271-407 sha256:4cacb553cd1af278ad9d2513e21cd70f968767b0eac3ef28ae42a90eb4e70d74；partial：机制推导适用，尚无目标profile因果证明；减少跨tile可避免的串行等待窗口；源算法字节、算术及DMA次数不减少；仅多tile核有稳态机会；正文要求把性能与容量/依赖合法性分开

- optimization skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md @ lines:89-207 sha256:44a68a5b982eb4107ad17d4a133a9b4786646609ef41484c0dd68e7533124b01；partial：正文给方法与完成边，具体SDK支持和资源未确认；原owner下将raw输入输出物理槽变2，计算scratch单份并明确最后消费者；容量不足返回C2；新增输入/输出物理槽、prolog/drain和回卷事件；若容量导致T缩小，tile和API次数增加

- parallel-planning skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md @ lines:83-188 sha256:0a602958e66a719ea6d7a959a6d447ac684f2ef53a22fc1fe3dc838bde06edd4；full：连续同形逐元素独占输出所有权适用；容量/API实例化仍待确认；提取现有owner区间；区分分核粒度与UB tile，保留原核数公式；所有物理分配按字节计入，不能仅Free就从UB账上删除

机读结果：[{"schema_version": "aprof.action-decision-validation/v2", "task_id": "case-05", "decision_hash": "sha256:2e84911c91644ffeb5c4a54013eda03ca599592f4e2e2a1a4d12faceaa8c4956", "selection_mode": "conditional_plan", "opportunity_count": 2, "status": "conditional", "missing_safety": ["constraint.capacity", "constraint.capacity", "constraint.dependency_lifetime", "constraint.dependency_lifetime"], "failed_safety": [], "pending_required_evidence": ["check-reuse-safe-0", "check-reuse-safe-1"], "performance_claim": false, "semantic_review_required": true, "C1_valid": true}, {"schema_version": "aprof.action-decision-validation/v2", "task_id": "case-05", "decision_hash": "sha256:011889e91a30bf518efdedabed3be83a2c42ceca113931545c797e8dbd3c07e8", "selection_mode": "conditional_plan", "opportunity_count": 2, "status": "conditional", "missing_safety": ["constraint.capacity", "constraint.capacity", "constraint.dependency_lifetime", "constraint.dependency_lifetime"], "failed_safety": [], "pending_required_evidence": ["check-reuse-safe-0", "check-reuse-safe-1"], "performance_claim": false, "semantic_review_required": true, "C1_valid": true}]
