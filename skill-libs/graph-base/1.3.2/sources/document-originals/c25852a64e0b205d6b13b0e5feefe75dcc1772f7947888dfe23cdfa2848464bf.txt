---
schema_version: aprof.knowledge-record/v1
id: implementation.fusion-composition.cv_multistage_handoff
kind: recipe
version: 1.0.0
status: active
title: dav-2201 的 C1–V1–C2–V2 多阶段交接
scope:
  platforms:
  - dav-2201
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/fused_infer_attention_score/op_kernel/arch22/fia_kernel_nonquant.h
  original_path: attention/fused_infer_attention_score/op_kernel/arch22/fia_kernel_nonquant.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 95
  - 1120
  sha256: sha256:f9329654b3966cbb62b4f23c4d6d91cd2fcc48335a58915075f9f52184f4f837
  excerpt_sha256: sha256:51be295b11320b07caaffe8c601255e1c445fa184612fe67e19ed521696afd4b
- path: skills/ascendc-aprof-optimization/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/fused_infer_attention_score/op_kernel/arch22/fia_block_cube_nonquant.h
  original_path: attention/fused_infer_attention_score/op_kernel/arch22/fia_block_cube_nonquant.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 455
  - 1039
  sha256: sha256:d094ef548ac453210f72ffdd3366a410ca74d9c10ac2084f93e49448a3224eb9
  excerpt_sha256: sha256:d5fd173ae1d08db1d82faedb841687992d289c9fad9ef504f32b4cb501f08a08
- path: skills/ascendc-aprof-optimization/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/fused_infer_attention_score/op_kernel/arch22/fia_block_vec_nonquant.h
  original_path: attention/fused_infer_attention_score/op_kernel/arch22/fia_block_vec_nonquant.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1429
  - 1445
  sha256: sha256:91bd5edfc5fb2aa44c6f33d479d2d258bff1da93a35b8385521703a8ba7fbeaf
  excerpt_sha256: sha256:b8150ef7e442f28b1f260c668560d1907e91fed1b5f6fe4bde9ff792d8fe671a
- path: skills/ascendc-aprof-optimization/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/flash_attention_score/op_kernel/arch22/flash_attention_score_s1s2_bn2gs1.h
  original_path: attention/flash_attention_score/op_kernel/arch22/flash_attention_score_s1s2_bn2gs1.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 399
  - 1100
  sha256: sha256:e739820e172fa26ae73c802ad8ca2ceabb1080ee9dd1e3c2c8226d08f7d6e34a
  excerpt_sha256: sha256:4a9a63533fd44f30032a770d25255ed92d8912b97484c2feea89c38fe62a081f
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md
  original_path: ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 155
  sha256: sha256:ea3be814234904a2d8a4a3b99847aec00c849f3fb3ce2647390a3dce0a734ba1
  excerpt_sha256: sha256:ea3be814234904a2d8a4a3b99847aec00c849f3fb3ce2647390a3dce0a734ba1
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md
  original_path: docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 28
  - 151
  sha256: sha256:69845e8fa794040e321959eaa57105a79cdf880c2d9460b7bf65a53f3c644827
  excerpt_sha256: sha256:02edbe3918b020be18c5b07b81c9bc18153e3f3ab7ba41a9962391c7173aa399
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md
  original_path: docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 28
  - 151
  sha256: sha256:fb6098e64301d056e53eb0f083dcc96083075fc8da78409492f905653c311f96
  excerpt_sha256: sha256:c5145c71c4361eef7d3e7a5597dfa8bc235c92153767ab8322ebee5109ed0b5d
- path: skills/ascendc-aprof-optimization/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/flash_attention_score/docs/FA算子设计介绍.md
  original_path: attention/flash_attention_score/docs/FA算子设计介绍.md
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 57
  - 94
  sha256: sha256:87667734ca5c9fdf6ada8aefe029cdf6110d94b30a8b15535933be5a3d462e44
  excerpt_sha256: sha256:6f04e84c2aa421fe1bde0912a554f3e7f8a3674a640872654f7151fd4f3c0bcd
learning: {}
tags:
- fusion
- source-reviewed
- not-benchmarked
seed_reason: 固定开源修订审读并以中文提炼；未做性能训练或硬件收益验证。
parent: implementation.fusion-composition
references:
- implementation.pipeline-sync.pipeline
- implementation.pipeline-sync.slots
- implementation.buffer-lifetime.reuse
- implementation.fusion-composition.cube_vector_epilogue
evidence_status: source_reviewed_not_benchmarked
---

# dav-2201 的 C1–V1–C2–V2 多阶段交接

## 范围、原理与适用条件

