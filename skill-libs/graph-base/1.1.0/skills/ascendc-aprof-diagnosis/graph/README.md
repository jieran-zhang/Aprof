# 诊断图 v0003

本区是 diagnosis 唯一活动 router。入口 [GRAPH.md](GRAPH.md) 从独立证据特征指向性能机制，再指向优化变换；细节在各自节点 Markdown。格式与扩展见 [FORMAT.md](FORMAT.md)，全量初值见 [INITIALIZATION.md](INITIALIZATION.md)。

- symptoms：独立可核验的 source / workload / profile 特征。
- problems：具体性能机制；旧六类问题族改为非互斥 tags。
- actions：可检验变换、前提与不变量；不在图里维护方案实例或实现模板。
- edges：supports、refutes、mitigated_by 及适用条件、1/2/3 初值与来源。边的唯一维护位置。
- versions/v0003：由 Markdown 确定性构建的机器快照。覆盖参数必须绑定版本及 hash。
- history：逐字保存旧图 v0001/v0002、旧 source、provenance 和 registry；只供历史回放，不参与当前路由。

源码、矩阵和优化策略的逐项去向见 [迁移清单](../../../workflows/migration/README.md)。旧 NOOP、规划选择和补采移至 workflow；unknown、measurement_limited、workload_limited 是诊断状态。容量超限、越界、同步错误归入实现约束，不当作已经成立的性能问题。

缺失字段、未知硬件分母、未实现 extractor 保持 unknown。允许带可回查原始引用的人工证据标注；模拟证据标记 proxy，不能激活动作硬前提。C1 带动作快照给 planning；后续角色不必读本目录。
