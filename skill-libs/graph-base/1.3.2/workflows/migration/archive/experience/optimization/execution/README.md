# 执行优化经验入口

继承冻结的并行和 dispatch 计划，再处理 tile、buffer、搬运、API 与流水。
先使用合法图路由选择技能；条件不明、证据冲突或需要反例时，再从
[Wiki 索引](../../../wiki/index.json) 读取一篇相关条目。

从 1.0.0 继承的已验证规则范围只有 910C/A3、CANN 9.0.0 下的 `exp-tile8192`。
同一源码与二进制的 20 case 正确性、42 项边界、控制和每 case 30 对正式
Task 计时已复用并回放；缺少的候选五次 PMU 与 oracle 已完成。
最终 gate 完整回放已得到 `production_safe_gain`，实际进程以 exit code 0
结束。原发布仅验证 exp 条目及其对应的单个 canonical skill 修订。
1.1.0 仍是未封存草稿；继承的证据不替代当前 runtime 变更或新候选的验收。
原任务的 oracle 解析失败与 PMU 续跑的证据绑定失败均保持失败记录；后续
成功的 gate-only 续跑没有新增构建、PMU 采集或正式计时样本。
`norm-p-specialization`、`tile-amortization`、`sigmoid-pipeline`、
`prefetch-boundaries`、`ub-accumulator` 及其余条目继续保留条件性观察、反例
和待验证问题；`parent-baseline` 保留连续搜索的比较边界。exp 的回执不能
覆盖 mish/addcdiv，也不能证明 sigmoid 流水收益。45 次 validation 对比与
封存后全量 test 在原限域发布中均未运行。

后续改动遵循统一计时协议（同名参考，非历史原件：[unified-timing.md](../../../../../../skills/ascendc-aprof-profiling/references/unified-timing.md)），
将完整正确性、适用边界和计时绑定到实际源码与二进制；按身份和预声明时限复用
有效记录。机制证据按合法图路由或归因需要补足，历史配对控制不成为新会话的
默认步骤。旧失败回执保持失败，Wiki 中的收益不能替代当前 `timing finalize`；
缺失的 profiling 谓词保持 unknown。

> 文档适配说明：本页已修复引用；缺失材料的链接已移除，同名补充参考不代表历史原件。来源及历史回放使用[保留的证据原文](../../../../../../sources/document-originals/ce8ed8a5244bfbf75720c49ac9e6c91e2e76963afe3aad1a8e814569bfabb3a9.txt)。
