---
schema_version: aprof.knowledge-record/v1
id: planning.flash-attention.online
kind: template
version: 1.1.0
status: active
title: Task 并行、KV streaming 与 online softmax
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/flashattention/design.md
  original_path: ops/ascendc-tiling-design/references/flashattention/design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 634
  sha256: sha256:83ed347947ce330ed2940beb797be67fdc3cc30d60b9cf376d81711d76ab09cb
  excerpt_sha256: sha256:83ed347947ce330ed2940beb797be67fdc3cc30d60b9cf376d81711d76ab09cb
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md
  original_path: ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 155
  sha256: sha256:ea3be814234904a2d8a4a3b99847aec00c849f3fb3ce2647390a3dce0a734ba1
  excerpt_sha256: sha256:ea3be814234904a2d8a4a3b99847aec00c849f3fb3ce2647390a3dce0a734ba1
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/community/ops/ascendc-evolution-strategies/references/tiling-design/flashattention/design/shape.md
  original_path: community/ops/ascendc-evolution-strategies/references/tiling-design/flashattention/design/shape.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 271
  sha256: sha256:d7aba4c9f89b0422b630646f922fbe4705ff5329645e7f3bc85829a3b4c23a0b
  excerpt_sha256: sha256:d7aba4c9f89b0422b630646f922fbe4705ff5329645e7f3bc85829a3b4c23a0b
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/community/ops/ascendc-evolution-strategies/references/tiling-design/flashattention/design/resources.md
  original_path: community/ops/ascendc-evolution-strategies/references/tiling-design/flashattention/design/resources.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 339
  sha256: sha256:36c29cd0eb871d5357a461228ea4e7431caf25f889fb3ae5c1ac7753fcfe5f0e
  excerpt_sha256: sha256:36c29cd0eb871d5357a461228ea4e7431caf25f889fb3ae5c1ac7753fcfe5f0e
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/fused_infer_attention_score/op_host/arch22/fia_tiling_nonquant.cpp
  original_path: attention/fused_infer_attention_score/op_host/arch22/fia_tiling_nonquant.cpp
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 544
  - 643
  sha256: sha256:ec01a86ea88d7b55f39833f9330c6da62c81b23e5e1f786f408973811618ffd6
  excerpt_sha256: sha256:dd9cb3a5b2249701a6c6757634c4002a97f0fd177c5c419346c7848ac2930745
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/flash_attention_score/op_host/arch22/flash_attention_score_tiling_general.cpp
  original_path: attention/flash_attention_score/op_host/arch22/flash_attention_score_tiling_general.cpp
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 2203
  - 2260
  sha256: sha256:31e42040e66cdc7fa6f4c68ba5e573d36cb3e07d9a7d837c0353154816114db9
  excerpt_sha256: sha256:a262f253576476da17f9c8869ffc06d7a2486f7ced5332a65530f2d606b42f7b
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/flash_attention_score/op_host/arch22/flash_attention_score_tiling_general.cpp
  original_path: attention/flash_attention_score/op_host/arch22/flash_attention_score_tiling_general.cpp
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 2764
  - 2775
  sha256: sha256:31e42040e66cdc7fa6f4c68ba5e573d36cb3e07d9a7d837c0353154816114db9
  excerpt_sha256: sha256:1290b17de76e9cec96c8cd1142cc48b8e7895819058a1281f45cde162cbe7eb4
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/flash_attention_score/op_kernel/arch22/flash_attention_score_s1s2_bn2gs1.h
  original_path: attention/flash_attention_score/op_kernel/arch22/flash_attention_score_s1s2_bn2gs1.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1937
  - 2018
  sha256: sha256:e739820e172fa26ae73c802ad8ca2ceabb1080ee9dd1e3c2c8226d08f7d6e34a
  excerpt_sha256: sha256:2d6dc0843b295d0b89a4e42594ac71d7b94bc0469440a8c978dea3198210d3a0
