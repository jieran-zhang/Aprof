# tile 放大与每 tile 设置开销

> 本页保留历史协议下的观察与结论。1.1.0 新会话使用[统一计时协议](../skills/ascendc-aprof-profiling/references/unified-timing.md)，不照搬历史配对采集或置信区间门槛。

## 适用条件

既定并行划分内若每核有多个 tile，且源码与 profile 指向重复的搬运/标量设置
开销，可在验证 UB 容量、尾部和动态分区后尝试增大 tile。这里汇合 exp、mish
与 foreach_addcdiv_scalar 的 train 观察；不同算子的收益不可合并为一个效应。

## 证据与反例

exp 4096→8192 与 mish 2048→4096 在各自 20-case task-sum 中约有 1.18×、
1.23× 描述性 suite 观察；addcdiv 2048→4096 的六 case 搜索约 1.20×，
继续到 6144 后收益和资源占用改变。addcdiv 的 MTE2 指令次数下降近半，
case14 的绝对 MTE2 时间却只下降约 0.9%；case20 CV 约 10%，不能确认收益。
exp/mish 的 A/A、CV 或资源控制尚不充分；固定算法不等于 vector time 不变。

来源：`l1:train/exp/exp001/tile-coalescing-search-retrospective`、
`l1:mish001-tile-amortization-final`、
`l1:foreach-addcdiv-scalar-tile-coarsening-search-draft` 等。

## 验证与结论

对目标源码逐项核对 UB/队列容量、每核循环数和 tail；预先声明零/单 tile
及最大 shape 反例，运行全量正确性和独立正式计时。历史结果没有提供跨算子
通用最优 tile 或生产准入，本页不进入已发布优化 skill。

## 2026-10-14 独立复验

910C/A3（9392）、CANN 9.0.0 上，exp 的 baseline 与 8192 tile 候选各自通过全部 20 个声明 case 和 42 个额外边界（含三种 dtype、tile/分区边界及特殊值）。预先固定的 A/A 对照中，case 3 与 9 的角色偏差分别为 2.4353% 和 3.6243%，超过 2% 上限；因此在候选 A/B 计时前停止，没有正式性能或机制结论。此结果只证明当前测量未通过控制实验，不能推断 tile 优化有收益或回退。未重采样，条目继续为 draft；哈希绑定回执见 evolution.jsonl 的 exp-tile8192-20261014。
