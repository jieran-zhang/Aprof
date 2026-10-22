# 运行时修复与纸面交接

runtime 0.8.1 沿用 action-decision/v3、handoff/v4 和现有结果关联入口；没有增加输入 schema、执行模型或日常必跑命令。

## 映射在首次实施前闭合

共享 `workload_case_payloads` 读取完整 `cases[{case_id,workload}]`，新图首次选择和有效反馈使用同一规则。后继按冻结 payload 核对 capture，不仅核对 case ID。D7 的裸矩阵仍可分析，缺映射回执为 conditional，C2 可继续条件规划，C3 明确拒绝；不能通过旧单机会 v2 入口或计划保证绕过。

混合裸行与包装行、重复 ID、部分 payload、错误覆盖及 D7 空 payload 被明确拒绝，不能猜补。D6 历史首轮继续按其原义；缺少测前映射的旧链不能事后追认为准入。该缺项是引用与复现边界，不是性能假设，也不要求先做硬件实验。

## 方案身份贯穿入口

完整 v4 链原有身份检查保持，独立交接决策入口补上非空且一致的 scheme ID/hash 检查。只有局部 Action 就绪、命中正文或存在文字方案不能准入整个候选。实例、目标、参数、共同计划、源码及实际 P/O 快照继续精确绑定。

## 实际检查

[CPU 检查回执](CPU-CHECKS.json)保存日志及 hash：历史 v2/v3 决策和 v4 交接 107 项、新 D7 映射及真实交接反例 18 项、当前知识/输入驻留/独立目录回放 30 项通过，共155项。另有[开发状态模型](execution-models.json)核对30种事件初始化/收尾组合，不模拟异步延迟或设备性能。

[三条完整纸面交接](examples/README.md)均从首次决定前创建完整 workload 映射，逐成员运行真实 router，并通过真实 decision 实施校验及 v4 链校验：

- 连续搬运单成员 → `implementation.memory-transfer.coalesce`。
- 搬运＋派生结果复用 → 上述搬运及 `implementation.buffer-lifetime.derived-results`。
- 搬运＋管理简化 → 上述搬运及 `implementation.pipeline-sync.vector-static-lease`。

纸面初始特征有单独、精确引用的结构声明，绑定父本与 workload；它们是 CPU 合同声明，`source_understanding_verified=false`。这些例子检验声明上下文中的路由和交接，不证明真实源码理解、构建、oracle、异步执行或收益。runtime 返回 implemented 也不改变此限制。真实源码信息使用另由无工具行为评测检查。

## 保留的边界

knowledge.py、旧 schema、冻结快照和旧路由原字节保留。工具核验的是身份、声明及状态，不能证明任意自然语言成本理由或事前时间顺序。没有编译目标 SDK、调用设备、训练、采集 memory 或切换默认版本。
