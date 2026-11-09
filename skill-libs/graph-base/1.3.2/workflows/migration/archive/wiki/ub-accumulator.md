# UB 累加器消除逐 tile scalar 反馈的反例

> 本页保留历史协议下的观察与结论。1.1.0 新会话使用统一计时协议（同名参考，非历史原件：[unified-timing.md](../../../../skills/ascendc-aprof-profiling/references/unified-timing.md)），不照搬历史配对采集或置信区间门槛。

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

> 文档适配说明：本页已修复引用；缺失材料的链接已移除，同名补充参考不代表历史原件。来源及历史回放使用[保留的证据原文](../../../../sources/document-originals/792df6e0d5f474660e4f29743f32a703cf794f795dc013d3e684f0d6bb876e3e.txt)。
