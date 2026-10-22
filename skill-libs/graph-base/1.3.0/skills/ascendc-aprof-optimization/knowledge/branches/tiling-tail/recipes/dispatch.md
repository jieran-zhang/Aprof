---
schema_version: aprof.knowledge-record/v1
id: implementation.tiling-tail.dispatch
kind: recipe
version: 1.2.0
status: active
title: 元数据分发与实现身份接线
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/elewise/patterns.md
  original_path: ops/ascendc-tiling-design/references/elewise/patterns.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 46
  sha256: sha256:8a1351ff5295af67a53383682a4264aca6a19a113a2cdb47158938f73bae0cec
  excerpt_sha256: sha256:8a1351ff5295af67a53383682a4264aca6a19a113a2cdb47158938f73bae0cec
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/Kernel-Tiling/TILING_KEY_IS.md
  original_path: docs/zh/api/SIMD-API/basic_api/Kernel-Tiling/TILING_KEY_IS.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 29
  - 109
  sha256: sha256:6aa47a2f6a12a5b0954fed6e93f3c0c2c25922b37849c866187a04f21560ee74
  excerpt_sha256: sha256:e7791334b8daf11cce11428c3b16682a4728599933f1d08a77dac28ef701fb7d
- path: skills/ascendc-aprof-optimization/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/activation/squared_relu/op_host/squared_relu_tiling.cpp
  original_path: activation/squared_relu/op_host/squared_relu_tiling.cpp
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 72
  - 118
  sha256: sha256:697c6defba0cef026c0f4a803516acf04e3addb7fd8eab135024febbd505d477
  excerpt_sha256: sha256:fe19b7c6810a6ebcaaff210bd0de23640f9d67a74a92d67dbf38b873868c7c9f
- path: skills/ascendc-aprof-optimization/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/activation/squared_relu/op_kernel/squared_relu.cpp
  original_path: activation/squared_relu/op_kernel/squared_relu.cpp
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 22
  - 46
  sha256: sha256:fec0dbec3c56df4d0351baa8c88deedf837558871a02491f0c425ad3ca33b6a8
  excerpt_sha256: sha256:832f0fb7e570d0a7409b25724c7d25d70f1b8a9e9d3ba7634c39c48d91507699
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/activation/squared_relu/op_host/squared_relu_tiling.cpp
  original_path: activation/squared_relu/op_host/squared_relu_tiling.cpp
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 1
  - 135
  sha256: sha256:697c6defba0cef026c0f4a803516acf04e3addb7fd8eab135024febbd505d477
  excerpt_sha256: sha256:697c6defba0cef026c0f4a803516acf04e3addb7fd8eab135024febbd505d477
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/activation/squared_relu/op_kernel/squared_relu.cpp
  original_path: activation/squared_relu/op_kernel/squared_relu.cpp
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 1
  - 47
  sha256: sha256:fec0dbec3c56df4d0351baa8c88deedf837558871a02491f0c425ad3ca33b6a8
  excerpt_sha256: sha256:fec0dbec3c56df4d0351baa8c88deedf837558871a02491f0c425ad3ca33b6a8
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/activation/squared_relu/op_kernel/squared_relu.h
  original_path: activation/squared_relu/op_kernel/squared_relu.h
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 1
  - 185
  sha256: sha256:3066b846cc664697da5682cdd37fca34ed947d017b83b995ae18897d37c6af35
  excerpt_sha256: sha256:3066b846cc664697da5682cdd37fca34ed947d017b83b995ae18897d37c6af35
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/posembedding/rotary_position_embedding/op_host/rope_interleaved_tiling.cpp
  original_path: posembedding/rotary_position_embedding/op_host/rope_interleaved_tiling.cpp
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 395
  sha256: sha256:0f2bac0d6cd52e57ef38976b7fb8205e3104f2e0ea26f3689f0be1dd0a09cec6
  excerpt_sha256: sha256:0f2bac0d6cd52e57ef38976b7fb8205e3104f2e0ea26f3689f0be1dd0a09cec6
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/posembedding/rotary_position_embedding/op_kernel/rotary_position_embedding.cpp
  original_path: posembedding/rotary_position_embedding/op_kernel/rotary_position_embedding.cpp
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 291
  sha256: sha256:5160d08c053ba32694df0c699d31ddc9b67a26d3ae4545f4fb9d6122efc3400e
  excerpt_sha256: sha256:5160d08c053ba32694df0c699d31ddc9b67a26d3ae4545f4fb9d6122efc3400e
learning: {}
tags:
- c2-contract
- dispatch-wiring
- entry-identity
seed_reason: 审读固定开源修订并提炼中文实现配方，保留既有 ID 语义；API 单位以实际 API 文档为准；未做目标 SDK 编译或 NPU 性能验证。
parent: implementation.tiling-tail
references:
- implementation.tiling-tail.fallback
- implementation.tiling-tail.valid-length
evidence_status: source_reviewed_not_benchmarked
---

# 将 C2 已选元数据条件、key 与 entry 接到真实实现

## 职责边界与输入

本条只负责实现C2已经选定并冻结的元数据条件、优先次序/互斥关系、稳定uint64 key、实际kernel entry和fallback接线。IMPLEMENT不得重新选择算法、发明新的shape/dtype阈值、创建新key含义或用测量case名补条件。若条件重叠、域未覆盖、key重复或entry缺失，应带证据回C2修正dispatch_plan；不能在这里悄悄“完善选择逻辑”。

