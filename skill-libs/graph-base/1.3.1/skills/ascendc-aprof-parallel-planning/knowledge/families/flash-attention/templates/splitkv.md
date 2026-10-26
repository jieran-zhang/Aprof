---
schema_version: aprof.knowledge-record/v1
id: planning.flash-attention.splitkv
kind: template
version: 1.1.0
status: active
title: Decode split-KV 与稳定合并
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
- split-kv
- stable-merge
- unnormalized-partials
seed_reason: 在保留原 ID/迁移来源的基础上审读固定开源修订，补全中文算法、任务所有权、字节成本与架构边界；未做 NPU 性能训练。
parent: planning.flash-attention
references:
- planning.flash-attention.fallback
- planning.flash-attention.online
evidence_status: source_reviewed_not_benchmarked
---

# Decode Split-KV：独立局部状态与稳定合并

## 适用问题与选择门禁

默认 query task 独立性不足、KV 较长且有效注意力工作可分片时，沿 KV 轴为同一个 query task 提供更多生产者。Decode 的短 Q 是常见触发形态，但不是按 Sq=1 或某个 Sk 固定数字机械决定；应先计算合法 Q/head/batch 分块的实际任务数与目标逻辑所有者数，再比较并行收益、部分状态流量、跨核同步及最终合并。

workload 先明确 B/Hq/Hkv、Dqk/Dv、有效 Q/KV 长度、head 映射、paged/变长布局、mask/causal 对齐、scale/bias、sink/dropout、量化和可选 LSE。Split-KV 是同一个 attention 的并行技术，不会自动把 MHA 改成 GQA 或改变 KV cache 语义；未具备该 workload 对应 partial/merge 路径时，回到 task 内顺序 streaming。

## 局部状态表示与合并公式

每 task 的有效 KV 域划分成互斥区间 Ki，覆盖一次且无遗漏。每生产者按在线递推计算行状态 `(mi,li,Ui)`，其中 `Ui=Σk∈Ki exp(xk−mi)Vk` **未归一化**，`li=Σk∈Ki exp(xk−mi)`。对每行非空 partial 集合 E：

```text
M = max(i∈E) mi
wi = exp(mi−M)
L = Σ(i∈E) wi li
U = Σ(i∈E) wi Ui
O = U/L；可选LSE = M + log(L)
```

若 partial 保存的已经是 `Oi=Ui/li`，则分子必须使用 `wi li Oi`；不能把归一化 partial 当未归一化 Ui。表示、dtype、是否含量化/缩放和 merge 次序必须写进规划及元数据。树状/线性合并数学上可等价，浮点舍入与确定性仍需单独验收。

空 split 或全 mask 行用 `(m=-∞,l=0,U=0)` 加有效标识（或 oracle 允许的等价约定）；合并跳过无贡献项，不算 `exp(-∞−(-∞))`。若 E 为空或 L 无有效分母，按 oracle 返回。NaN/Inf 和 sink 项不能简单按 l=0 判断“应跳过”；sink 若作为全局额外 softmax 项，只能计一次或采用已证明的独立贡献表示。dropout 的分母、随机数索引和输出分子也须保持原定义。

## 任务、槽位与同步

生产任务键 `(call,batch,qHead,qBlock,kvSplit)` 唯一，各自独占 partial 槽；最终所有者按 `(batch,qHead,qBlock)` 读齐参与 split，执行一次归一化、post-quant/epilogue 与输出写回。不同 split 绝不能直接竞争更新同一 m/l/U，因为 max 变化要求整套状态同时重标度。

若分块跨页，逻辑 KV 区间与物理搬运段分别描述；空片仍要满足协议的完成/退出要求。消费者依赖所有实际生产者完成且写入可见，可用目标已验证跨核协议或分 kernel 边界。arch22 FIA `FlashDecode` 中实际有同步后 combine，并管理 decode 参数与事件；不等同于任意 kernel 加一条 SyncAll 即可合并。使用 barrier 时列出包括空闲核的参与集合，核数/入口模式变更重新验证进度。

