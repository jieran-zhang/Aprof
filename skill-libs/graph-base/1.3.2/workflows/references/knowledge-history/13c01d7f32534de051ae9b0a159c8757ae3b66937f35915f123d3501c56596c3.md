---
schema_version: aprof.knowledge-record/v1
id: planning.under-fusion.chain
kind: template
version: 1.1.0
status: active
title: 融合与组合：连续逐元素链
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ops-design-paradigms/references/paradigms/reduction/generic/liveness-fusion.md
  original_path: ops/ops-design-paradigms/references/paradigms/reduction/generic/liveness-fusion.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 111
  sha256: sha256:08f91ab6c5846b60435aa9e70fed185f0947718604320544a99dbd8132ba8477
  excerpt_sha256: sha256:08f91ab6c5846b60435aa9e70fed185f0947718604320544a99dbd8132ba8477
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/arch35/ub_resident_design.md
  original_path: ops/ascendc-performance-best-practices/references/common/arch35/ub_resident_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 164
  sha256: sha256:d097c7e2d7cd4b5473dfe5fb52a6c9bd05e71df8d15389545f1c2ff7c68dde78
  excerpt_sha256: sha256:bd5f506785fb6069884d0d36e9af924ab458d24f12e1647272569eb666e787b2
learning: {}
tags:
- fusion
- composition
- liveness
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.under-fusion
references:
- planning.under-fusion.fallback
- planning.under-fusion.reduce_broadcast
- planning.under-fusion.epilogue
evidence_status: source_reviewed_not_benchmarked
---

# 融合与组合：连续逐元素链

## 从计算图确定边界

用于 `y=f_m(...f_2(f_1(x),p_2)...,p_m)` 的逐元素或可局部广播链。先列出每个中间值的 dtype、舍入位置、所有消费者、别名及可见输出。只有同一输出分区内可完成所有依赖，才能由一个 task 负责该 tile 的整条链；跨行统计、跨核更新或外部消费者会增加阶段边界或需要保留中间结果。融合 kernel 边界、复用片上 buffer 和中间数据经过何种存储是三个独立决策。

顺序执行原算子中的 fp16/bf16 写回可能本身是一次舍入；移除 GM 写回不等于允许把整链提高到 fp32、合成 FMA、改变饱和/cast 或改变异常值传播。`cast_T(a*x)` 后再 `+b` 与 `cast_T(a*x+b)` 不自动等价。C2 必须写出保留哪些计算边界；若不满足精度契约，保留中间 cast，或在该处拆 kernel。

## 片上计划与所有权

每个 tile owner 搬入输入/参数、按原依赖完成算术链、只写自己负责的有效输出。常量参数可在多个本核 tile 间驻留，但常驻区会压缩主 tile 容量；多消费者中间值在最后一个消费者完成前不得覆写。维护“读者完成→失效→复用”的存活表；异步 MTE3 尚在读的输出 buffer 也算存活，不能仅以已发出写指令视为死亡。不同 task 不共享可变 UB；同一地址的原地更新只有 API 支持和跨 task 读写顺序均已证明才允许。

对每个合法融合边界比较：整链驻留、在峰值存活最高处拆成两段、保留独立算子。参数较大时比较每 tile 重载与分块驻留；无需创造固定链长阈值。来源的 arch35 bank/寄存器规则仅能按该架构使用，本条只复用其生命周期分析方法，不据此给 dav-2201 安排 padding 或假定寄存器融合 API。

## 容量与流量

令 `A(n)=ceil(n/a)*a`（字节对齐 a）、b_j 为中间值 j 的计算字节宽、t_j 为其 tile 元素数、q_j 为并存分配份数。`U_peak=max_phase(Σ_live_j q_j*A(t_j*b_j)+Tmp_phase)+U_resident+F≤U_available`。输入输出双缓冲份数来自实际流水，不能无条件取 2；API 不允许 in-place 时源/目的要同时计入。workspace 只在跨 task/跨 kernel 保留值时另计峰值。

若中间 j 在基线中恰写 GM 一次、被本链读一次，且没有外部消费者、在融合版完全片上保留，则可消去的理论 GM 流量为 `2*t_j*b_storage_j`；多消费者读数、外部可见输出、spill、GM 中转和额外参数重载应逐项重算。仅合并启动但仍经 GM 交接时该项为零，不能宣称必然省 GM。时间候选包含启动、实际 DMA、计算、等待和更高 UB 占用造成的 tile 数变化，不套用来源历史收益。

```text
冻结每一步 dtype/cast 与全部消费者
对每个候选 kernel 边界做 live-byte trace；选容量可行的 tile
for 每个唯一输出 tile:
    搬入输入与需要的参数；等待就绪
    按依赖执行算术与必要 cast
    每个值的最后读者完成后回收其空间
    写有效输出及必须保留的中间输出；等待异步读者结束后复用
```

```cpp
// 已声明的同长度 LocalTensor；展示顺序，不代表可省略原算子的 cast。
AscendC::Muls(tmpLocal, xLocal, scale, validCount);
AscendC::PipeBarrier<PIPE_V>();
AscendC::Adds(outLocal, tmpLocal, bias, validCount);
```

片段非完整算子；具体 API 重载和队列依赖在目标 SDK 核验。涉及归约用 `planning.under-fusion.reduce_broadcast`，矩阵乘输出组合用 `planning.under-fusion.epilogue`。验证尾块、所有参数广播、输入输出别名、外部消费者、中间舍入边界、NaN/Inf/±0 和资源峰值。本条 scope all 是通用规划方法，未做硬件资格或性能验证。
