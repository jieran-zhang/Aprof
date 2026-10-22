# 执行优化经验入口

继承冻结的并行和 dispatch 计划，再处理 tile、buffer、搬运、API 与流水。
先使用合法图路由选择技能；条件不明、证据冲突或需要反例时，再从
[Wiki 索引](../../../wiki/index.json) 读取一篇相关条目。

从 1.0.0 继承的已验证规则范围只有 910C/A3、CANN 9.0.0 下的 `exp-tile8192`。
同一源码与二进制的 20 case 正确性、42 项边界、控制和每 case 30 对正式
Task 计时已复用并回放；缺少的候选五次 PMU 与 oracle 已完成。
最终 gate 完整回放已得到 `production_safe_gain`，实际进程以 exit code 0
结束。原发布仅验证 exp 条目及其对应的单个 canonical skill 修订。
1.0.1 仍是未封存候选；继承的证据不替代当前 runtime 变更或新候选的验收。
原任务的 oracle 解析失败与 PMU 续跑的证据绑定失败均保持失败记录；后续
成功的 gate-only 续跑没有新增构建、PMU 采集或正式计时样本。
`norm-p-specialization`、`tile-amortization`、`sigmoid-pipeline`、
`prefetch-boundaries`、`ub-accumulator` 及其余条目继续保留条件性观察、反例
和待验证问题；`parent-baseline` 保留连续搜索的比较边界。exp 的回执不能
覆盖 mish/addcdiv，也不能证明 sigmoid 流水收益。45 次 validation 对比与
封存后全量 test 在原限域发布中均未运行。

每个后续改动仍须满足图合同，并将完整正确性、适用边界、控制、正式计时
和机制证据绑定到实际源码与二进制。仅当显式续跑协议允许且身份、原始证据
和时间窗口全部可回放时，才能复用已通过的分项；旧失败回执保持失败。
Wiki 的点估计不能代替机器 gate，缺失的 profiling 谓词保持 unknown。
