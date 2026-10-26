# 并行规划知识树 v0002

从 [算子族与模式入口](ROUTER.md) 按需读取；[格式](FORMAT.md)、[来源](NOTICE.md) 和 [初值](INITIALIZATION.md) 解释维护方式。数学方法、选择条件和关键伪代码在条目正文中完整给出，使用者不需要打开原始仓库或 sources 才能理解方案。

## 如何选择

| 输入形态 | family | C2 需要比较的核心问题 |
| --- | --- | --- |
| 连续逐元素、广播 | elementwise | 输出区间、广播复用和小任务成本 |
| 归约、Norm、Softmax | reduction | 行 owner、完整加载/分段、partial 合并 |
| MatMul、GMM | matmul | MN、Split-K、StreamK、跨组调度和驻留 |
| Attention | flash-attention | 核间轴、S1/S2、在线状态与 Split-KV |
| Sort、TopK | sort-topk | 局部排序、归并扇入、比较与索引语义 |
| Transpose 等 | layout | 输出布局所有权、局部转置与容量 |
| Gather、索引更新 | indexing | 数据相关地址、重复目标与归约所有权 |
| MoE 路由和回收 | moe-routing | 阶段组合、索引映射、排序/Gather 与加权归约 |
| 可组合的计算链 | under-fusion | 叠加到上述族：融合边界、外部消费者和中间交换 |

family 是数组，可以同时进入多个分支。under-fusion 是融合与组合模式，不是已经成立的性能问题。方案来源的固定阈值与硬件常数只是实例，不能作为跨平台分派条件。只有当前任务的语义、容量和所需能力满足，才实例化模板。

## 使用与交接

每个条目解释适用形态、任务/输出所有权、归约同步、容量和成本、参数与替代方案。公式按字节记资源；伪代码表明依赖，Ascend C 片段说明局部契约，均不冒充完整已编译工程。

C2 比较方案后交出模板必要内容快照、实例参数和 implementation_freedom。跨角色不依赖知识目录互读；C3 接收快照即可实现。条件不齐保持 needs_evidence。当前只有来源审读，没有本版新增硬件性能验证。

Scan/Prefix、卷积各方向、窗口/池化列为待扩充内容，不用空模板替代实际资料。两树版本独立于包版本；本树 v0002 相比 1.2.0 的 v0001 只做知识和路由扩充。
