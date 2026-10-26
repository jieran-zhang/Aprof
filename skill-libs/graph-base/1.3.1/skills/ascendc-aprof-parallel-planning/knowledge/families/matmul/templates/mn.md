---
schema_version: aprof.knowledge-record/v1
id: planning.matmul.mn
kind: template
version: 1.1.0
status: active
title: MN 输出分块与完整 K 所有权
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/matmul/ascendc-api-gmm-tiling.md
  original_path: ops/ascendc-tiling-design/references/matmul/ascendc-api-gmm-tiling.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 313
  sha256: sha256:90d9b2c693a9fb876326157a618e383413c28cf660e8d4f92941a96b6c593cb1
  excerpt_sha256: sha256:90d9b2c693a9fb876326157a618e383413c28cf660e8d4f92941a96b6c593cb1
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 138
  sha256: sha256:080b31488432d91c218eacb24f37608c99425ab7b6b692f2e6e7691a407475a6
  excerpt_sha256: sha256:080b31488432d91c218eacb24f37608c99425ab7b6b692f2e6e7691a407475a6
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 139
  sha256: sha256:411edebe99b43b0bb05bac2754c1d4ffd4abe46c726df718c0c1b4a7131eb0ed
  excerpt_sha256: sha256:411edebe99b43b0bb05bac2754c1d4ffd4abe46c726df718c0c1b4a7131eb0ed
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/community/ops/ascendc-evolution-strategies/references/tiling-design/matmul/ascendc-api-matmul-tiling.md
  original_path: community/ops/ascendc-evolution-strategies/references/tiling-design/matmul/ascendc-api-matmul-tiling.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 408
  sha256: sha256:d2d1a460951b3fbf013c01cd21a1ebeb7014b3501ff7681f36cb77524bdcf3f5
  excerpt_sha256: sha256:d2d1a460951b3fbf013c01cd21a1ebeb7014b3501ff7681f36cb77524bdcf3f5
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/gmm/grouped_matmul/op_kernel/grouped_matmul_kernel.h
  original_path: gmm/grouped_matmul/op_kernel/grouped_matmul_kernel.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 167
  - 386
  sha256: sha256:904a8e8df4325a44c32a5f60b7f9bcc3ce345bb3c5520a10ec16af4e4f159dc1
  excerpt_sha256: sha256:9179b2567eee9939d5da0c3387ca0a83dbce6fa61b1e48b5270d11a24826b6d0
learning: {}
tags:
- arch22-source
- complete-k
- mn-ownership
seed_reason: 在保留原 ID/迁移来源的基础上审读固定开源修订，补全中文算法、任务所有权、字节成本与架构边界；未做 NPU 性能训练。
parent: planning.matmul
references:
- planning.matmul.gmm
- planning.matmul.resident
- planning.matmul.splitk
- planning.matmul.streamk
evidence_status: source_reviewed_not_benchmarked
---

# MN 输出分块与完整 K 所有权

## 适用问题与规划输入

计算 `C[M,N]=A[M,K]×B[K,N]`，也适用于形状已规范化的 BatchMatMul 和多组独立矩阵乘。先明确转置、物理 stride、广播规则、输入/累加/输出 dtype、bias/激活及允许的误差。这里的 K 是数学归约长度，不能从张量最后一轴盲取；非连续和 NZ 布局还需独立的物理地址函数。

这是首个可比较基线：沿输出 M/N 切成互不重叠的任务，完整 K 保留在一个输出所有者内。分组异构和组尾轮转在 `planning.matmul.gmm` 中细化；本条保留原路径与 ID，旧入口仍可到达。

## 算法骨架与任务所有权

选输出任务跨度 `TM,TN`，组 g 有 `Tg=ceil(Mg/TM)×ceil(Ng/TN)` 个任务。任务键为 `(batch/group,mTile,nTile)`，所有者遍历全部 K 后写一次有效输出。基本计算块 `BM,BN,BK` 与任务跨度可以不同：一个核任务可包含多个基本块，不能把 API 的 singleCoreM/N 与 baseM/N 混成同一层。

对 T 个任务和 P 个逻辑计算所有者，可按 `task=p,p+P,...` 分配；任务等重时每核数量最多差一。异构 K、M/N 尾块或稀疏任务使“任务数均衡”不再等于耗时均衡，需比较每核估计工作量 `Wp=Σt∈p wt` 与 `max(Wp)`。初始 `wt≈2 mt nt Kt` 只计乘加工作，不含转换、量化和调度；各项可用同一环境的基线测量修正。

