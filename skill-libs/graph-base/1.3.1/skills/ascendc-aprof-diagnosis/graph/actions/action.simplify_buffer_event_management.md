---
schema_version: aprof.diagnosis-record/v1
id: action.simplify_buffer_event_management
kind: action
version: 1.3.0
status: active
title: 简化buffer与事件管理并保留完成边
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/00_vector_compute/add_high_performance/add.asc
  original_path: examples/01_simd_cpp_api/05_best_practices/00_vector_compute/add_high_performance/add.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 188
  - 240
  sha256: sha256:f7d075958365a8fc1af9879e90ab6494573f8869d3a538832c537d8e0f905042
  excerpt_sha256: sha256:bad0e51c0dcd8e89f7d4afe871429a68f343e8375237fb5a83500ea9b0f65f2b
- path: skills/ascendc-aprof-diagnosis/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/data_structures/LocalTensor/LocalTensor_constructor.md
  original_path: docs/zh/api/SIMD-API/basic_api/data_structures/LocalTensor/LocalTensor_constructor.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 296
  sha256: sha256:103ec2d4324f59620a49df8b4ddaec36c81552c1a5a850233177ecec77a34946
  excerpt_sha256: sha256:103ec2d4324f59620a49df8b4ddaec36c81552c1a5a850233177ecec77a34946
- path: skills/ascendc-aprof-diagnosis/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/intra_core_sync/SetFlag_WaitFlag_ISASI.md
  original_path: docs/zh/api/SIMD-API/basic_api/sync_control/intra_core_sync/SetFlag_WaitFlag_ISASI.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 124
  sha256: sha256:dada622bc1f47bcdbb58acd765bd1d596bcaa14b0b8143a4d5f4f17ed6f929fe
  excerpt_sha256: sha256:dada622bc1f47bcdbb58acd765bd1d596bcaa14b0b8143a4d5f4f17ed6f929fe
learning:
  bias: 0
tags:
- execution-cost
- simplify-buffer-event-management
seed_reason: 固定五仓库来源审读与机制推导；独立复核通过前仅工作稿，不继承旧Action语义。
transformation: 简化buffer与事件管理并保留完成边
preconditions:
- fact: constraint.semantic_equivalence
  state: true
- fact: constraint.capacity
  state: true
- fact: constraint.static_buffer_event_domain
  state: true
- fact: constraint.dependency_lifetime
  state: true
- fact: constraint.target_api
  state: true
invariants:
- 完整语义和精度
- 有效元素覆盖和唯一写回
- 容量、同步与所有权合法
expected_effect: 仅性能假设：减少动态管理的可能Scalar工作，静态状态、分支、事件与收尾成本可能抵消，不能按API数量推性能。
slots:
- name: target
  kind: object
  description: 动态管理对象、物理地址区间、槽与事件所有权
  required: true
- name: stage
  kind: stage
  description: 初始化、稳态、主尾、最后完成及收尾
  required: true
- name: workload
  kind: workload
  description: 绑定shape、dtype、layout、feature与有效元素域，不跨workload借证据
  required: true
- name: implementation
  kind: implementation
  description: 绑定当前parent源码、host/tiling/kernel、编译配置或artifact身份
  required: true
claims:
- id: direct_source
  text: 静态Add的LocalTensor视图、四类HardEvent完成边与退出drain构成同核双缓冲协议。
  basis: code_fact
  source_indexes:
  - 0
  review_status: reviewed
  limitations:
  - 只证明固定源码事实，不证明任意算子或目标硬件收益。
- id: method
  text: 简化buffer与事件管理并保留完成边；减少动态管理的可能Scalar工作，静态状态、分支、事件与收尾成本可能抵消，不能按API数量推性能。
  basis: mechanism_inference
  source_indexes:
  - 0
  - 1
  - 2
  review_status: reviewed
  limitations:
  - 通用方法是本次机制推导，独立复核后才最终注册；无目标硬件因果验证。
review:
  state: reviewed_with_limits
  source_credibility: 固定五仓库修订中的源码/API；保留LICENSE、完整文件及行hash。
  discriminating_power: 比较明确重复生成/管理工作与新增存活、准备、同步和覆盖域；不是由名称判断热点。
  observed_frequency: unknown
  gaps:
  - 未做目标SDK编译、NPU异步正确性或性能试验。
  - 已独立复核来源、语义与准入边界；尚无目标SDK编译或硬件收益验证。
instantiation:
  target_slots:
  - target
  - stage
  - workload
  - implementation
  required_bindings:
  - target
  - stage
  - workload
  - implementation
  effect: 简化buffer与事件管理并保留完成边
  costs:
  - 减少动态管理的可能Scalar工作，静态状态、分支、事件与收尾成本可能抵消，不能按API数量推性能。
  unknown_policy: 逐项证明安全与结构条件；性能假设独立比较，不以管理API数或逻辑工作减少承诺速度。超出C2自由度必须返回规划。
  replan_triggers:
  - 目标/阶段、owner或有效元素域变化
  - 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
  - 工作量、dtype、平台、容量或profile反证使原干预假设失效
