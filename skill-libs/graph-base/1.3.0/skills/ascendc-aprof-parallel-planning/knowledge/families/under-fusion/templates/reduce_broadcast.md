---
schema_version: aprof.knowledge-record/v1
id: planning.under-fusion.reduce_broadcast
kind: template
version: 1.1.0
status: active
title: 融合与组合：归约后广播
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/ara-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ara-fullload.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 228
  sha256: sha256:621e3770b5ad87c0a852eb639fac7bfea7b7c231380d66414aa2ba06cd50a1e2
  excerpt_sha256: sha256:621e3770b5ad87c0a852eb639fac7bfea7b7c231380d66414aa2ba06cd50a1e2
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ops-design-paradigms/references/paradigms/reduction/generic/liveness-fusion.md
  original_path: ops/ops-design-paradigms/references/paradigms/reduction/generic/liveness-fusion.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 111
  sha256: sha256:08f91ab6c5846b60435aa9e70fed185f0947718604320544a99dbd8132ba8477
  excerpt_sha256: sha256:08f91ab6c5846b60435aa9e70fed185f0947718604320544a99dbd8132ba8477
learning: {}
tags:
- fusion
- composition
- reduce-broadcast
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.under-fusion
references:
- planning.reduction.fullload
- planning.reduction.split
- planning.reduction.statistics
- planning.under-fusion.fallback
evidence_status: source_reviewed_not_benchmarked
---

# 融合与组合：归约后广播

## 归约边界先于融合边界

用于同行统计供本行归一化、affine 或激活消费的计算。将形状记为 `[A1,R,A0]`：R 是归约轴，A1/A0 为保留轴；尾轴归约 A0=1，非尾轴的每个统计是一个 A0 向量元素。先按 `planning.reduction.fullload` 或 `planning.reduction.split` 确定统计状态和合并顺序，再选是否与广播输出组合。均值/方差、sum/max、Welford 或二阶矩并非同一数值算法，不能为融合随意互换。

统计与输出的任务所有权须保持一致。一个统计 owner 必须取得该 R 域全部贡献后，才可把最终状态用于任何相关输出。完整 `[R,tileA0]` 能驻留时，搬入一次，完成统计，复用未被破坏的源数据作广播。源复用型 Reduce API 可能破坏输入，若后段仍需原 x，应选择不破坏源的合法重载或保存/重读；不能只看到源码变量名仍存在就认为内容有效。

## 三种合法组合

全载路径：统计和所有输出归同一 task，统计完成后本地广播，无跨核同步。行过长但独立行足够多：每个行 owner 流式扫描 R 得最终状态，再读同一行分段输出；第二遍读换来较小 UB。行数少需 split-R：各 task 写自己的 partial state，合并 owner 按固定规则合成最终统计，完成后再将统计发布给输出分区；消费者必须等最终统计，不能消费本核 partial。可分 kernel，也可采用目标支持的核间协议；独立 kernel 的流依赖通常使边界更易证明。

如第二阶段已有输入或变换中间值保留在 workspace，比较保存它与重读/重算 x 的完整流量。融合的 kernel 数减少与是否消除 GM 中间量分别记账；跨核统计或 GM 中转仍可能存在，不能无条件宣称一次读取和零 workspace。

## 容量与精度

令 b_x/b_c/b_y 为输入/计算/输出字节宽，a 为字节对齐，`A(z)=ceil(z/a)*a`，t=tileA0，R_a 为满足当前 API 的本地 R 跨度，q 为实际队列分配份数。全载保守预算为 `U=q_x*A(R_a*t*b_x)+U_cast+A(t*b_state)+q_y*A(R_a*t*b_y)+Tmp_reduce+Tmp_post+F`；真正逐阶段复用时按同时存活项取峰值，不能盲目把各阶段 tmp 全加或全取 max。保留原 x、广播统计和输出可能同时存活，须明确这一峰值。

流式路径的主 tile 使用 r<R：`U_stream≈q_x*A(r*t*b_x)+U_state(t)+q_y*A(r*t*b_y)+Tmp+F`；split-R 的状态 workspace 是 `W=P_split*A(t*b_state)` 乘同时存活输出组，再加最终状态及同步元数据。b_state 表示每个输出统计整组状态字节宽（例如多个数值字段），不是输入 dtype 宽。二遍扫描通常读 x 两次；若用临时数据代替第二次读，应加入该数据的一次写读与额外容量。

epsilon 的位置、variance 定义、舍入、mask/填充的单位元、归约结合顺序和最终 cast 均冻结。多核固定合并顺序只使新实现可复现，不自动等于原逐项顺序。来源 ARA 全载示例的固定 tile/repeat/tmp 下界属于具体实现，不能拿来做通用 R 阈值。

```text
owner 扫描完整归约域 -> local_state
若 split-R：写 partial；等全部 partial；按声明顺序 merge；发布 final_state
保持原输入有效，或按同一 stride 重读/重算当前块
只用 final_state 广播、affine、activation；写唯一拥有的有效输出
所有读者完成后释放原输入/状态/临时区
```

对于归一化，后段可表现为 `out=(x-mean)*invStd*gamma+beta`，但源数值计算次序和 dtype 必须按接口逐步实现，不能把这个数学式当作允许重结合的许可。验证 R/A0 尾块、全相等/大偏移小方差、NaN/Inf、状态合并、输入保留和容量边界。本条通用方法 scope all，尚无当前硬件资格或性能验证。
