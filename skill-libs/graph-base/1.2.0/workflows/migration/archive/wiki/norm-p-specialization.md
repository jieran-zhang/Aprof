# foreach_norm 的运行时 p 分支代数特化

> 本页保留历史协议下的观察与结论。1.1.0 新会话使用[统一计时协议](../skills/ascendc-aprof-profiling/references/unified-timing.md)，不照搬历史配对采集或置信区间门槛。

## 适用条件

仅在数学定义、精度/特殊值语义及运行时 `p` 分支确认为 1、2、4 时，考虑用
identity、乘法和平方根等替代通用 Power 链；其他 `p`、±Infinity、零与
NaN 路径必须保持独立验证。该改动发生在既定归约结构内，属于执行优化。

## 证据与反例

历史 20-case 候选中，12 个目标分支观察倍率为 2.96–3.86×；suite 约
2.05×，但正式 verdict 仍为 `benchmark_specialized_gain`。七个非目标有限
`p` case 全部出现约 0.64–1.34% 的小回退；+Infinity case 约 1×，没有执行
该特化。另一批 p=1 identity 消除实验在目标 case 获益，也记录了非目标
case 的小回退。不能把 suite 加速写成所有分支均获益。

来源：`l1:lesson.foreach_norm.002`、
`l1:foreach_norm-002-p1-identity-after-partition`。

## 验证与结论

先用独立正确性 oracle 检查所有 `p` 分支、dtype、尾部和特殊值，再测目标与
非目标分支，保留一般 fallback。只有生产安全的全域验收通过后才能提升为
skill 规则；本页保持 draft。
