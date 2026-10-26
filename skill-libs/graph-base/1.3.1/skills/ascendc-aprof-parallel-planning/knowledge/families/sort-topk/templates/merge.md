---
schema_version: aprof.knowledge-record/v1
id: planning.sort-topk.merge
kind: template
version: 1.1.0
status: active
title: Sort/TopK 分块与层次归并
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/sort/alg-two-level-mrgsort.md
  original_path: ops/ascendc-tiling-design/references/sort/alg-two-level-mrgsort.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 681
  sha256: sha256:031b9829393ccd4f83ca8cd19d8a6ce47d42274e2975c247d487e9d87edcdcf6
  excerpt_sha256: sha256:031b9829393ccd4f83ca8cd19d8a6ce47d42274e2975c247d487e9d87edcdcf6
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/sort/patterns.md
  original_path: ops/ascendc-tiling-design/references/sort/patterns.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 67
  - 200
  sha256: sha256:915e5ca3f7c163d43b7c6d7c592ab8d45edd0776c6864a89bd8b0758395e2851
  excerpt_sha256: sha256:4b3f156e4294fdb7a3b6f22a44970e81d4507704d9aa55d004b515d1e248d05f
learning: {}
tags:
- sort
- topk
- merge
- ownership
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.sort-topk
references:
- planning.sort-topk.fallback
- planning.moe-routing.route_sort_gather
evidence_status: source_reviewed_not_benchmarked
---

# Sort/TopK 分块与层次归并

## 适用域与先决语义

用于完整排序或可证明剪枝的 TopK。冻结每行长度 N、K、升降序、索引基准、相等键次序、稳定性及 NaN/±0 规则。value 与原 index 始终作为一对移动；局部 index 要加该 tile 的原始起点。通用分治方法适用于各平台，但这里的 Sort/Concat/MrgSort 调用和 proposal 表示只来自固定修订的源码审读，尚未取得当前 SoC/SDK 的可执行性或性能资格。

先确定比较关系，再选硬件排序路径。若需要稳定顺序，比较关系必须等价于 `(key, original_index)` 的约定顺序；仅因算法名叫归并排序，不能推断某个 API 对相等值稳定。int64 键、较大整数转 fp32、NaN、自定义次序均不可未经证明套用 fp32 proposal。padding 也必须有独立有效位或严格位于所有合法键之后的哨兵，不能让 padding 抢走合法极值。

## 分区、所有权与阶段

令 T 为容量允许的局部排序长度，P 为可用核数，Q=ceil(N/T) 为 tile 数，f 为当前 API 合法归并路数。Q=1 时单核排序；1<Q≤P 时各核至多排序一块后跨核归并；Q>P 时各核先把自己的多块归成一条 run，再跨核归并。核内归并没有跨核依赖，不必加入全核 barrier。跨核每轮把至多 f 条有序 run 合成一条：输出 run 区间唯一 owner，输入只读。尾 run 长度必须用实际元素数递推，不能以“满块长度×路数”覆盖尾部。

run 超过 UB 时采用流式归并：保存各输入 run 的已消费位置，每次搬入各路当前窗口，输出合法的一段后，只前移 API 实际消费的元素数；未消费尾部继续参与下一轮。当前 API 的 suspend/resume、每路长度和消费计数必须核验，不可每窗口独立排序后直接拼接。最后一轮 Extract value/index，按原输出 dtype 转换并写出。

跨核生产结果完成后才发布就绪；消费者读完后才复用输入 workspace。可以用独立 kernel 阶段建立依赖，也可以用经平台支持的核间同步。若使用全核 barrier，退役核仍需以相同次数/顺序参加，不能在某轮提前 return；不能把同一核里的 PipeBarrier 当作全设备完成事件。

## 容量与代价

所有量以下均为字节。`A(n,a)=ceil(n/a)*a` 为按 a 字节对齐；b_v 为输入值字节宽，b_k 为排序键宽，b_i 为索引宽，b_p 为 API proposal 宽，U 为扣除系统和固定状态后的可用 UB，q_* 为实际分配份数。

`U_sort(T)=q_v*A(T*b_v,a)+q_k*A(T*b_k,a)+q_i*A(T*b_i,a)+q_p*A(T*b_p,a)+TmpConcat(T)+TmpSort(T)+F`。不需要独立 cast 时去掉对应项；只有生命周期确实不重叠才共享地址。TmpConcat/TmpSort 由目标 SDK 的查询接口获得，不能用每元素常数代替。

`U_merge=f*A(w*b_p,a)+A(o*b_p,a)+TmpMerge(f,w,o)+F_merge≤U`，w/o 为输入窗口/输出段长度。workspace 一般需两代 run 的读写隔离：`W≈2*A(N*b_p,a)+W_meta+W_sync`，若原地或单代方案有合法覆盖证明才扣减。层数约为 `ceil(log_f(Q))`；每轮完整归并都需读写该轮实际保留的 proposal，成本还包含重复窗口搬运、索引生成、cast 和最后 Extract。上游固定 tile、四路、API 32 元素粒度和 tmp 示例必须绑定其具体重载，不能变成全平台阈值。

## TopK 的剪枝证明与替代

若所有阶段使用同一全序，某个 run 的第 K 名之后至少已有 K 个本 run 元素排在它前面，因此它不可能进入全局前 K；每 run 保留 min(K,run_len) 才合法。相等值次序/NaN 关系不一致时该证明失效。K=N 时保留全部 N 项，输出是否要求有序仍按接口契约处理；K>N 必须遵循接口对越界参数的报错或其他明确行为，不能擅自钳制成完整排序。K 很小可比较专用选择或逐级候选合并；N 小用单核可免 workspace/同步；特殊比较器或 dtype 不支持时用 `planning.sort-topk.fallback`。路由重排所需的是排序与映射组合，见 `planning.moe-routing.route_sort_gather`。

```text
冻结 compare(key,index), padding, 输出 cast
每核：排序拥有的 tiles，保存实际长度与原始 index
每核：流式归并本核 runs（不加跨核同步）
每轮跨核：等待输入 runs 完成；唯一 owner 归并到另一代 workspace
             等全部消费者完成后交换两代地址
最后一轮：保留合法 K 或完整 N；Extract；按输出语义写回
```

验证空/单元素、K=0/K=N/越界 K 的接口行为、非整 tile/f 路尾部、相等键跨核、NaN/±0、索引最大值和容量上限。当前仅来源审读，没有 NPU 性能验证；C2 固定比较关系、输出 owner、剪枝证明和轮间依赖，C3 再选择合法 API 与 tmp 大小。
