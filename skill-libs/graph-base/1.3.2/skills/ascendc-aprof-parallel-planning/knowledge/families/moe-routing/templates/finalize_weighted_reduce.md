---
schema_version: aprof.knowledge-record/v1
id: planning.moe-routing.finalize_weighted_reduce
kind: template
version: 1.0.0
status: active
title: MoE Finalize：token/hidden owner 的 Gather 加权归约
scope:
  platforms:
  - dav-2201
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_finalize_routing/README.md
  original_path: moe/moe_finalize_routing/README.md
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 111
  sha256: sha256:86f63ff730adb5c47fb9d3943d5b1bcbf0c77e9be9bef09a6562ebff9776251d
  excerpt_sha256: sha256:86f63ff730adb5c47fb9d3943d5b1bcbf0c77e9be9bef09a6562ebff9776251d
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_finalize_routing/docs/aclnnMoeFinalizeRouting.md
  original_path: moe/moe_finalize_routing/docs/aclnnMoeFinalizeRouting.md
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 25
  - 176
  sha256: sha256:d1262d33987e3de7c383f188fd2ba14a26d5e8d0c80c9e135868b89ff6209309
  excerpt_sha256: sha256:0dc23e648ece7696d7ad9cefd2b66aaf6f178b270cc3625a2d128edc1ab94ffd
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_finalize_routing/op_host/moe_finalize_routing_tiling.cpp
  original_path: moe/moe_finalize_routing/op_host/moe_finalize_routing_tiling.cpp
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 631
  sha256: sha256:99719b9d340b9ea251b70ae4ab566218799f5f76bcf90c89fe085d4fe1f2a7b5
  excerpt_sha256: sha256:99719b9d340b9ea251b70ae4ab566218799f5f76bcf90c89fe085d4fe1f2a7b5
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_finalize_routing/op_kernel/moe_finalize_routing_fp_db.h
  original_path: moe/moe_finalize_routing/op_kernel/moe_finalize_routing_fp_db.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 267
  - 397
  sha256: sha256:deb901b7427aae6ec4e65ac429e7e8b1852934b21ae7035b0a0fbab4bbff4ecc
  excerpt_sha256: sha256:df75554c19b8f81f6ddd0e4c488b0130e071953a3a2020f2e6f2ed40880d5e6a
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_finalize_routing/op_kernel/moe_finalize_routing_bf16.h
  original_path: moe/moe_finalize_routing/op_kernel/moe_finalize_routing_bf16.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 274
  - 419
  sha256: sha256:7842e5c84291ad0783eda0bbb52575db17b4c6139aa75ca1dc94bd74656bfa8c
  excerpt_sha256: sha256:bca6438616541c2a766e783efa910414ae11c3db7d9dd2c46bca1d3973acdda8
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_finalize_routing/op_kernel/moe_finalize_routing_fp_cuth.h
  original_path: moe/moe_finalize_routing/op_kernel/moe_finalize_routing_fp_cuth.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 457
  sha256: sha256:fbc870846fc337335f2eb571cac2668aef0add86a231be6bc664c02522500f65
  excerpt_sha256: sha256:fbc870846fc337335f2eb571cac2668aef0add86a231be6bc664c02522500f65
learning: {}
tags:
- moe
- finalize
- weighted-reduction
- gather
- ownership
seed_reason: 固定开源修订审读并以中文提炼；未做性能训练或硬件收益验证。
parent: planning.moe-routing
references:
- planning.moe-routing.route_sort_gather
- planning.indexing.gather_output_owned
- planning.reduction.split
- planning.under-fusion.reduce_broadcast
evidence_status: source_reviewed_not_benchmarked
---

# MoE 最终合并：按 token/hidden 所有权 Gather 并加权归约

## 精确映射与数值次序

设 token 数 N、hidden 宽 H、每 token 分支 K、专家数 E。FFN 输出 Z 的路由行通过一维 inverse `M[t+k*N]` 查找；token 的 scale 与 expert id 则是 `[N,K]` 的 token 主序 `S[t,k]`、`Eid[t,k]`。最终输出是：

`Y[t,h]=x1[t,h]+(x2[t,h] 若存在)+Σ_(k=0..K-1) S[t,k]*(Z[M[t+k*N],h]+bias[Eid[t,k],h])`。

本接口 finalize 的 expandedExpertIdx 是 `[N,K]`、值在 `[0,E)` 的 token/分支专家表；不能把 init 输出的“一维按专家排序列表”不经转换直接接到这里。map 的值必须落在当前 Z 的有效路由行域内；如果 init 只输出 A<L 行，必须由完整图明确丢弃/补零/重映射语义，不能 clamp 越界或按零权重擅自跳过读取（NaN/Inf 乘零未必为零）。