## 字节、容量与成本

令 Q 个 query task，每 task 允许 `S_t` 个 KV 片；`Br_t` 为有效 Q 行数，`Ar_t,Ad_t` 为 partial 存储对齐后的行/输出宽；`sU,sM,sL` 为对应每元素字节，`Am_t,Al_t` 为行统计实际对齐存储长度。

```text
Wpartial = Σt S_t × (Ar_t Ad_t sU + Am_t sM + Al_t sL)
Wtotal = Wpartial + Wnormal_stage + Wapi + Wmetadata + 其他峰值存活区
额外partial写读 ≈ 2 Wpartial
合并输出分子工作 ≈ Σt (S_t−1) Br_t Dv_t 次加权累加
收益门禁: Tstream_critical − Tsplit_compute_critical
          > Tpartial_IO + Tstable_merge + Tsync + Tlaunch_delta
```

必须把正常 QK/softmax/PV 中间 workspace 与 split partial 区同时计入；tile 或核数改变两者都需重算。`sU/sM/sL` 来自实际存储类型，不默认全部 FP32 或与输入同类型。若按每核首/尾归并碎片而非每 `(task,split)` 存储，按真实 fragment 数和对齐算空间，不能沿用本简式的 S_t。row-stat 行对齐可能使统计存储大于两个紧凑标量。

## 参数与替代方案

搜索 S_t、KV 边界/合法粒度、Bc、Br、partial 类型、merge 分块与树、组内消费者数、分 kernel/同 kernel 协议。最大非空片数受有效 KV、mask/page 和最小合法工作块约束；不为填核制造大量空片。K/V 不同片要共享 Q，新增 Q 重读与缓存行为也计入模型。

若 Q 独立任务够多，先用 task streaming；若只是 workload 异构引起尾核，先比较按有效 KV 工作量调度。空间、合并或精度不通过时降低 S，最终退回单所有者流式。arch22 源码的固定 buffer 深度、K 阈值、workspace 上限和 AIC/AIV 比例只对相应分派分支成立；A2/A3 分别验证，不迁移 950 专用实现。

## 伪代码与关键代码

```text
Host: generate disjoint valid KV intervals and unique partial slots
for each producer(task,split):
    compute local unnormalized m,l,U in its interval; mark row validity
    write partial and publish completion after memory visibility
after all required partials complete:
    for each query row owned by merge task:
        E = valid partials; branch on empty before exponentiation
        M=max(mi); L=sum(exp(mi-M)*li); U=sum(exp(mi-M)*Ui)
        finalize output/LSE/epilogue once according to oracle
```

```cpp
// 上下文：Ui 未归一化，weight=exp(mi-M)，partLocal 已完成加载。
AscendC::Muls(weightedLocal, partLocal, weight, validDv);
AscendC::Add(mergedLocal, mergedLocal, weightedLocal, validDv);
// 同时累加 weight*li，最后统一除 L；归一化 partial 需额外 li。
```

片段不包含完成边界、首次初始化、统计计算和 API 临时区；这些必须在 C3 实现并核验目标 SDK。规划冻结 partial 表示、合并次序、最终所有者与融合边界；同 kernel 的局部状态/partial 仍可能通过 GM，不因 CV 融合而删除模型中的写读。

## 验证与证据状态

与单所有者在线结果比较，覆盖 S=1、各片长度不等、空/全 mask 片、所有片为空、KV page 边界、causal/变长/头映射、不同 Dqk/Dv、极端 logit、sink/dropout 所声明子域、LSE、重复执行和空闲核退出。归一化与未归一化表示分别检查，归并顺序变化单独验收精度与确定性。

本条审读了实际 arch22 FIA host 的 normal/FlashDecode 工作区与 kernel 合并入口，未编译/上板。源码存在仅证明可选实现形态，不证明当前 shape 的实际分派或收益；不满足支持域时使用真实已验证 attention fallback entry/key。
