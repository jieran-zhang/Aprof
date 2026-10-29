# 一 tile 预取的收益边界

> 本页保留历史协议下的观察与结论。1.1.0 新会话使用统一计时协议（同名参考，非历史原件：[unified-timing.md](../../../../skills/ascendc-aprof-profiling/references/unified-timing.md)），不照搬历史配对采集或置信区间门槛。

## 适用条件

在多 tile、存在可隐藏的搬运等待、双槽容量与同步合法时，才考虑在当前
Compute 前发出下一 tile 的 CopyIn。单 tile、无等待、较高 UB 占用或
额外 scalar 控制成本可能抵消收益。

## 证据与反例

masked_scale 的四个 PMU sentinel 的 MTE2 stall 均下降，但 20-case 主 task
时间效果异质，case11 有明显点估计回退，case20 stall 下降而主时间点估计
回退。exp 的预取候选相对原始 baseline 仍较快，但它继承了父本 tile 放大；
相对直接父本 case8 小回退，13 个 case/config 点估计低于 1。原始 baseline
收益不能推算预取的增量收益，历史 A/A 与精度限制仍在。

来源：`l1:masked_scale001-input-prefetch-wait-reduction-mixed-timing`、
`l1:train/exp/exp002_new/input-prefetch-search-retrospective`。

## 验证与结论

每次分别测候选对直接父本和对原始 baseline；不把 PMU stall 或历史倍率
乘积当成正式 task 时间。补齐全量正确性、容量、队列顺序和独立正式计时前，
不得晋升为默认预取规则。

## 2026-10-14 独立复验

910C/A3、CANN 9.0.0 上，masked_scale 原始 baseline 与预取候选各通过声明 20 case。预先固定的第一项额外边界使用 shape=[33]、FP16 x=65504、int8 mask=2、scale=0.5：原有 PyTorch oracle 的中间 FP16 乘法溢出，期望 33 个 +Inf；baseline 在 FP32 中计算，实际为 33 个 65504，特殊值掩码检查失败。原始算术及 verifier 均未修改。

这是 baseline 已存在的语义差异，不能归因于预取。按计划停止，候选在该边界及其余 60 个额外边界尚未运行；没有 A/A、候选计时或 PMU 结论。未删除反例或缩窄范围，未晋升。完整 trace、原始诊断、执行成本和哈希见 evolution.jsonl 对应的 masked_scale 独立提案。

> 文档适配说明：本页已修复引用；缺失材料的链接已移除，同名补充参考不代表历史原件。来源及历史回放使用[保留的证据原文](../../../../sources/document-originals/24e01b7a1c612ea1f5323fce9e5e54c4a2ef6aaa768df6748013c2981152d997.txt)。