learning: {}
tags:
- arch22-source
- fusion-boundary
- online-softmax
- task-state-ownership
seed_reason: 在保留原 ID/迁移来源的基础上审读固定开源修订，补全中文算法、任务所有权、字节成本与架构边界；未做 NPU 性能训练。
parent: planning.flash-attention
references:
- planning.flash-attention.fallback
- planning.flash-attention.splitkv
evidence_status: source_reviewed_not_benchmarked
---

# Task 并行、KV streaming 与在线 softmax

## 问题语义与适用域

对每个 query 行计算 `softmax(scale×QKᵀ + additive_bias + mask) V`。输入冻结 batch、query 头数 Hq、KV 头数 Hkv、各 batch 的 Q/KV 有效长度、Q/K 的宽度 Dqk、V/输出宽度 Dv、layout/stride、head 映射、mask 对齐、scale、dropout、量化及输出/LSE 约定。GQA/MQA 的共享 KV 通过明确 head 映射实现，不能把 Hq 和 Hkv 混为同一维；MLA 等变体有自己的投影、维度和缓存语义，不凭此基础公式直接覆盖。

默认沿 `(batch,query-head,Qblock)` 建互斥输出任务，任务内按合法 KV 块顺序流式处理。先利用 batch/head/Q 独立性；仅当合法任务分块仍欠并行且 KV 长，才比较 `planning.flash-attention.splitkv`。基础任务数为 `T=Σb Hq×ceil(Sq_b/Br)`，其中 Sq_b 是 batch b 的有效 Q 长度；若将 GQA 组内 Q/head 合并成任务，则按实际映射重算 T。每 task 还需估计其实际执行的 KV 轮数 J_t；不跳块时粗略乘加量为 `2×validQ_t×processedKV_t×(Dqk+Dv)`。稀疏/causal 的有效键数不等于实际执行元素数，只有已跳过的计算块才从工作模型扣除。

## 稳定递推、状态与所有权

对一个 Br 行 Qblock，状态为行最大值 m、非归一化行和 l、非归一化输出累加矩阵 U。初始化 `m=-∞,l=0,U=0`。当前有效块分数 X 已包含 scale/bias/mask；逐行定义：

```text
mNew = max(m, rowMax(X))
alpha = exp(m − mNew)
Pblock = exp(X − mNew)
lNew = alpha l + rowSum(Pblock)
UNew = alpha U + Pblock Vblock
最终 O = U/l；若需要 LSE，LSE = m + log(l)
```

这里 Pblock 是局部指数权重，并非已除全局 l 的概率。全 mask/空块显式走零贡献分支：不能计算 `exp(-∞−(-∞))`。全行无有效键、NaN/Inf、sink、dropout 的输出和 LSE 遵循 oracle；dropout 若作用在概率上，分母和输出分子通常承担不同语义，不能把 Pblock 无条件替换成含 dropout 后还拿来累计 l。跨 tile 的随机数映射也要保持。

一个 task 独占 Q 输出和 m/l/U；KV 只读可复用。s2 默认 task 内顺序推进，每次更新必须等待前一状态；多个并发 task 的状态槽以 task 身份索引，不能用 KV loop 取模覆盖尚未结束的另一个 task。QK→softmax→PV→rescale 的阶段槽、跨 task 状态槽、KV 预取槽分别定义，数量相同也不能混作一个常量。

## 分层字节与 GM 工作区

令 `Br,Bc` 为 Q/KV tile 行数，`Dqa,Dva` 为相应物理对齐宽度；`sQ,sK,sV,sScore,sP,sU,sStat` 为各表示每元素字节；`d_e` 是边 e 的同时活跃槽数；`AlignLayout` 返回考虑 stride、padding、格式的实际字节。

```text
Qtile = AlignLayout(Br,Dqa,sQ)
Ktile = AlignLayout(Bc,Dqa,sK)；Vtile = AlignLayout(Bc,Dva,sV)
Score = AlignLayout(Br,Bc,sScore)；P = AlignLayout(Br,Bc,sP)
Ustate = AlignLayout(Br,Dva,sU)；统计状态 = 2×AlignLayout(Br,1,sStat)
Wstage = Σ实际经GM的边e d_e × bytes_e
Wtotal = Wstage + Wspill_state + Wmask/dropout/transform + Wapi + Wmetadata
```