本条**来源实现与路由范围限定dav-2201/arch22**，面向C2已选FA/FIA式融合方案的910C/A3落地候选。通用思想是让一个stage的完整输出成为下一stage输入，在保留依赖的同时交错不同tile；具体描述符数量、GM槽数、事件和preload不推广到950/arch35。数学上的Cube→Vector→Cube→Vector链可迁移到其它算法，但迁移需要重新定义任务、所有权、状态和通路。

对于attention，一条KV块内保持`C1(QK)→V1(scale/mask/online softmax)→C2(PV)→V2(rescale/accumulate/final output)`。融合region把四阶段放入同一kernel；arch22数据交接仍可使用GM；跨不同KV块交错才带来C/V overlap。这三件事不能互相代证。

适合有多个KV块或多个query task、QK与PV能在已预算的L1/L0执行、Vector状态有明确保存位置的shape。只有一个块、极短序列、query task不足、workspace/UB挤压严重时，多级流水未必胜过浅流水。paged cache、GQA/MLA、TND/NTD、mask压缩、量化、Rope及Split-KV均有额外分派/布局限制，必须匹配实际arch22模板，不是见到attention名称就套用。

## C2决定结构，C3实现许可的交接

C2冻结融合region、query/KV task定义、task到逻辑core的分配、C:V配比、Split-KV/最终归并所有者、s2遍历顺序、状态精度、mBase/sInner范围、GM/UB通路、workspace分区和流水候选拓扑。C3可以在这些约束内实现stage发射、ready/free、buffer地址及收尾；改变任务粒度、预加载所需存储深度超预算、迁移state到另一核或换通路都须重规划。

S1的FIA arch22源码常量是`PRELOAD_NUM=2`（数据workspace倍数）与`FIA_PRELOAD_TASK_CACHE_SIZE=3`（RunInfo描述符数）。主调度`ExecuteTask`在节拍t安排：

| 节拍阶段 | 逻辑任务 | 硬件/职责 | 必须已满足的前提 |
|---|---|---|---|
| C1 | t | AIC计算QK并输出S | 当前任务有效、输入ready、S槽可写 |
| V1 | t-1 | AIV读S并产生P/online状态 | C1(t-1)已发布，P槽及state可写 |
| C2 | t-1 | AIC读P计算PV | V1(t-1)已完成P的GM搬出 |
| V2 | t-2 | AIV读PV并更新O | C2(t-2)已发布，所需旧state尚未覆盖 |

这是S1的具体发射结构，不是对任意环形state布局都安全的全局定序。若C2选择的state只有一份且V1会覆盖V2仍需的旧因子，必须为旧state保留独立槽或在许可拓扑内先执行V2。不能直接把其它架构文档“V2必须提前”或“统一用3槽”当作当前源码事实。

## 数学最终化与跨s2状态

以下是**算法依赖说明**，不是要求C3替换原FA算法。对同query的KV块t，令`S_t=scale*Q*K_t^T+mask`，`m_t=max(m_{t-1},rowmax(S_t))`，后续块`alpha_t=exp(m_{t-1}-m_t)`，`P_t=exp(S_t-m_t)`：

```text
l_t = alpha_t*l_(t-1) + rowsum(P_t)
O_t = alpha_t*O_(t-1) + P_t*V_t
Y   = O_last / l_last
```

首块直接形成`l=rowsum(P), O=P*V`，不读取未定义的旧O/alpha；后续块必须回读同query的running max/sum、重标定因子和Oacc。V1中P是未归一化指数，并非完整softmax概率；最终除法在该query最后一个有效KV块及必要Split-KV归并后发生。全mask/空KV/无效行输出、NaN/Inf和零分母策略须沿用原oracle及选中模板，不可为“防除零”任意加epsilon改语义。

每个QK或PV块若内部沿归约K分多次Mmad，只有完整归约后才向下游发布；不能对QK partial先做非线性softmax，也不能用某次Fixpipe完成替代逻辑最终化。Split-KV将同query分到多核时，局部max/sum/O的最终合并是另一任务阶段，C3不擅自把局部输出当最终Y。

## 交接表与可计算的字节预算

令m为query行tile、s为对齐KV块长、dv为对齐输出宽度。`ES=m*s`、`EP=m*s`、`EO=m*dv`、`EU=m*dv`，类型字节为eS/eP/eO/eU；feature可能增加组件。各slotStride按目标DMA/存储对齐a_j取整：

