# 完整算子耗时、PMU 与输出核验范围

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
只解释可能原因，正式收益仍由兼容的全工作负载配对计时与机器 gate 裁决。
这些方法事实尚未作为 1.0.0 新技能独立复核。