各层容量按本层同时存活区单独求和，并包含 softmax 临时区、mask、广播临时数据和 L0 累加区。QK 的归约维是 Dqk，PV 的归约维是当前 Bc，PV 输出维是 Dv；三者不能共用一个 D 假设。QK/PV 的 L0 K/N 分块需要分别预算。

若 Br×Dv 状态可合法驻留，保留本地 U 以减少反复读写；若不够，可缩 Br 或按行/Dv chunk 流式读写状态。若前 J−1 个 KV 轮结束时写 U、下轮读回，而末轮直接归一化写 O，则附加状态请求近似 `2×(J−1)×Ustate`，J 为有效 KV 轮数；末轮 U 另存再读、统计状态落 GM 或 padding 时另计实际字节。不能一律要求 U 上 GM，也不能一律声称可常驻。

arch22 FIA host 实际显式预算 MM1、Vec1、MM2、Vec2 workspace；FA host 也有 bmm 中间区。因此 Cube/Vector 融合不是“全部边消除 GM”的证明。若某边确实转为局部通路，才从模型中删除对应 workspace/请求，同时加入目标可用本地容量与同步约束。

## 参数、选型与融合边界

联合搜索 Br/Bc、Dqk 归约步长、Dv chunk、任务顺序、KV page 对齐、状态驻留/溢出、各级槽深度和逻辑所有者数。较大 Bc 减少循环和递推次数，也放大分数/概率中间区；较小 Br 增加独立任务但可能增加 KV 重读。容量、最长核、尾块、page 搬运和 workspace 共同判断，不复制来源的固定 tile、比例或上限。

分页 KV 的逻辑连续块未必物理连续；按 page 边界拆实际搬运或证明跨页访问有效。TND/NTD、左 padding、causal/band、prefix、压缩 mask 等特性需进入 workload 域和地址模型。融合在规划阶段决定哪些数据仅供内部消费、哪段状态跨 KV 轮保存、输出/LSE/softmax 是否外露；实现阶段再选择混合入口、事件和 API，不能删掉被外部消费者需要的张量。

## 伪代码与上下文片段

```text
for task=(batch,qHead,qBlock) assigned to owner:
    map qHead to kvHead; derive valid query rows and KV/mask range
    m=-inf; l=0; U=0
    for each valid KV chunk in semantic order:
        X = ApplyDeclaredScoreTransform(Q*K^T, scale, bias, mask)
        skip zero-contribution rows/blocks without inf-inf
        update m/l and rescale old U; compute block PV; accumulate U
    finalize O and optional LSE using the oracle's empty-row behavior
```

```cpp
// 单行 U 的递推算术；alpha 已在有效行上由稳定 max 更新得到。
AscendC::Muls(oldULocal, oldULocal, alpha, validDv);
AscendC::Add(newULocal, oldULocal, pvLocal, validDv);
// l 的递推另行完成，最后一次归一化才输出。
```

片段省略 QK/PV、API 临时区、队列与完成依赖，不能替代完整 kernel。实际 `SoftmaxFlashV2` 首轮/后续轮参数、reduction/broadcast 形式依 SDK 与目标 kernel 核验；C2 冻结语义顺序和所有权，C3 不得通过局部 API 切换改变它们。

## 验证与回退

覆盖 prefill/decode、GQA 头映射、变长/分页、Q/KV/D 尾块、scale/mask 操作顺序、causal 对齐、全 mask 行、prefix、LSE、dropout 和量化所声明子域，以及多 task 交错和重复调用。检查状态槽不会串 task、每输出恰一次写回、workspace 上界随核数/tile/feature 同步更新。

容量/语义/API 资格不明确，回到支持该 workload 的已验证 attention 入口；必要时保留分解基线并计显式分数矩阵空间。资料包含实际 arch22 FA/FIA host/kernel，其他平台只作为规划候选，不继承其 API 或性能资格。当前未编译、未上板，无固定收益与通用最佳参数。