所需输入包括C2 action/模板快照、每个工作负载group的真实元数据谓词和其平台/dtype/layout有效域、既定key→entry表、参数字段/单位、输出所有权、workspace约束与fallback域。只用运行时可获得的实际元数据；benchmark ID、case序号、文件名和上轮耗时都不是合法dispatch依据。shape无法在Host验证的属性不得无证据变成特化条件。

## 接线步骤

逐行抄核C2表，区分“运行时元数据选择”和“编译时架构/dtype可用实现”。保持表的原有条件与优先次序，Host实现相同选择器并写入其key，同时序列化该entry需要的tiling数据、blockDim和workspace。字段按entry实际读取顺序、大小和单位核验；例如同名tileSize若一侧为元素另一侧为字节，key一致也会错。

Kernel为每个已选key提供匹配的`TILING_KEY_IS`分支，并实际初始化/调用冻结entry；通用fallback也必须有自己的已选key。官方文档要求N条分支用N个`TILING_KEY_IS`表示，不能用一个裸`else`兜住未知key。文档还说明该宏暂不用于kernel直调工程；直调样例的SCENARIO/模板编译参数不能直接等同于本工程的运行时dispatch。

Host不应发出没有编译实现的key；不在已声明候选域时，按C2已选fallback条件发送其key。fallback也不支持该元数据则在Host按现有错误路径结束，不得随意送入某个最快或最通用名字的分支。Kernel不匹配任何key而静默返回同样不是有效fallback。

## 一个真实接线例与移植规则

来源`ops-nn/activation/squared_relu`现有Host根据输入dtype选`TILING_KEY_HALF/FLOAT/BFLOAT16`，然后`SetTilingKey`；其arch22 kernel已有key1→half、key2→float、key3→bfloat16的相应实例。这里仅用这一真实映射解释接线检查，不将它变成其他算子的选择计划或把三个数作为通用常量。

```text
审查C2已有表的每一行 r（不新增行或改变条件）:
    Host 在 r.condition 成立时产生 r.key
    Host 写出的每个tiling字段与 r.entry 的读取契约一致
    Kernel 已编译且仅以 TILING_KEY_IS(r.key) 接到 r.entry
    r.entry 对该行全部平台/dtype/layout和尾域可执行
    fallback 行也完成完全相同的四项核验
```

在实际Host上下文中，`selectedKey`类型为uint64_t，值只来自已核验的C2选择器，`context`为当前`gert::TilingContext*`，则接线调用为`context->SetTilingKey(selectedKey)`。这里不提供一个虚构`SelectBestKernel()`或新阈值函数。实际Kernel的字面量/编译常量key必须来自同一冻结表；对来源entry不能只保留函数声明而漏链接真实代码。

## 身份、容量与验证

实现改动后记录真实`implementation_source_hash`、实际entry/编译分支和所用知识条目版本；`plan_basis_source_hash`仍绑定原分析源码，不能把它改成候选hash来掩盖计划偏离。若只调tile参数，仍须在C2自由度范围内；参数改变引起workspace、blockDim、queue槽、对齐字节和存活期变化要同步实现，不能只改Host字段。

Dispatch逻辑本身通常只增加少量Host元数据检查，不能通过运行多个kernel再挑最快结果选择；每条已选entry的UB/GM workspace均按其真实分支计入，可能同时存在的workspace按完整生命周期求峰值。fallback通常需要更广的边界处理，但其容量不能凭候选分支证明。

验证每个合法key可到达且有唯一实际entry，覆盖谓词各边界前/等/后、所有dtype/layout、未知shape的已声明fallback、错误元数据和缺省值。对原计划证明的互斥/优先关系做同域检查；观察实际执行kernel/分支身份与Host所写key吻合，再运行原oracle全域和同协议性能。若计划选中特化而执行旧entry、未知域误入fallback或更改key后结果未变化，先核查构建、链接和tiling数据，而不是继续调整阈值。

来源事实：官方TILING_KEY_IS文档定义Host key到Kernel分支的契约及无裸else限制；SquaredRelu给出实际dtype-key-entry配对。C2与IMPLEMENT职责、源码身份和计划符合性要求属于本知识树的工程契约；没有从该来源算法生成新的C2选择策略，未做目标工程构建/NPU验证。

## 进入本条前：分派不是性能目标

先由C1/C2比较通用骨架及其参数化是否能覆盖目标域。只有不同语义、API能力、算法结构或资源需求确实要求不同实现，或通用改进后仍存在可解释的不适用域，才形成dispatch计划。通常先改善主要通用路径；dtype或硬件能力天然不同的实现不必等待“多数case已优化”。没有新增入口的方案同样是合法甚至更好的结果。

分域说明必须回答：哪个机制或合法性条件不同，单一/参数化方案为何不足，子域由哪些运行时元数据可判定，未覆盖输入去哪里，新增代码/编译体/验证矩阵和维护成本是多少。测试case数、某一批已测赢家或人工命名不是分域依据；测得边界只能形成待解释假设，不能直接写成生产阈值。当前收益unknown不否定已有合法算法域，但也不构成加Key理由。

固定SquaredRelu的Host与kernel按dtype映射入口，这是接口/类型路径的真实实例，不是“增加三个Key能加速”的证据。RoPE的Host根据形状、dtype转换区和UB可容纳范围选择分块，再由entry映射对应类，说明应先有资源/算法计划再接key；其具体阈值和key数不复制为通用策略。每次R2出现局部回归，先重新比较访存顺序、活跃状态、同步和任务覆盖，不默认通过隔离回归case修复。
