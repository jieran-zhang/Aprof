# AProf 优化策略先验

本文是生成初始 SkillGraph 的可读冷启动先验，不是 runtime 路由契约。历史六类是非互斥解释维度；已发布图的类型边与 transformation 契约具有权威性，不能用本文替代或绕过它们。

## 使用顺序

1. 先用 diagnosis predicate 与临时机制假设，保留关联假设、指标、缺证据和反证；历史 `problem_family` 可以贡献多个先验维度。
2. 无问题族时可根据 profile 解释：MTE/Memory → `data_movement`，overlap/bubble → `pipeline_parallel`，UB/resource conflict → `onchip_memory`，核占用/负载均衡 → `ai_core_utilization`，Vector/Scalar/API → `api_algorithm`。
3. 源码检查可关注 `tileLength`、`blockDim`、`DataCopy`、`InitBuffer`、`TBuf/TQue`、`SetFlag/WaitFlag`、`MatMul/MMAD`、`Softmax`、`Sort/TopK`、`Reduce`、`GetValue/SetValue`、`std::` 与 Vector API。证据不足保留 `unknown_unresolved` 或选择合法 `NOOP`，不能强行分类。

按需读 `optimization-candidate-design.md` 和一份对应策略；复杂算子再选 MatMul、Softmax/FA、Reduction/Sort、Vector/Scalar 手册之一。API 或平台问题未解时读 `optimization-local-knowledge-index.md`，不默认展开全部外部/通用技能。

## 共用边界

环境与 architecture 证据有效即可复用，实际执行身份仍需核验。修改前分析任务分解、容量、每核工作、流量下界和可达性能；默认保持 `production_safe` 的数学、精度、动态域、尾块与边界。风险 API 修改先查准确来源，修改后先静态审查再构建与完整正确性。

候选反馈与正式收尾统一遵循 [主工作流](../../ascendc-aprof-workflow/SKILL.md) 和 [计时协议](../../ascendc-aprof-profiling/references/unified-timing.md)。PMU 是按需机制证据，simulator 是代理证据；二者不能替代完整调用计时。合法图要求的 profile predicate 缺失时需补证据，未实现 extractor 保持未知。

固定 tile 本身不等于特化；只有 case 捷径、未经验证的固定假设、删动态处理、降精度或缩小契约域时才标 `scope_status=benchmark_specialized`。

## 六维策略表

| 问题族 | 触发信号 | 候选方向 | 参考 | 预期变化 | 不适用条件 |
| --- | --- | --- | --- | --- | --- |
| `tiling` | tile 过大/小、尾块慢、任务形状或 MatMul/FA 分解不匹配 | 任务/tile/shape 分解、尾块统一、Vec/UB 与 Cube/L1+L0 两级划分 | `tiling-optimization-strategies.md` | 有效搬运增大、尾块失衡降低、CUBE/MTE/Fixpipe 更均衡 | 容量未知、动态 shape 缺失、padding 参与有效计算 |
| `data_movement` | 小/非对齐 DataCopy、GM 冗余往返、高 MTE 低带宽 | 合并搬运、有效长度 DataCopyPad、L2/驻留复用 | `data-movement-optimization-strategies.md` | MTE 指令与 GM 字节降低、每指令有效字节提高 | padding 被消费、真实带宽饱和、存活期不明 |
| `pipeline_parallel` | 重叠低、空隙、双缓冲仍串行、PING/PONG/AIC/AIV 等待 | 序幕/稳态/收尾重排、事件解耦、UnitFlag/预取/提前发射、同步修复 | `pipeline-parallel-optimization-strategies.md` | 重叠提高、等待降低、耗时降低且 GM 不增加 | 循环太短、容量不足、同步是算法必需 |
| `onchip_memory` | UB 占用高、参数重读、bank 冲突、workspace slot 问题 | 存活期复用、驻留、分区/布局/padding、slot 拆分 | `onchip-memory-optimization-strategies.md` | 占用、重读、冲突/等待降低 | 别名不明、无冲突证据、驻留挤压主 tile |
| `ai_core_utilization` | 活跃核少、尾块失衡、长 K/MN 并行度低、FA decode 任务少 | 任务分解、StreamK/DP+SK、split-KV、分阶段并行 | `ai-core-utilization-optimization-strategies.md` | 有效活跃核增多、核间波动和尾部降低 | 小 workload、硬编码核数、缺 workspace/数值论证 |
| `api_algorithm` | Scalar/API 开销、repeat 风险、局部 API 低效、GM 往返 | Scalar 重写、repeat/Counter、Cast 融合、online softmax、局部 API 替换 | `api-algorithm-optimization-strategies.md` | Scalar/misc 降低、Vector 效率提高、GM 往返减少 | 支持未知、精度改变、融合超 UB |

## 旧计划字段映射

旧 `optimization_plan.json` 策略记录保留 `problem_family`、`linked_hypotheses`、`linked_metrics`、`bound_type`、`optimization_scope`、`semantic_requirements`、`structural_edits`、`capacity_model`、`abort_conditions`、`required_evidence`、`expected_metric_delta`、`pre_patch_checks`、`post_patch_checks` 和 `failure_handoff`。无法由证据填写时用空列表或 `"unknown"`，在 `notes` 说明缺失，不能编指标。

可执行候选对应关系：`decision_gate` 来自 `required_evidence`、触发与禁用条件；`capacity_formula` 来自 `capacity_model`；`structural_patch_shape` 来自 `structural_edits`；`metric_delta` 来自 `expected_metric_delta`；`abort_conditions` 原样保留。这些是旧格式映射，不新增严格 schema 字段。

## 判定与失败

本轮输出候选代码与 runtime 的 `performance_engineering_only` 结果，不据此指定 `best_op`。`semantic_status=preserved`、`scope_status=production_safe`、`portability_risk != high` 和 `accepted_for` 含 `production` 是历史生产选择契约的条件，不是新计时结果字段；当前流程不为补这些字段转入旧配对或 episode 通道。快但被拒或仅适合 benchmark 的结果，在 `final_optimization_report.md` 保留实际比较及拒绝原因。

正确性失败交 `ascendc-precision-debug`，运行错误交 `ascendc-runtime-debug`，超时/崩溃/AIC 交 `ascendc-crash-debug`，缺采集证据交 `ops-profiling`。回归先保留结果并停止该尝试，有剩余范围和预算才开始下一候选。
