---
schema_version: aprof.knowledge-record/v1
id: implementation.buffer-lifetime.derived-results
kind: recipe
version: 1.3.0
status: active
title: 派生结果生成一次多次消费
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/posembedding/rotary_position_embedding/op_kernel/rotate_interleaved_split_bs.h
  original_path: posembedding/rotary_position_embedding/op_kernel/rotate_interleaved_split_bs.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 108
  - 225
  sha256: sha256:92e2365907ffbd499d113d173a67bd2ade41d1a92d82f3d20b3965eaad17b001
  excerpt_sha256: sha256:5b1c369c0cad17cfb39c00a5bd4d354ab55d80d8eb0c902d05007674a233af35
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/arch35/ub_resident_design.md
  original_path: ops/ascendc-performance-best-practices/references/common/arch35/ub_resident_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 19
  - 46
  sha256: sha256:d097c7e2d7cd4b5473dfe5fb52a6c9bd05e71df8d15389545f1c2ff7c68dde78
  excerpt_sha256: sha256:d3920eeb4b4de9e9825bed4b1e64aa0dd2873d63403e80f09d69a444c98339bd
learning: {}
tags:
- execution-cost
seed_reason: 固定五仓库来源审读；通用方法为条件化机制推导，未做目标硬件验证。
parent: implementation.buffer-lifetime
references:
- implementation.buffer-lifetime.reuse
- implementation.memory-transfer.cache-hint
evidence_status: mechanism_inference_from_reviewed_source_not_benchmarked
---
# 派生坐标、系数与索引生成一次并多次消费

## 对象、方法与安全条件

对象是由输入和元数据计算出的坐标、权重、Gather偏移、转换参数或局部统计，不是原始输入切片，也不是只改地址前缀的控制外提。先记录 `D=G(inputs,metadata)` 的全部依赖轴、dtype/舍入、有效域、生成者、每个消费者及最后完成点。只在窗口内所有依赖不变且生成次数/可见副作用可合并时生成一次；依赖某轴时不得跨该轴复用。随机状态、原子更新、时变输入、异常行为与外部可见写不能按纯函数处理。

固定RoPE源码在Process进入seq/batch循环前通过SetGatherSrcOffset产生Gather偏移，ReinterpretCast为uint32_t视图并供Compute/ComputeCastFp32反复消费；InitBuffer按bufferNdSize*sizeof(int32_t)分配。它证明此RoPE变体存在派生索引复用，不证明任意插值/采样的坐标与权重数值等价。通用方法是本次机制推导，具体计算API及平台能力逐项核验。

1. 对每个候选复用轴列明生成位置、消费者集合和原重算次数r。只在所有依赖与语义边界一致的窗口中移动生成位置；必要的Cast仍保留在原数值边界。
2. 同owner在UB/TBuf保存Q个记录；容量至少A(Q*s)，再加mask、offset、API临时区和实际槽数。若存Scalar数组，单列编译后寄存器/栈/spill未知，不能声称不花UB就免费。
3. 每个消费者都结束后才覆盖；跨核或跨kernel共享改为GM表时，生产者唯一写、发布完成、消费者只读及最后读取完成都须明确，返回C2确认通路/owner/workspace。
4. 比较重算、小tile局部保存、扩大复用轴和GM表；布局转换/打包/初始化属于准备成本，不能归零。几何复用不减少依赖通道的原始输入值读取。

## 性能假设与代价

原生成逻辑量为r*G(Q)，保存版为G(Q)加r次派生记录读取；节省(r-1)*G(Q)是逻辑工作预测，不是时间。GM表另有写Q*s与r次读Q*s的逻辑流量及发布等待；布局准备加P(Q)，一次性预处理与每tile准备分别计数。保存延长活跃状态，可能缩小tile、减少任务/流水槽或增加离散取数，编译器也可能已消除重算。主导成本不是派生生成时，收益可能很小或反转。

选择前与输入复用、必要逐元素工作、融合消除中转等主要机会比较。可将不可分割的生成位置+存储+完成边作为一个可解释机制候选；单因素用于归因或调试，不能强制把合法完整方案拆成互相不成立的片段。R2核对实际patch的生成次数、存活峰值、布局/GM字节和残余消费者，按反馈保留、缩窗、重算或退回。

## 平台与缺口

本意图的数学依赖分析可跨平台检索；具体RoPE仅支持其源代码分派、布局及dtype，Gather/ReinterpretCast/InitBuffer的目标SDK重载须核验。没有GridSampler完整链、通用插值阈值、目标SDK编译、寄存器分配或目标硬件收益证据。实现安全未知阻断实施；性能预测未知记录决策影响，不自动否决合法试验。
