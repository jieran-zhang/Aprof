# 父本改善不代表超过原始 baseline

> 本页保留历史协议下的观察与结论。1.1.0 新会话使用[统一计时协议](../../../../../../../../skill-libs/graph-base/1.3.2/skills/ascendc-aprof-profiling/references/unified-timing.md)，不照搬历史配对采集或置信区间门槛。

## 适用条件

连续候选从上一个正确性已验证、但性能未正式接受的父本继续时，同时保存
`source_parent`、`decision_basis` 和原始 baseline 身份。父子边是源码谱系，
不是收益因果边。

## 证据与反例

Level2 的 apply_adam_w001 搜索 suite 相对原始 baseline 约 0.949×；003
相对直接父本约 1.03×，但相对原始 baseline 仍约 0.993×。arg_max001 约
0.320×；后续相对父本改进，003 相对原始 baseline 仍约 0.477×。两组都只有
部分 case 的研究计时，所有正式准入均为 `not_evaluated`，不能作为生产负
reward。它们说明只看“比上一轮快”会选错整体候选。

来源：`l2:apply_adam_w001` 至 `003`、`l2:arg_max001` 至 `003` 的反馈文件。

## 验证与结论

每轮独立采候选对直接父本与原始 baseline 的实际比较；不得连乘不同时期
或不同协议的倍率。新计时结果不自动选择生产 best；生产选择另循独立契约，此页只保留决策反例。
