---
name: ascendc-aprof-diagnosis
description: 从源码、workload 和 profile 证据沿 v0003 图诊断 Ascend C 性能机制，输出问题与优化方向、反证、缺项及 C1 动作快照。
---

# AProf 诊断

职责见 [diagnosis 角色](../../workflows/agents/diagnosis.md)，输入/输出见 [C1](../../workflows/contracts/diagnosis.md)。由 coordinator 传入 C0、实际父版本和已有 C4；补证据后创建新诊断实例。

唯一诊断入口是 [graph/GRAPH.md](graph/GRAPH.md)。按观测选择 symptom，沿 supports/refutes 找机制，沿 mitigated_by 提出动作；不再维护平行判断矩阵或固定六类 router。节点、边、分数及扩展规范见 [FORMAT](graph/FORMAT.md)。

把事实标为 source/profile/workload 渠道，附原始引用、单位、硬件分母和 evidence_id。同一观测不重复计分，unknown 不等于 false。未实现 extractor 保持该状态；有原始引用的人工核验可以标注事实，不能凭预期收益造 profile。模拟数据保留 proxy 标记。

运行包内 `knowledge route --root <包> --owner diagnosis --context <evidence.json>`；也可用 graph route 的 v0003 入口。C1 保存图版本/hash、匹配证据、问题/动作排序、缺项、候选 action 的必要内容快照和反证。planning 接收快照，不读取图目录。

unknown / measurement_limited / workload_limited 是诊断状态；NOOP、补采、重规划由协调者决定。缺前提的动作是待验证方向，不能成为 executable。补采需求写指标/单位、case、实现、后端和能区分的假设；通过 coordinator 调 profiling。API 或分母不清时调用 ascendc-docs-search、tool-npu-compute，架构变化交 coordinator/npu-arch。

本角色不选具体算法模板、不写候选、不裁决性能。历史图只按原版本回放，旧 logit/行为概率不能套进当前排序。
