---
schema_version: aprof.knowledge-record/v1
id: planning.matmul.fallback
kind: strategy
version: 1.1.0
status: active
title: MatMul / GMM 通用回退
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
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/community/ops/ascendc-evolution-strategies/references/tiling-design/matmul/ascendc-api-matmul-tiling.md
  original_path: community/ops/ascendc-evolution-strategies/references/tiling-design/matmul/ascendc-api-matmul-tiling.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 408
  sha256: sha256:d2d1a460951b3fbf013c01cd21a1ebeb7014b3501ff7681f36cb77524bdcf3f5
  excerpt_sha256: sha256:d2d1a460951b3fbf013c01cd21a1ebeb7014b3501ff7681f36cb77524bdcf3f5
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
learning: {}
tags:
- complete-k
- verified-fallback
seed_reason: 在保留原 ID/迁移来源的基础上审读固定开源修订，补全中文算法、任务所有权、字节成本与架构边界；未做 NPU 性能训练。
parent: planning.matmul
references:
- planning.matmul.gmm
- planning.matmul.mn
- planning.matmul.resident
- planning.matmul.splitk
- planning.matmul.streamk
evidence_status: source_reviewed_not_benchmarked
---

# MatMul / GMM 通用回退：完整 K 与明确支持域

## 触发条件与基线范围

当 dtype/布局/API 资格、容量、分组语义、跨核进度、误差标准或输出所有权尚未闭合，保留已验证实现。C2 要写出真实 fallback entry/key、可覆盖的元数据域和候选入口互斥条件；“通用 MatMul”不是一个可执行入口名，也不能承诺覆盖 API 不支持的组合。

完整 K 的 MN 独占输出是可审阅基线：每个 `(batch/group,mTile,nTile)` 只由一个所有者计算全部 K，按既定 epilogue 写一次。已有成熟 SDK/框架算子可作为该实现；若 GMM 组合无法被单次接口支持，可逐组调用合法基线并保留实际启动成本。若已有基线本身合法使用其他算法，不为本条机械改写，先保留其已验证语义和资格。

## 输入与分区契约

记录逻辑 M/N/K、转置与物理 stride、广播映射、输入/累加/输出类型、bias/scale/激活、组列表语义、允许误差与未更新输出范围。分组轴和额外切 K 区分；groupType 数字和 API 版本成对保存，旧文档中的枚举不能无检查复制。

令输出任务跨度 TM/TN，组 g 的 `Tg=ceil(Mg/TM)ceil(Ng/TN)`，跨组总任务 `T=Σg Tg`。组前缀构造互斥任务；每核处理其分配任务，核内顺序遍历 K。只读输入可共享，不能让多个输出所有者同时覆盖同一 C 区域。尾 M/N 只写有效长度；空/零 K 的结果按现有 oracle，而不是自行规定清零。

## 容量、成本与停止条件

`sA,sB,sAcc,sC` 是对应每元素字节，`Â` 是按物理布局/对齐计算的字节函数，d 为同时活跃槽数。

```text
L0A=dA×Â(BM×BK×sA)；L0B=dB×Â(BK×BN×sB)
L0C=dC×Â(BM×BN×sAcc)
L1/UB分别取本层所有同时存活区与API临时区字节之和
有效输出字节 = Σg Mg Ng sC_g
额外workspace = 前处理 + 中间stage + partial + 元数据 + API区的峰值存活集合
逐组基线时间 = Σg (launch_g + compute_g + required_transform_g)
```

逐层与当前平台可用容量比较；字节与元素数不能混用。容量、合法 fragment、核数、转换支持未知时补证据；未证明之前不替换已验证路径。基线仍需记录 workspace，不能把“未融合”或“框架接口”当作空间为零。

## 替代方案与融合边界

先比较合法更细 MN 与跨组轮转，再考虑小侧驻留；欠并行长 K 才评估静态 Split-K/StreamK，且同时报告合并、同步、精度成本。规划定义 epilogue 一次执行点、跨 kernel 消费者与允许保留的中间张量；实现阶段选择 API、队列、事件，融合不自动抹去 GM 中间区。

```text
if metadata lies in verified candidate domain and every required proof is present:
    select that candidate's exact entry/key
else if metadata lies in verified fallback domain:
    run fallback entry/key with original ownership and numerical contract
else:
    report unsupported/missing evidence; do not fabricate an implementation
```

```cpp
// 只是“先验合法性分派”的形态；下列变量/入口由工程定义。
if (!candidateDomain || !capacityClosed || !semanticProof || !apiQualified) {
    RunVerifiedFallback(inputs, outputs, originalMetadata);
    return;
}
```

该片段不代表 API 对所有 shape 均支持；fallback 也必须有支持域。验证候选与回退交界 shape、尾块、组基址、特殊值、repeat、错误元数据拒绝和 workspace 上界；计时比较用相同口径保留实际 launch/转换/归并开销。当前仅固定来源审读，未编译/上板；arch22 的支持证据不构成 A2/A3 相同收益保证。
