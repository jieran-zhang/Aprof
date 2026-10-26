---
schema_version: aprof.knowledge-record/v1
id: planning.flash-attention.fallback
kind: strategy
version: 1.1.0
status: active
title: FlashAttention 通用回退
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
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/fused_infer_attention_score/op_host/arch22/fia_tiling_nonquant.cpp
  original_path: attention/fused_infer_attention_score/op_host/arch22/fia_tiling_nonquant.cpp
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 544
  - 643
  sha256: sha256:ec01a86ea88d7b55f39833f9330c6da62c81b23e5e1f786f408973811618ffd6
  excerpt_sha256: sha256:dd9cb3a5b2249701a6c6757634c4002a97f0fd177c5c419346c7848ac2930745
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/fused_infer_attention_score/op_kernel/arch22/fia_kernel_nonquant.h
  original_path: attention/fused_infer_attention_score/op_kernel/arch22/fia_kernel_nonquant.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 736
  - 784
  sha256: sha256:f9329654b3966cbb62b4f23c4d6d91cd2fcc48335a58915075f9f52184f4f837
  excerpt_sha256: sha256:519bc53648d37280ed04cbf3edceff564ba374a0d0369cd613a86f36c00ac6bd
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
- attention-semantics
- verified-fallback
seed_reason: 在保留原 ID/迁移来源的基础上审读固定开源修订，补全中文算法、任务所有权、字节成本与架构边界；未做 NPU 性能训练。
parent: planning.flash-attention
references:
- planning.flash-attention.online
- planning.flash-attention.splitkv
evidence_status: source_reviewed_not_benchmarked
---

# FlashAttention 通用回退：保持注意力语义与输出所有权

## 触发与可执行支持域

workload 的 head 映射、mask/scale 顺序、分页/变长、量化、特殊值、dropout、LSE，或平台 API、容量、跨核进度尚不明确时，保留支持该域的已验证 attention 入口。C2 写出实际 fallback entry/key、它覆盖的元数据范围、与候选分支互斥条件及缺失依据；不以一个“通用 FA”名称替代可执行实现。

首选语义可审阅的 task 内 KV streaming：一个 `(batch,qHead,Qblock)` 所有者顺序计算全部有效 KV，维持稳定 `(m,l,U)` 并只写一次最终输出。已有验证基线不要求按本条机械重写；若需要分解 QK→softmax→PV 作为精度基线，要保留实际中间矩阵容量和启动成本，不能认为分解路径天然能覆盖最大 shape。

## 任务、状态与归并契约

记录 `B,Hq,Hkv,Sq_b,Sk_b,Dqk,Dv`、layout/stride 与实际长度、Q→KV 头映射、causal 对齐、prefix/page、scale/additive mask/偏置的操作顺序、输入/累加/输出 dtype、空行和特殊值行为。Dqk 是 QK 归约维，Dv 是输出宽，二者可不同。

默认 task 独占 query 输出，KV 只读共享；s2 顺序推进，不新增跨核 softmax 状态竞争。有效块使用 `m'=max(m,rowMax(X))`、`l'=exp(m−m')l+Σexp(X−m')`、`U'=exp(m−m')U+exp(X−m')V`，末尾按 oracle 归一化与输出 LSE。全 mask 行先走明确分支，避免 inf−inf；dropout、sink 和量化不能按未声明的简化数学式处理。

若已有基线本身含 Split-KV，保留其 partial 表示、同步、合并顺序与误差资格。只有完成证明后才能更换分段或把状态从未归一化改成已归一化；不能通过“回退”绕开其完成边界。

## 字节、容量和成本

`Br,Bc` 是 query/KV 块行数，`sScore,sP,sU,sStat` 为对应每元素字节，`AlignLayout` 是考虑真实物理布局、padding 与对齐的字节函数；d_e 是实际边的活跃槽数。

```text
本地U状态 = AlignLayout(Br,Dv,sU)
本地m/l状态 = 2×AlignLayout(Br,1,sStat)
QK中间 = AlignLayout(Br,Bc,sScore)；概率块 = AlignLayout(Br,Bc,sP)
流式工作区 = Σ经GM的边e d_e bytes_e + 状态溢出 + API/feature/元数据区
显式分解Score矩阵 = Σb Hq Sq_b Sk_b sScore（还须物理对齐）
若概率另存GM，再加 Σb Hq Sq_b Sk_b sP
```

L1/L0/UB 分别预算同时存活集合；外部输出、mask/dropout 转换区及可选 LSE 也保留。分解基线的 Score 可能增长为 Q×KV，超空间时选择已验证 streaming 路线，不能靠隐式覆盖或错误别名规避。scope=all 仅检索，不表示所有布局/dtype/平台能运行。

## 选型、融合边界与上下文

独立任务足够时保留 task streaming；不足时补充最长核、有效 KV 工作、合法 Br/Bc、空间和同步证据，再比较 Split-KV。增大 Bc 减少循环也增加中间区；增加核/槽深度必须重算工作区，不照搬 arch22/arch35 的固定上限或比例。

规划明确内部状态、外露 softmax/LSE、后续消费者、epilogue 和转换位置；具体 API/queue/event 由实现阶段核验。CV 融合仍可能经 GM，只有证明某条边的局部转交才删除其写读预算。

```text
if candidate domain and ownership/capacity/numerics/API proofs all hold:
    select verified candidate entry
else if fallback supports this exact metadata:
    retain fallback entry and its original task/state/merge contract
else:
    report unsupported or missing evidence; preserve known outputs/inputs
```

```cpp
// 工程分派示意；fallbackQualified 包括布局、特性、dtype 与版本支持域。
if (!candidateReady && fallbackQualified) {
    RunVerifiedAttention(inputs, outputs, semanticMetadata);
    return;
}
```

该片段不是 SDK API，未知组合不进入任一未验证入口。验证候选/回退边界、变长/分页/因果对齐、全 mask 行、特殊值、不同 Dqk/Dv、GQA 映射、LSE、重复执行与 workspace 上界；精度通过后才用统一计时口径比较全流程。固定来源包含 arch22 FA/FIA 实现依据，当前未编译/上板，A2 与 A3、950 的性能资格分别补证。
