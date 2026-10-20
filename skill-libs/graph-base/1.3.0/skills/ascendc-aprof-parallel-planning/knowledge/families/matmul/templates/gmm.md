---
schema_version: aprof.knowledge-record/v1
id: planning.matmul.gmm
kind: template
version: 1.0.0
status: active
title: GMM：跨组任务串接、异构负载与组尾轮转
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/community/ops/ascendc-evolution-strategies/references/tiling-design/matmul/ascendc-api-gmm-tiling.md
  original_path: community/ops/ascendc-evolution-strategies/references/tiling-design/matmul/ascendc-api-gmm-tiling.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 313
  sha256: sha256:90d9b2c693a9fb876326157a618e383413c28cf660e8d4f92941a96b6c593cb1
  excerpt_sha256: sha256:90d9b2c693a9fb876326157a618e383413c28cf660e8d4f92941a96b6c593cb1
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/gmm/grouped_matmul/README.md
  original_path: gmm/grouped_matmul/README.md
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 146
  sha256: sha256:722098cea2767385e5a35e9b85410fd07cedd36608d3e2d2e6e16505d8e8389a
  excerpt_sha256: sha256:722098cea2767385e5a35e9b85410fd07cedd36608d3e2d2e6e16505d8e8389a
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/gmm/grouped_matmul/op_kernel/grouped_matmul_kernel.h
  original_path: gmm/grouped_matmul/op_kernel/grouped_matmul_kernel.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 167
  - 386
  sha256: sha256:904a8e8df4325a44c32a5f60b7f9bcc3ce345bb3c5520a10ec16af4e4f159dc1
  excerpt_sha256: sha256:9179b2567eee9939d5da0c3387ca0a83dbce6fa61b1e48b5270d11a24826b6d0
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/gmm/grouped_matmul/op_host/op_tiling/grouped_matmul_tiling.cpp
  original_path: gmm/grouped_matmul/op_host/op_tiling/grouped_matmul_tiling.cpp
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 777
  - 837
  sha256: sha256:e6a78676240ef526b9a1ec46d24fe348ddb053b9becb9cc6bfa58803b6ed5c25
  excerpt_sha256: sha256:eb22efb1917bc3e23cbe4d5be5e0d501f31302baeef59a6a42a9e5832514b9fa
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/gmm/grouped_matmul/op_host/op_tiling/grouped_matmul_tiling.cpp
  original_path: gmm/grouped_matmul/op_host/op_tiling/grouped_matmul_tiling.cpp
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1627
  - 1650
  sha256: sha256:e6a78676240ef526b9a1ec46d24fe348ddb053b9becb9cc6bfa58803b6ed5c25
  excerpt_sha256: sha256:8b17125f37358480f74b9b1f2323ea92c690e2750cf2a571cad3b93cb0cb0c81
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 138
  sha256: sha256:080b31488432d91c218eacb24f37608c99425ab7b6b692f2e6e7691a407475a6
  excerpt_sha256: sha256:080b31488432d91c218eacb24f37608c99425ab7b6b692f2e6e7691a407475a6
learning: {}
tags:
- gmm
- group-tail-carry
- heterogeneous-scheduling
seed_reason: 从固定开源修订的实际调度代码提炼独立规划模板；与现有输出分块、静态切 K 语义区分；未做 NPU 性能训练。
parent: planning.matmul
references:
- planning.matmul.mn
- planning.matmul.resident
- planning.matmul.splitk
evidence_status: source_reviewed_not_benchmarked
---

# GMM：跨组任务串接、异构负载与组尾轮转

## 为什么独立成模板

GMM 计算 `Yg[Mg,Ng]=Xg[Mg,Kg]×Wg[Kg,Ng]`，常见于已按专家打包的 MoE token。独立组的地址、shape、空组和 epilogue 参数不同；每组都从核 0 重新分配，可能让相同核反复承担尾任务。跨组调度是 MN 基线之外的独立规划问题，不能只把 group 作为额外索引后宣称已均衡。

先冻结分组轴、tensor-list/单 tensor 组合、groupList 的“累积端点/每组大小/稀疏组号与大小”语义、组基址、转置与物理布局、量化参数对应关系。**K 轴分组**仍可产生多个独立 Yg；它与对同一 Y 的 K 贡献做 Split-K 不是同义。groupType 数字须按目标 API 版本核验；本次高阶 API 说明与实际代码的枚举数字已有差异，不在规划中照抄旧数字。

## 分区、所有权与组尾轮转

每组 `Tg=ceil(Mg/TM_g)ceil(Ng/TN_g)`，组前缀 `Og=Σh<g Th`，把局部 tile j 映射为全局任务 `t=Og+j`。基线分配 `owner=t mod P`，每核遍历 `t=p,p+P,...`。等重任务总数最多差一；与“每组 j 从 0 起取模”相比，后一组从上组的余数继续，避免组尾集中在同一组核。

实际 GMM kernel 用 `count=curCount mod coreNum` 跨组携带轮转起点，是同一机制的在线形式；既可 host 展开任务表，也可 kernel 按组前缀解码，不能因此假设上游已采用动态抢任务。对异构 Kg、不同尾 M/N 或量化工作量，按 tile 计数仍可能失衡，应比较带权 `Wp=Σt∈p wt`，必要时按形状/路径分桶或使用已实现的带权静态表；调度改变同时比较组内权重复用。

