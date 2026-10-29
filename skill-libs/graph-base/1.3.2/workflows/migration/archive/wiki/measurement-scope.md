# 完整算子耗时、PMU 与输出核验范围

> 本页保留历史协议下的观察与结论。1.1.0 新会话使用统一计时协议（同名参考，非历史原件：[unified-timing.md](../../../../skills/ascendc-aprof-profiling/references/unified-timing.md)），不照搬历史配对采集或置信区间门槛。

## 适用条件

一个算子含多个 TensorList 成员、partial/finalize kernel，或 profile 指标与
端到端/完整调用计时不一致时，先写明度量边界。原生 task sum、设备 event、
PMU core time、进程墙钟、host 间隙和完整调用延迟是不同量。

## 证据与反例

foreach_norm 必须计入全部列表成员、partial 和 finalize；只比较一个同名
kernel 会漏掉完整工作。历史方法记录中，1200 次 context session 并不等于
1200 份被保留并核验的输出，实际只留了 40 个最终输出。masked_scale case20
的 PMU 时间约 45.35→36.78 μs、MTE2 stall 约 37.38→28.51 μs，主 task
时间点估计却回退；stall 减少不能替代正式延迟收益。旧采集器的输入 manifest
修订也只修正证据绑定，不产生新候选收益。

来源：`l1:lesson.method.timing_output_scope`、
`l1:masked_scale001-input-prefetch-wait-reduction-mixed-timing`、
`l1:feedback-collector-native-input-manifest-correction` 等。

## 验证与结论

报告每个指标的原始单位、采集协议、完整调用覆盖和实际输出核验数；机制 profile
只解释可能原因，当前性能结果由统一协议下完整 workload 的 timing finalize 判定，历史收益按原配对协议解释。
这些方法事实尚未作为 1.0.0 新技能独立复核。

> 文档适配说明：本页已修复引用；缺失材料的链接已移除，同名补充参考不代表历史原件。来源及历史回放使用[保留的证据原文](../../../../sources/document-originals/38ecd3ac99d0ec7c488a2e6b63c3855054e303cc768317cc785cd212331e8125.txt)。
