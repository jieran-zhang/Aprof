# UB 累加器消除逐 tile scalar 反馈的反例

## 适用条件

已有逐 tile `GetValue` 反馈、可安全保持 FP32 UB running buffer 时，这是一项
可提出但需验证的执行层干预；INF 等未走该分支的模式不能当作机制正例。

## 证据与反例

foreach_norm 历史候选把 GENERAL/ZERO 的 sum 留在 UB。20-case suite 观察
约 1.0203×，正式 95% LCB 约 1.0196×，低于既定 1.03 门槛，机器 verdict
为 `attribution_uncertain`。FP32 case 的观察收益约 1.2–1.7%，FP16/BF16
约 2.4–2.6%；旧 scalar time 反而增加，与原先预测相反。INF case 虽略快，
其路径仍保留原 scalar max/GetValue，不能证明本干预的机制。

来源：`l1:lesson.foreach_norm.003`。

## 验证与结论

保留这个未达收益条件的实验，防止把低于正式门槛的小幅观察写成强规则。
新候选必须另做容量、正确性、直接父本和全量正式计时。
