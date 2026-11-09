# 中位数探索稳定性协议 v2

统计协议：`median_stability_exploration_v2`；异常策略：`bounded_outlier_v2`。这是1.3.0的**试用探索规则**，阈值不是跨设备通用标准。原始采集仍为 `single_role_l2_clean_task_v1`：每case／实现新进程、5次预热、20次逐轮清L2的完整调用。PMU机制证据的5% CV要求是另一契约，不随本页放宽。

## 一次异常识别，分别报告轮内质量和中位数

从原始20值计算中位数m、MAD=`median(|x−m|)`；只检测一轮：

`|x−m| > max(0.10×m, 3×1.482602218505602×MAD)`。

MAD系数沿用旧实现精度，约为4.4478。快慢两侧对称，恰好等于阈值不标异常。异常≤4时一次剔除全部标记项，保留至少16值；异常>4时一项也不剔除。不得重新检测剩余值、只删最慢点或逐次删除直到通过。

每个窗口完整报告：原始20值、原始／处理后中位数、原始／处理后样本CV、MAD及阈值、异常数量与索引、剔除索引、保留数、剔除引起的中位数变化。CV=`sample_stddev / mean`，不是中位数标准误。

- 异常≤4且处理后CV≤10%：`within_window_acceptable`，只说明达到本试用轮内规则。
- 超限：`variable_review_required`（波动较大／需复核），保留可解释的收益点估计，不直接写成“性能失败”。4/20占20%，不能默认全是设备外部噪声。
- 缺Task、错误stream、未完整20次、非正／非有限值、错误身份、正确性失败等仍拒绝；中位数稳不能修复这些缺陷。

## 跨窗口：A、B各自检查

只比较同一source、binary、case/workload、输入、硬件、工具链、collector、kernel序列、清L2口径的独立采集。首次与每次复验均保留；计算原始中位数漂移：

`drift_j = |raw_median_j − raw_median_first| / raw_median_first`。

全部已执行复验分别对首测计算，不只比较首末；取最大值作状态说明：≤3%为`stable_evidence`，>3%且≤5%为`caution`，>5%为`uncertain`。没有复验是`not_measured`，不能填写0或宣称跨窗口稳定。A/B比值保持不变也不能覆盖两侧都漂移的事实。

复验仅在测前明确的次数和外部任务预算内进行。声明`max_retests`是每实现、每case的上限，不授权用完额度、不自动追加采集。若执行复验，必须提交原首测及全部已执行窗口，按时间排列；**最后已执行窗口无条件作点估计**，不选择最快、最低CV或刚好过门槛的窗口。复验原生capture_id不得重复，重包装同一个native窗口不能制造稳定性证据。未报告的外部采集无法由运行时凭空发现，协调者仍须完整登记尝试。

`replication_recommended`只是预算内提示：仅在尚无复验且轮内需复核或恰在工程门槛附近时提示；普通单窗口缺漂移信息不会自动建议全量再采。已有不一致窗口交复核，不重复采到通过；预算为0时不产生追加采集建议。该字段不授予新的次数或停止权限。

## 稳定性与收益分别决定

工程要求保持：逐case中位数比的等权GM≥1.03，任一case回归≤3%，正确性及完整调用不放宽。HAP目标、Action—P/O正式交接分别报告；计时协议不自动授予其通过。

结果包含三层信息：

1. `engineering_assessment`：固定最后窗口、处理后中位数的工程点估计，可能达到或未达到原收益要求；不是因果归因。
2. 原始值敏感性：同时计算原始中位数的工程判断和每case回归。剔除若改变GM达标或任何case的3%回归门槛结论，保持需复核。保留原始/处理后的逐case比值，不能只报告有利结果。
3. `timing_quality`与最终`verdict`：任一侧跨窗口漂移>5%保持不确定；轮内超限即使中位数稳定，也只进入`further_benefit_review_possible`，不自动accepted。正常轮内质量与已有窗口一致时才进一步给出工程结论；没有跨窗口证据仍明确披露单窗口限制。

对于已有多个窗口，额外展示每case原始／处理后窗口中位数的观测范围：用min(A)/max(B)及max(A)/min(B)重算GM和最坏case。它是**选择对已观测变化的敏感性**，不是真实同时发生的A/B配对，也不是置信区间。范围跨工程门槛时需复核；≤3%的窗口漂移不能自动证明1%～3%的收益。约3%门槛收益若缺双方稳定窗口，也不自动accepted。3%～5%的漂移可谨慎解释，保留该状态及敏感性，不额外假装已获稳定保证。

`inconclusive`不表示候选变慢；应同时说明点估计、真实负面证据和未解不确定性。明确回退不能被阈值放宽抹去。缺少可信耗时或窗口不能通过重命名unknown、KEEP或收益标签解决。

## 版本、调用与兼容

测前declaration使用schema_version=3，绑定完整case及原有复用时限，增加：

```json
{
  "stability_protocol": "median_stability_exploration_v2",
  "stability_policy": "bounded_outlier_v2",
  "replication_policy": {"max_retests": 1, "estimator": "last_executed_window"}
}
```

上例1是明确预声明的示例额度，应服从外部任务范围。baseline assumed仍须绑定原source/binary，v3声明可使用原有baseline_trust。

比较请求使用schema_version=2，采集protocol仍为`single_role_l2_clean_task_v1`，增加`stability_protocol`及`replications: {"baseline": [], "candidate": []}`。原`baseline_captures`／`candidate_captures`必须包含完整首测集合；复验列表只放实际执行的追加capture引用。正确性、路径根、hash、来源、复用有效期和A/B间隔继续校验，重复、乱序、缺首测、身份变化或超额度被拒绝。

沿用`tools/aprofctl timing finalize`及按需`timing verify`，不增加日常必跑工具。新结果schema_version=2，记录统计协议、全部窗口和decision_hash。新schema分别为[声明v3](../../../schemas/unified-timing-declaration-v3.schema.json)、[请求v2](../../../schemas/unified-timing-request-v2.schema.json)、[结果v2](../../../schemas/unified-timing-result-v2.schema.json)。旧声明／请求／结果schema及`bounded_outlier_v1`保持原字节和判定；不能事后重写声明把历史capture升级为新协议，旧handoff/v2也不接收新稳定性结果。

独立数据尚未验证本试用协议。既有数据的[离线对照](../../../workflows/references/development-records.md#median-timing-130)只做阈值及窗口敏感性分析，不能追认历史候选、HAP或未准入的完整交接。