不同任务无输出归约；A/B 只读共享。核内 K 块依序累加，同一输出累加器的首块初始化、末块写回；使用多个局部槽时，只有消费完成才可覆写。跨核同步通常只在前处理/后处理确有依赖时需要，独立 MN 任务不增加全局屏障。

## 容量、流量与符号

`sA,sB,sAcc,sC` 分别是 A/B、累加、输出的每元素字节；`Â(X)` 表示按目标布局、行跨度与搬运粒度补齐后 X 的实际存储字节；`dA,dB,dC` 是同时存活槽数。

```text
L0A需求 = dA × Â(BM×BK×sA)
L0B需求 = dB × Â(BK×BN×sB)
L0C需求 = dC × Â(BM×BN×sAcc)
L1需求  = Σ同时存活的 A/B 大包、驻留区、bias/scale 与 API 临时区字节
T        = Σg ceil(Mg/TM) ceil(Ng/TN)
理想乘加量 F = Σg 2 Mg Ng Kg
无跨任务复用时，输入读量估计 = Σt (mt Kt sA + Kt nt sB)
最终有效写量 = Σg Mg Ng sC
```

前三个容量分别与对应层的可用字节比较，不能把它们相加后与单一缓存容量比较。输入读量是逻辑请求估计；缓存命中、padding、预变换及跨 tile 重用会改变实际 GM 流量。输出 tile 的大包 K 深度、L0 基本块和各层 double buffer 要分别列出生命周期，不能仅检查一个 `BM×BN`。

## 参数空间与选择规则

先搜索合法 `TM,TN`，报告 T、最长核工作量、M/N 有效占比，再搜索 `BM,BN,BK` 与 L1 包深度。缩小输出任务能填核，也会增加调度、重复输入搬运和尾块比例；足够并行时优先比较遍历顺序、小侧驻留及共享工作集分片，不能只追求启动满核。

M/N 达到合法粒度仍欠并行且 K 长时，比较静态 Split-K 的额外合并成本；只有末轮不满时，可另评估 StreamK 混合调度。重复侧实际可容纳且会多次使用时比较驻留。Batch 合并进 M 必须证明 B 广播、A 布局和输出地址连续性，不能仅凭 batchB=1 改 shape。

## 伪代码与关键上下文

```text
Host: validate logical shapes/strides -> choose task grid and legal base tiles
      compute tasks and per-core work -> freeze owner map and valid extents
for task assigned to this owner:
    decode (group,m,n); acc = zero in declared accumulation type
    for k in [0,K) by BK:
        load valid A/B fragments, pad only invalid fragment elements
        wait for consumed slots -> acc += A_fragment × B_fragment
    apply the declared epilogue once; write valid M,N only
```

```cpp
// 仅展示任务枚举；usedOwners 是规划后的逻辑所有者数，须大于零。
for (uint64_t t = ownerId; t < totalTasks; t += usedOwners) {
    const auto task = DecodeTask(t);       // 工程自定义，返回组基址与 m/n 有效范围
    mm.SetSingleShape(task.validM, task.validN, task.K);
    mm.SetTensorA(aGm[task.aOffset], transA);
    mm.SetTensorB(bGm[task.bOffset], transB);
    mm.IterateAll(cGm[task.cOffset]);       // 此上下文为完整 K、独占输出的 API 路线
}
```

片段省略 Matmul 注册、SetOrgShape、buffer 初始化、偏移定义与 API 收尾；DecodeTask 不是 SDK API。`ownerId` 必须由 kernel mode 映射，混合核入口的物理 blockIdx 不能直接当所有者 ID。API 具体重载、同步语义、dtype、尾块与转置支持在实现阶段核验；模板不授权更改数值语义。

## 融合边界、回退与证据

规划阶段决定 bias/激活是否属于此输出所有者、输出是否有外部消费者、是否跨 kernel 保留中间结果以及转换发生点；后续实现才选择 Cube/Vector API、事件和局部缓冲。融合能减少某些边的写读，混合核握手或 API 可能仍走 GM，不能预先把全部中间流量计为零。

不能闭合容量、地址或精度时退回已验证的完整 K MatMul 路线，并提供真实 entry/key 与互斥范围。验证至少覆盖转置组合、M/N/K 主尾块、零维语义、广播、组基址、重复执行及允许的特殊值；确认每有效输出恰写一次、无越界及新增未定义区域写入。资料包含 arch22 A2/A3 API/实现依据，scope=all 仅作检索范围；未编译、未上板，型号收益与最优参数未验证。
