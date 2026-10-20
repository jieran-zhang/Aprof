---
schema_version: aprof.knowledge-record/v1
id: planning.matmul.splitk
kind: template
version: 1.1.0
status: active
title: 静态 Split-K：固定 K 分段与部分和归并
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/matmul/streamk_design.md
  original_path: ops/ascendc-performance-best-practices/reference/matmul/streamk_design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 374
  sha256: sha256:7fbd5d30ca6333991a4d9cf8d30c7e0468dd9ed4d09d2a2f0abe6ba8d934edb9
  excerpt_sha256: sha256:7fbd5d30ca6333991a4d9cf8d30c7e0468dd9ed4d09d2a2f0abe6ba8d934edb9
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
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cann-samples/17c948bb961fc6a660e4fcab45f6bf217c9c6239/Samples/2_Performance/matmul_story/matmul_recipes/include/block/matmul_block_scheduler_streamk.h
  original_path: Samples/2_Performance/matmul_story/matmul_recipes/include/block/matmul_block_scheduler_streamk.h
  revision: 17c948bb961fc6a660e4fcab45f6bf217c9c6239
  lines:
  - 1
  - 186
  sha256: sha256:ab29684d3cf7520f21b489fb640f6b4d0fb565b4bfbe505abc6b3b78052ae129
  excerpt_sha256: sha256:ab29684d3cf7520f21b489fb640f6b4d0fb565b4bfbe505abc6b3b78052ae129
learning: {}
tags:
- arch22-source
- partial-ownership
- static-split-k
seed_reason: 在保留原 ID/迁移来源的基础上审读固定开源修订，补全中文算法、任务所有权、字节成本与架构边界；未做 NPU 性能训练。
parent: planning.matmul
references:
- planning.matmul.gmm
- planning.matmul.mn
- planning.matmul.streamk
evidence_status: source_reviewed_not_benchmarked
---

# 静态 Split-K：固定 K 分段与部分和归并

## 身份与适用范围

保留稳定 ID `planning.matmul.splitk` 和原路径，正文明确原有“每输出 tile 拆 K、产生 partial、最终归并”的静态语义。StreamK 的完整波次/欠载尾轮调度另见 `planning.matmul.streamk`，不能因两者都有部分和就共用一个算法承诺。

当合法 MN 输出分块仍不足以利用目标计算所有者，K 足够长且额外归并可接受时，把选中的每个输出 tile 的 K 轴预先切成 S 个互不重叠区间。S 和各段边界由 host/规划元数据固定；每段内部按 BK 顺序计算。这里的“静态”指任务到 K 区间的映射固定，不要求 shape 编译期常量。

输入要明确累加 dtype、输出 dtype、非线性 epilogue、精度与可复现标准，以及原子能力或 workspace 上限。K 轴分组的 GMM 语义不等于对同一输出做 Split-K；先识别逻辑输出，再决定是否额外切其归约轴。

## 所有权、两种归并与同步

部分任务键 `(group,mTile,nTile,kSplit)` 唯一，K 区间覆盖 `[0,K)` 且不重叠；槽位含调用实例/批次，防止复用 workspace 时读到上次值。推荐先用 workspace 归并建立可审阅基线：每段写独有 partial，完成后由唯一合并所有者按声明顺序读 S 段，执行一次 bias、残差、激活、转换和最终写回。

原子路线仅在目标 dtype/API 支持且误差允许时进入候选：输出清零责任唯一且必须先于所有原子贡献；K partial 的 atomic-add 次序可能不确定。浮点原子不等同于可复现归并。含非线性激活/量化时，不能每段先做再相加；bias 也不得重复 S 次，外部初值/残差必须按语义只加入一次。

同 kernel 合并需要真实跨核可见性和进度保证；局部 event/PipeBarrier 只解决核内流水，不能保证其他核 partial 已完成。可采用已核验的跨核协议，或以独立归并 kernel 的启动顺序建立完成边界。忙等协议须证明生产者能运行，不可在资源占满时让所有消费者等待未调度生产者。

## 容量、字节与成本

`Ts` 是被拆分的输出 tile 数，`AM,AN` 为 workspace 中对齐后的 tile 存储长宽，`sP` 为 partial 每元素字节，`S_t` 为 tile t 的非空分段数，`Bmeta` 为完成标记/任务元数据实际字节。

```text
Wpartial = Σt∈split S_t × AM_t × AN_t × sP
Wtotal   = Wpartial + Bmeta + API临时区 + 其他同时存活工作区
额外 partial 写读请求 ≈ 2 Wpartial
额外归并加法量 = Σt∈split (S_t−1) × validM_t × validN_t
每段局部 L0C需求 = dC × AlignLayout(BM,BN,sAcc)
选择条件: Tbaseline_critical − Tsplit_compute_critical
          > Tpartial_IO + Tmerge + Tsync + Tlaunch_delta
```

`sAcc` 是局部累加每元素字节，可能与 sP 不同；中途降精度必须单独验收。约 `2Wpartial` 是“与不落 partial 的基线相比”的附加请求，不包含基线最终 C 写回，也不是带宽实测值。原子路线的代价是共享输出的读改写/争用，不能照搬 workspace 的流量公式。

## 参数与替代方案

搜索 S、等长/按合法 K 粒度分段、拆全部还是指定输出子集、partial dtype、合并块形状与顺序。S 不超过合法非空 K 片的数量；按对齐扩展的末段必须屏蔽逻辑 K 之外元素。比较再细 MN、跨组汇总任务、小侧驻留、只处理欠载尾轮的 StreamK 与不切 K 基线。

arch22 文档与 API 路线支持 `EnableMultiCoreSplitK` 及目标原子/工作区归并候选；这不能证明 arch35 样例的 AIC/AIV flag、固定 K 阈值或 dtype 同样可用。S 的选择来自当前任务数、K 粒度、空间和实测，不迁移固定核数、容量或精度模式。

## 伪代码与关键代码

```text
Host: freeze K intervals; verify exact cover and unique partial slots
producer(task,split):
    acc = sum over its declared K interval
    store partial[task,split]; publish completion after store is visible
after all producers finish:
    for each split task assigned to merge owner:
        acc = combine partials in declared order and precision
        apply epilogue once; cast once; write valid output once
```

```cpp
// 合并阶段：partLocal 已从本 tile 当前 split 的唯一槽读入并同步完成。
if (split == 0) {
    AscendC::Adds(sumLocal, partLocal, 0, validCount);
} else {
    AscendC::Add(sumLocal, sumLocal, partLocal, validCount);
}
// 读完全部 split 才做 epilogue 和输出转换。
```

这是“已具备 partial 完成边界”的局部算术片段；队列、读取、首次零值、DMA 单位、API 重载与 alias 需在实现阶段核验。C2 冻结分段、输出所有者、归并次序、数值边界与融合边界；C3 才实现事件及具体接口。

## 验证与回退

验证 S=1、K 不整除、不同分段数、M/N 尾块、拆分与未拆分输出并存、bias/残差只一次、atomic 清零先行、重复执行、允许的 NaN/Inf 与极值。与完整 K 基线比较误差；确定性需求比较重复运行和固定归并树，不仅检查一次容差。若空间、原子能力、同步进度或精度不闭合，回退完整 K MN 所有权。当前仅来源审读，未编译/上板，无性能收益资格。
