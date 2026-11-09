# foreach_norm 的独立 partial 归约划分

> 本页保留历史协议下的观察与结论。1.1.0 新会话使用[统一计时协议](../skills/ascendc-aprof-profiling/references/unified-timing.md)，不照搬历史配对采集或置信区间门槛。

## 适用条件

在 910C/A3 上，先核对每个 TensorList 成员的独立工作量、当前 partial block
数、实际核数与每核最小 tile；只有存在未利用的独立工作时，才考虑增加
partial 分区。任务划分、归约和 workspace ownership 属于并行设计阶段。

## 证据与反例

历史 `foreach_norm` 候选把部分成员从每成员 4–5 个 block 扩到 48，相关组
观察倍率约 7.52–10.08×；20-case 等权 suite 约 4.03×。基线已有 32/42/41
个 block 的 case 只见约 1.40/1.14/1.23×；已达 48 block 且 tiling 不变的
case3/9 约为 1×。这是条件性效果，不能把低核利用率直接归咎于分区。
历史机器 verdict 为 `benchmark_specialized_gain`，且只覆盖冻结输入和环境。

来源：`l1:lesson.foreach_norm.001`、
`l1:foreach_norm-001-calibrated-search-boundaries`。

## 验证与结论

新应用须保持一般 shape 与 fallback、验证全部成员和 partial/finalize 精度，
再对新增边界 shape、原始 baseline 和直接父本做独立正式计时。未获得
`production_safe_gain` 及作用范围复核前，本页只是优化提案。

## 2026-10-14 独立复验

910C/A3（9392）、CANN 9.0.0 上，baseline 与动态 partial 候选均通过 20 个声明 case。参考计算使用历史已核验的 32 个 PyTorch CPU 线程；首次 2 线程参考的 FP32 p=3 偏差、与 FP64 复核结果均已保存，未改生成器或容差。预先声明的额外边界在 FP16 p=0 上发现 baseline 语义错误（MERE 0.1660，阈值 0.0009766；特殊值掩码也不一致）。此前五个 p 分组的 baseline/candidate 共 160 个张量检查通过；失败分组的 candidate 及剩余分组未运行。按停止规则未计时、未 profile、未晋升，不能归因于 partial 改动。机器 accuracy_failed 表示额外语义范围尚未完成验收，不能写成候选 20 个声明 case 失败。回执见 evolution.jsonl 的 norm-partials-001-independent-20261014。