数学 Σ 不授权任意重结合。固定源 FP/half 分支按 k 递增，以 Add(Z,bias)→Muls(scale)→Add(acc) 计算，先把 x1 与可选 x2 合成初值；双缓冲仅预取相邻 k，仍按原次序累加。BF16 分支将相关输入转 fp32 累加，最后按 CAST_ROUND 回写 BF16。当前任务需要逐位等价时保留这一 dtype/转换/次序，不能直接换 FMA、树归约或先累加专家再统一加 bias。

## 所有权与切分

优先按 token 行分核，每个 owner 完整处理该 token 的 K 个 expert，连续写 `[H]`；行数足够且整 H 的缓冲可容纳时，批 r 个 token 共同搬入 x1/x2、scale 和 expert 元数据。Z/bias 行由路由索引取回，但输出没有跨 token 冲突，因此不需要输出原子。

H 太大时沿 hidden 切 h 片，同一 `(t,h区间)` owner 仍完整遍历 K；source map、scale、expert 可在本核多 h 片间复用。对该输出片，x1/x2/bias/Z 的 h 起点一致；本地 h_a 对齐跨度与 GM 的 H 跨度分开。切 H 只改变逐元素覆盖，不改变每个输出的 k 顺序。

K 元数据太大时可以分 k 批串行加载并保留同一 accumulator，批间继续递增 k，无需跨核归约。若为了并行度将 K 分给多个核，则产生 partial `[t,h]`，需要 workspace、固定合并和最终 owner；这是 `planning.reduction.split` 的新候选，改变结合次序须精度契约允许，x1/x2 与任何固定 bias 不得多次计入。gather 地址与重复源读取参考 `planning.indexing.gather_output_owned`，无需重造索引方法。

## 容量与重用

令 a 为字节对齐，`A(z)=ceil(z/a)*a`；b_x 为存储宽、b_c 为累加宽、b_i=4 为索引宽，δ2 表示可选 x2 是否存在，r/h 为 token 批/hidden 片，k_t 为元数据批，q_* 为真实队列分配份数。一个保守预算为：

`U=q_skip*(1+δ2)*A(r*h*b_x)+A(r*h*b_c)+q_z*A(h*b_x)+q_b*A(h*b_x)+q_meta*[A(r*k_t*b_x)+2*A(r*k_t*b_i)]+U_cast+q_out*A(r*h*b_x)+Tmp+F`。

两个 INT32 项分别是 expert id 与 map；若 map 采用标量 GM 查询而不驻留 UB，则移除该缓冲项并记录标量读/同步代价，不能容量和成本都不计。BF16 的 fp32 skip/Z/bias cast 区同时存活时逐项计 U_cast；双缓冲 q_z/q_b=2 只有实际分配并重叠预取时成立。若缓存整个 `[E,H]` bias，需要另外计 `A(E*H*b_x)`，不能因专家数小而默认容量够。

普通 token/H owner 路径不需算法级 partial workspace，但接口系统 workspace 仍按目标 API 分配；split-K 的 `W_partial=P_k*A(r*h*b_c)` 乘同时存活 token 组，另计合并及同步元数据。估算完整流量：每 token 读取 K 个 Z/bias hidden 片、scale/map/id，以及 x1/x2 一次、Y 一次；缓存 bias、重复专家/相同行和元数据批量化可能改变实际读取次数，按布局与分布计算。来源固定 K 专门展开、H 阈值只属于其分支，不转成通用门槛。

## 数据依赖与伪代码

FFN 路由输出全部就绪后才开始 finalize；若流水消费，必须有每个所需路由块的完成信号，不能仅凭 map 已就绪读取 Z。每个本地 slot 在 DMA 完成后供 Vector 使用，在 Vector/标量读者全部结束后才能预取覆盖；双缓冲的 prefetch 次序不能改变最终 k 累加顺序。

```text
每个 task 拥有 token t 和 hidden 区间 [h0,h0+h)
acc = 按规定 dtype 计算 x1[t,h] + 可选 x2[t,h]
for k 从 0 到 K-1（可分批预取，消费次序不变）:
    row = M[t+k*N]；expert = Eid[t,k]；scale = S[t,k]
    等 Z[row,h] 与 bias[expert,h] 的拷贝就绪
    tmp = 按接口 dtype/cast 计算 Z[row,h]+bias[expert,h]
    tmp = 按接口计算 tmp*scale；acc = 按接口计算 acc+tmp
按规定 cast 输出，仅写拥有的有效 h；搬出完成后回收 slot
```

本模板 scope dav-2201，固定 README 列 A3/A2 支持，但这里仅把 A3 作为实现范围，未构建或上板；数学公式可泛化，硬件/API 资格不可随之泛化。验证 map 的 `t+k*N` 与 scale/id 的 `t*K+k` 差别、重复 expert、K 奇数、可选 x2、N/H 尾部、大/小权重、NaN/Inf/±0、bf16 回写和 active 路由域。当前没有性能验证，不继承源专用分支的历史收益。