```text
B_S=align(ES*eS,aS); B_P=align(EP*eP,aP)
B_O=align(EO*eO,aO); B_U=align(EU*eU,aU)
W_normal = logicalCores*(dS*B_S+dP*B_P+dO*B_O+dU*B_U)
W_total  = W_normal + W_splitKV + W_feature + 必要对齐间隙
UB_AIV   = 输入/输出物理槽总字节 + online状态 + mask/pse + scratch + API预留
```

这是本文保守推导；S1实际`InitWorkspace`按四类区域逐个推进offset、每类有`GetBlockNum()*PRELOAD_NUM*elements*sizeof(type)`，其实际元素尺寸由Host tiling提供。复用某区域前必须证明同一tensor布局和生存区间允许；不能按上述抽象公式抹掉FP32/NZND/量化等额外分量。S4的FA arch22对BMM1/Vec1按类型/格式调整倍数，说明workspace不恒等于四张量乘统一常数。

| 交接对象 | 生产者→消费者 | 存储/索引域 | 生命周期终点 |
|---|---|---|---|
| S=QK | C1 Fixpipe→V1 MTE2 | GM handshake，序号按数据depth | V1搬入/最后所需读完成 |
| P=exp(S-m) | V1 MTE3→C2 MTE2 | GM handshake，独立于任务描述符 | C2完成读取P的大包 |
| PV | C2 Fixpipe→V2 MTE2 | GM handshake | V2读完本块 |
| running max/sum、alpha | V1→后续V1/V2 | query self-reference state | 当前query最后相关读者完成 |
| Oacc | V2→后续V2/最终写回 | query state或GM回写槽 | 同query最终输出/归并完成 |
| RunInfo描述符 | 创建方→四stage | S1为3份task缓存 | V2不再引用后invalid |
| Q/P、KV的L1包 | MTE2→MTE1 | 各自包计数与ping/pong | 最后baseK读取完 |

例如仅作演算：m=64、s=128、dv=128，S/O为float、P为half、U为float，32B对齐且四类各2槽，每逻辑core显式GM数据为`2*(32768+16384+32768+32768)=229376B`；三份描述符不把这值改成三倍。实际case必须使用选中模板的真实E/type与feature开销。

## prolog、steady、drain 的上下文伪代码

以下模型强调有效位、描述符和数据槽相互独立；`C1/V1/C2/V2`是本文stage名称，不是仓库私有helper。实现只能使用目标SDK公开Matmul/Vector/搬运/同步接口或当前工程既有封装。

```text
初始化所有task descriptor为invalid；初始化query state契约和可写槽
for tick in [0, taskCount+2):
    if tick < taskCount:
        require desc[tick%3]已退休
        desc[tick%3] = frozen_task(tick); valid=true
        C1(desc[tick%3], S_slot=tick%dataDepth)
    if 0 <= tick-1 < taskCount:
        d=desc[(tick-1)%3]
        V1(d)   # wait C1 ready；写P/state；在MTE3完成点publish
        C2(d)   # wait P ready；完整PV归约后publish
    if 0 <= tick-2 < taskCount:
        d=desc[(tick-2)%3]
        V2(d)   # wait PV ready；保留同query前态；末块才最终输出
        require该描述符再无异步读者
        d.valid=false
# 等所有已提交搬出，回收本核事件；不能从drain继续建新task
```

在实际分离的AIC/AIV路径中，两个硬件各执行自己的stage，跨核事件使它们在消费点会合，并非一核顺序执行四段。S1主循环同时考虑“还有可派任务”与“缓存中仍有有效任务”，保证停止创建后仍继续排空；sparse/zero/skip路径也必须沿真实任务序列更新，不能只递增一边的计数。

## 真实SDK同步片段与架构语义

S2/S3的arch22服务实现证明C1输出后在PIPE_FIX上发ready、V1搬出P后在PIPE_MTE3上发ready、C2输出后再发ready。下面把外部服务类名去掉，仅保留可在`kernel_operator.h`下使用的公开API，`fC1V1/fV1C2/fC2V2`是工程分配且避开库占用的不同flagId。

```cpp
#include "kernel_operator.h"
// AIC：已经完整计算/提交Fixpipe(S)后：
AscendC::CrossCoreSetFlag<0x2, PIPE_FIX>(fC1V1);
// AIV：准备消费S前；其后搬入S、执行V1并提交P的GM写回：
AscendC::CrossCoreWaitFlag<0x2>(fC1V1);
// AIV：P的MTE3写回路径完成点：
AscendC::CrossCoreSetFlag<0x2, PIPE_MTE3>(fV1C2);
// AIC：C2搬入P之前：
AscendC::CrossCoreWaitFlag<0x2>(fV1C2);
// AIC：完整PV及Fixpipe(PV)提交后：
AscendC::CrossCoreSetFlag<0x2, PIPE_FIX>(fC2V2);
// AIV：V2消费PV前：
AscendC::CrossCoreWaitFlag<0x2>(fC2V2);
```

