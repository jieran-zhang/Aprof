---
schema_version: aprof.knowledge-record/v1
id: planning.under-fusion.vector_producer_consumer
kind: template
version: 1.3.0
status: active
title: 一般Vector生产消费融合
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/posembedding/rotary_position_embedding/op_kernel/rotate_interleaved_split_bs.h
  original_path: posembedding/rotary_position_embedding/op_kernel/rotate_interleaved_split_bs.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 108
  - 225
  sha256: sha256:92e2365907ffbd499d113d173a67bd2ade41d1a92d82f3d20b3965eaad17b001
  excerpt_sha256: sha256:5b1c369c0cad17cfb39c00a5bd4d354ab55d80d8eb0c902d05007674a233af35
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ops-design-paradigms/references/paradigms/reduction/generic/liveness-fusion.md
  original_path: ops/ops-design-paradigms/references/paradigms/reduction/generic/liveness-fusion.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 111
  sha256: sha256:08f91ab6c5846b60435aa9e70fed185f0947718604320544a99dbd8132ba8477
  excerpt_sha256: sha256:08f91ab6c5846b60435aa9e70fed185f0947718604320544a99dbd8132ba8477
learning: {}
tags:
- execution-cost
seed_reason: 固定五仓库来源审读；通用方法为条件化机制推导，未做目标硬件验证。
parent: planning.under-fusion
references:
- planning.under-fusion.chain
- planning.indexing.coordinate_neighborhood
evidence_status: mechanism_inference_from_reviewed_source_not_benchmarked
---
# 一般Vector生产者—消费者融合与中转取舍

本条使用既有under-fusion分类，覆盖生成坐标/系数/索引、局部变换、普通Vector链、加权邻域消费及必要局部归约；不要求存在MatMul、FA或归约广播模式。固定来源直接给出存活期融合方法与RoPE生成Gather偏移后在循环中反复消费；一般生产消费骨架为本次机制推导，不提供任意采样数学公式或通用API。

先列有向数据流 `producer -> value(dtype,layout) -> 全部consumers`，标注外部可见输出、别名、Cast/舍入边界、每个consumer的owner和读取结束事件。只有生产者与消费者可由同一合法owner完成且依赖闭合时，才在同一kernel按tile局部生产/消费。消费者跨task/核、输出外部可见或容量不够时，保留GM中转或拆阶段；不能因合并启动就宣称省GM，也不能为省中转删除后继消费者。

比较四类实际候选：每消费者重算；同owner生成一次并驻留；先写GM派生表供多消费者；在一个kernel保留完整生产消费链。它们不是互斥标签，需分别列生成、布局准备、存储位置与依赖。例如复用坐标可同时融合消费，但原始输入仍须按通道读取。

对Q条派生记录、r消费者、记录s字节：重算r*G(Q)；片上保存G(Q)+r次本地读且新增A(Q*s)活跃状态；GM表至少写Q*s和r次读Q*s（缓存后的实际DRAM字节另论），再计发布/等待及workspace；融合消除每个内部值原GM写一次和读r次时，理论省(1+r)*Q*s，但仍有外部消费者、spill或布局中转则逐项扣回。G是分类型逻辑操作数量而非时间。布局准备P(Q)、对齐/打包/转置、索引宽化、初始化与API workspace都应按执行次数计入；准备仅当被多个消费者合法共享时才摊销，不能把它藏在Init而归零。

每个tile执行“获取输入→生成必要派生值→等待生产完成→按既定数值顺序消费→写全部有效输出→等最后异步读完成后回收”；累计值每个输出初始化一次、finalCast按原边界执行，局部小加权和也需precision-boundaries.numeric。改变融合边界、owner、task或GM通路须C2确认；同一计划已授权范围的API/布局选择可留C3。容量用各phase同时存活的真实槽和API临时区高水位，扩大复用轴可能减少task、缩tile或破坏overlap。

选择先判断哪种工作影响主要域，再比较启动/逻辑计算/中转/布局/存活与任务，不以少kernel、少API或最小patch直接判赢家；完整机制可联合变更，归因需要时才做单因素消融。R2把实际变化与预测、剩余逐元素工作和未覆盖域逐项对照。API按目标SDK的Vector/Cast/Gather/搬运路径核验，arch35寄存器/bank与950直通能力不能迁到A3。缺口：没有通用插值实现、目标编译和硬件收益，源代码数值链不能替代当前oracle。