---
# 普通Vector静态buffer租约与事件闭环

## 对象与准入

用于同核普通Vector的固定地址/固定槽布局，把反复动态分配、队列状态或事件领取管理改为初始化一次的TBuf或公共LocalTensor静态视图，并保留全部数据完成依赖。对象是管理表达，不是取消真实同步、跨核发布或把少queue/API当作速度证明。TQue、TBuf加事件与静态Tensor都可合法；按动态shape/feature、地址、存活、目标SDK与实际成本选择，不固定TQue优先。

`LocalTensor<T>(TPosition::VECCALC, offsetBytes, sizeElements)`只构造视图，不替调用者分配/检查内存。先列 `[offsetBytes,offsetBytes+A(sizeElements*sizeof(T)))` 的全量租约表，包含所有输入/输出/临时区、ping/pong、padding和API workspace；核验同一物理存储区、地址单位、对齐、上界以及全部dtype/主尾/feature路径。复用区间必须由最后读完成→下次写开始连接；动态tile或分支无法证明时保留受管理方案。不能与TPipe分配器在同一地址域各自声称所有权。

## 单槽到多槽的完整协议

每个槽维护INPUT_FREE、INPUT_READY、OUTPUT_FREE、OUTPUT_READY四类逻辑边：

| 边 | 源完成后发布 | 下一消费者等待 | 保证 |
|---|---|---|---|
| 输入可覆盖 | V_MTE2 | 下轮MTE2 | 上轮Vector已读完输入 |
| 输入已就绪 | MTE2_V | 本轮Vector | DMA写入完成 |
| 输出可覆盖 | MTE3_V | 下轮Vector | 上轮DMA已读完输出 |
| 输出已就绪 | V_MTE3 | 本轮MTE3 | Vector写入完成 |

首次使用输入/输出槽时，空闲token由初始化发布一次或用已证明的首轮免等分支；不对尚未产生的token Wait。每轮先等输入可覆盖、发CopyIn，再发布并等待输入就绪；等输出可覆盖后计算，计算结束发布输入可覆盖与输出就绪；搬出结束发布输出可覆盖。使用s=i%q独立事件对每槽记账；同一event/ID未被Wait消费前不得再次Set，不能用会丢代次的重复Set代替计数器。无任务路径不等待未发布事件；尾tile沿原合法DataCopyPad/有效长度与mask，不能直接套主块DataCopy。

循环结束按“已发布且尚未消费的token”排空，不能按槽是否做过工作推断状态。若初始化为全部q槽各发布输入/输出空闲token，即使0个tile或只有1个tile，未用槽的初始化token也必须各Wait一次；已用槽最后的输入可覆盖与输出可覆盖token也须消费。若采用按需初始化或首轮免等，只排空真正发布且未消费的token，从未发布者不可Wait。完成所有最后读依赖、消费遗留token后才释放事件、返回或转交arena，确保重复调用不会对旧token再次Set。固定Add双缓冲源码用两个事件ID初始化空闲token、按奇偶选择槽、最后四次Wait完成回收；这是同核依赖例子，不是FA的跨AIC/AIV workspace槽协议。

## API/平台与事件所有权

固定LocalTensor构造表支持A2/A3的C++ Tensor范式；SetFlag/WaitFlag(ISASI)在A2/A3支持但不保证跨硬件版本兼容。HardEvent方向和ID必须完全配对，Set不阻塞源流水，Wait消费并清零标志。静态范式开发者管理ID，文档建议0–5，6/7暂不直接用；TPipe/TQue范式必须通过AllocEventID或FetchEventID取得，不能把静态ID硬塞进受管理事件池。与库算子混用时还须证明事件/地址不冲突；需要兼容抽象时按目标SDK评估TQueSync。跨核同步仍用原合法CrossCore协议，本配方不适用跨核slot发布。

## 性能选择、验证与回退

预算原动态管理次数、Scalar控制/地址工作与新增分支/初始化/收尾次数、真实UB分配、事件占用及失去的overlap。管理API减少只证明源码表达变化；编译器内联/消除、静态状态增加、保守等待和tile改变均可能抵消。可以整体比较保持同一数学、owner与完成关系的管理实现，再在有决策价值时做归因消融，不要求每次只改一行或一个因素。

检查0/1/q−1/q/q+1/多轮tile、主尾、奇偶末轮、全部feature/dtype、重复调用、事件占用冲突、并发live区间和退出drain。CPU状态模拟只检验配对/租约，目标SDK编译、NPU异步行为与性能未验证；不能从样例收益推目标阈值。失败恢复原TQue/TBuf协议和独立区，再定位地址、首次token、代次与最后读完成。