这些行分属于不同硬件分支，不应连成同核独立函数运行。它们展示正向ready；环形数据复用还必须由既定阶段次序和必要反向free保证。mode2是AIC与两个AIV，空片也不能破坏参与计数；不要随意让AIV1 early-return。

S6/S7官方文档应作为跨架构同步语义的直接依据：A2/A3的Wait模板mode/pipe不作为硬件输入，省略mode不改变功能，Wait阻塞全部流水后续发射；所以S2/S3源码Set<2>与默认Wait不构成天然bug。显式同mode有助代码审阅。950 mode4另有硬件指令且2201不支持，不能从950样例抄来。事件资源、库内部flag占用和counter上限应按目标SDK核对。

## 源码事实、合成推导与平台旁证

- S1/S2/S3是FIA arch22具体workspace、调度和C/V就绪链事实；S4是另一FA arch22模板的2数据槽/3描述符及格式额外workspace事实，不能将两套内部类拼成依赖。
- S5是arch22性能设计指南，作为审读方法；本文的活跃区间、通用字节模型、伪代码与演算shape属于合成推导，需要当前工程证实。
- S8的FA设计文档同时含A2和950章节：950的preload=3与共享UB叙述仅为其架构分支，不用于本条dav-2201路由或默认参数。主线独立依赖上述arch22源码。

## 验证、失败与回退

静态提交task拓扑、四类GM区间、每个stage读写集合、每种slot深度/代次、事件生产消费及首轮/尾轮数量。正确性覆盖task数0/1/2/3及超过数据/描述符回卷周期、同query多个s2、query切换、奇数M、尾KV、空/全mask块、Split-KV若存在及重复运行；核对每次state更新属于同一query，输出只最终化一次。

周期性精度漂移通常提示数据槽与描述符混用；只多s2失败提示state过早覆盖；首尾挂起提示空任务/skip/drain未配对；V忙C闲可能要由C2重排stage而非盲目加槽。回退为原计划允许的浅流水或串行stage，保留同样online语义和最终化；需要新的state布局、Split-KV策略、核数、workspace或通路时交回C2。只有完整正确性通过后才比较Task Duration及C/V/MTE timeline，公开源码不保证当前910C shape收益。

## 固定来源与证据级别

- S1：[attention/fused_infer_attention_score/op_kernel/arch22/fia_kernel_nonquant.h](../../../sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/fused_infer_attention_score/op_kernel/arch22/fia_kernel_nonquant.h)，行 95–1120；修订 `d7e6a7c6c1450c040049486845336c77f3100406`。
- S2：[attention/fused_infer_attention_score/op_kernel/arch22/fia_block_cube_nonquant.h](../../../sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/fused_infer_attention_score/op_kernel/arch22/fia_block_cube_nonquant.h)，行 455–1039；修订 `d7e6a7c6c1450c040049486845336c77f3100406`。
- S3：[attention/fused_infer_attention_score/op_kernel/arch22/fia_block_vec_nonquant.h](../../../sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/fused_infer_attention_score/op_kernel/arch22/fia_block_vec_nonquant.h)，行 1429–1445；修订 `d7e6a7c6c1450c040049486845336c77f3100406`。
- S4：[attention/flash_attention_score/op_kernel/arch22/flash_attention_score_s1s2_bn2gs1.h](../../../sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/flash_attention_score/op_kernel/arch22/flash_attention_score_s1s2_bn2gs1.h)，行 399–1100；修订 `d7e6a7c6c1450c040049486845336c77f3100406`。
- S5：[ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md](../../../sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md)，行 1–155；修订 `41377d0a442cd5b1c2356874873a3dda591c6633`。
- S6：[docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md](../../../sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md)，行 28–151；修订 `d378849769f9ee610af9d0ac38db2b3b6bed3209`。
- S7：[docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md](../../../sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md)，行 28–151；修订 `d378849769f9ee610af9d0ac38db2b3b6bed3209`。
- S8：[attention/flash_attention_score/docs/FA算子设计介绍.md](../../../sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/attention/flash_attention_score/docs/FA算子设计介绍.md)，行 57–94；修订 `d7e6a7c6c1450c040049486845336c77f3100406`。

来源事实、本文推导与待验证项在正文分别标注。冻结源码及仓库许可证随包保存；本次仅完成审读，未在目标 SDK 构建，未运行 NPU 正确性或性能测量。源码存在不代表当前 shape 已分派到该路径，任何收益都须由当前候选的完整正确性、Task Duration 与针对性 timeline 证明。