任务键 `(invocation,group,mTile,nTile)` 唯一，独占相应 Yg 区域。组输入和权重只读；组 id 与 tensor-list 序号、稀疏专家号和紧凑输出序号可能不同，必须独立保存。零输出元素的组不产生计算任务，但其对前缀、组号、输出未指定区域的约定仍保留，不能因跳过计算而把下一组基址错移。零 K 但 M/N 非零的组按 oracle 决定是否写零、执行 bias/epilogue 或保持未更新区，不能从源码某个分支的跳过逻辑推导通用语义。

## 归约、同步与融合边界

默认每任务完整 Kg，无跨组输出归约。只有显式对某个 Yg 做额外 Split-K，才新增 partial 槽与归并所有者。若量化/反量化/激活由 Vector 消费 Cube 中间结果，需定义 `(group,tile,stage-slot)` 槽和生产完成依赖；同 kernel 融合仍可能通过 GM workspace，不能省略写读成本。

在规划阶段确定 bias/scale/激活属于哪个组、哪一行/列、在完整归约前后哪个位置，以及是否保留外部消费者需要的中间结果。具体 dtype API、核比例、flag 和 queue 在实现阶段选，不能把某个量化子路的 AIC/AIV 比例泛化到全部 GMM。

## 容量与成本公式

`sA_g,sB_g,sC_g,sAcc_g` 是各组对应每元素字节；`at,bt,ct` 是某任务有效 M、N、K 长度；`AlignLayout` 返回真实布局和对齐字节。

```text
T = Σg Tg；总乘加量 = Σg 2 Mg Ng Kg
task权重初值 wt = 2 at bt ct + 量化/转换/epilogue估计工作
输出有效写字节 = Σg Mg Ng sC_g
任务表字节 = T × descriptorBytes；组前缀表 = (G+1) × prefixBytes
L0C需求 = 同时活跃累加槽数 × AlignLayout(BM,BN,sAcc)
Wstage = Σe (liveSlots_e × AlignLayout(rows_e,cols_e,dtypeBytes_e))
Wtotal = Wstage + WsplitK + Wpretransform + Wmetadata + Wapi
```

e 遍历 Cube→Vector、Vector→Cube 等实际经 GM 的边；liveSlots 由流水深度与所有者数共同确定。按峰值同时存活集合复用内存时，需要生命周期证明，不能简单把所有区重叠。组数上限、NZ 对齐、数据类型支持与工作区策略按当前平台/SDK 核验；不搬用来源的固定数组长度、baseN、UB 划分常数或 quant 阈值。

## 参数与选择规则

搜索任务跨度、跨组顺序/分桶、组尾轮转、使用所有者数、单组 N 合并跨度、小侧驻留窗口、量化 epilogue 分块。大任务多时按组保持连续以复用权重；大量小组时先汇总组间独立性；少数大 Kg 组拖慢尾核时比较带权表或对这些组单独 Split-K。合并 N 任务会减少调度但增加单任务工作，需同时算最长核与驻留机会。

动态 groupList 无法 host 读取时，可传经校验的最大范围并在 kernel 解码；workspace 和溢出检查以可达上界预算，不可用平均 token 数当最大需求。语义/布局支持不明确，回到目标 SDK 支持的分组算子，或逐组已验证 MatMul；逐组启动的成本需保留为基线，不把新候选默认为更快。

## 伪代码与关键代码

```text
normalize group metadata without changing group identities or untouched output ranges
build prefix tile counts; validate addresses, total sizes and arithmetic overflow
for global task assigned to this owner:
    find group and local tile, using prefix or online carry
    load group-specific pointers/shape/scale; compute its complete K
    consume dependent stages; apply group epilogue once; write valid Yg region
```

```cpp
// 等重静态调度的跨组轮转示意；carry 在组间保留，owners>0。
uint64_t carry = 0;
for (uint64_t g = 0; g < groups; ++g) {
    const uint64_t end = carry + groupTiles[g];
    uint64_t t = ownerId >= carry ? ownerId : ownerId + owners;
    for (; t < end; t += owners) {
        ComputeGroupTile(g, t - carry);  // 工程自定义，使用组专属基址与有效范围
    }
    carry = end % owners;
}
```

片段对应实际 kernel 的 count carry 机制，省略 MN 遍历与生命周期管理；ComputeGroupTile 不是 SDK API。groupTiles 与加法/索引宽度须校验，混合核 ownerId 映射和 API 收尾在实现阶段核验。

## 验证与证据状态

覆盖单组、多组、全空/间隔空组、极不均匀 token、不同 Kg/Ng、累积/长度/稀疏 groupList、单/多 tensor、非连续与 NZ、组号不同于 list 序号、输出未指定区域、多个组均有尾块、重复调用。审查每组有效输出覆盖、scale/bias 索引和每核带权负载。

正文已结合实际 GMM README、host 与 kernel 纠正旧说明的泛化限制；通用调度可用于候选检索，具体 arch22 与 arch35 入口及量化路径必须分开核验。当前未编译/上板，不继承来源性能阈值或收益。
