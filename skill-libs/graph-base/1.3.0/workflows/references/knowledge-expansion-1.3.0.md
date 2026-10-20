# 1.3.0 中文知识扩充

本版以1.2.0为基础，规划知识为v0002，实现知识为v0004，机制诊断为v0004，runtime为0.5.0。实现v0003在原v0002上补齐同owner输入片保留方法及Action路由，见[输入复用增量](input-reuse-1.3.0.md)；历史v0002保持冻结。诊断模板、任务推理及案例提案分层，见[诊断升级](diagnosis-v4.md)。本文说明分类、边界与来源使用方式；实际方法从两个 skill 的知识 router 按需读取。

## 阅读与交接

- C2 按算子 family 与组合模式选择方案，说明任务、所有权、归约、同步拓扑、workspace、通路与参数自由度。
- C3 接收 C2 的必要内容快照，在该自由度内选择实现技巧。涉及算法、所有权、归约顺序或全局数据交换方案的变化，交回协调者重规划。
- router 保持简短，template/recipe 解释完整方法，example 保存具体条件。主要正文归属唯一，同一树内使用 references 复用；跨角色通过交接快照传递，不能要求优化角色重读规划目录。
- 知识正文包含适用条件、必要数学、变量单位、关键片段与限制。原始来源仅供校验和追溯，不能用“参见上游”替代方案说明。

## 分类

planning 保留 elementwise、reduction、matmul、flash-attention、sort-topk、layout 与 under-fusion；under-fusion 的展示名称为“融合与组合模式”，是可与算法族同时命中的模式。新增 indexing 与 moe-routing；前者处理数据相关寻址及冲突语义，后者组织排序、索引映射、Gather 和加权回收，复用已有基础族。

optimization 保留 tiling-tail、memory-transfer、buffer-lifetime、pipeline-sync、vector-api、precision-boundaries；新增 cube-api、scalar-control、fusion-composition。precision-boundaries 是公共数值与有效域约束。缓存策略、预取、多缓冲和 Bank 布局作为相应分支的技巧，不再各建一级分类。

| 兼容与分化 | 本版处理 |
| --- | --- |
| `planning.matmul.splitk` | 保留静态 Split-K 原义；另建 `planning.matmul.streamk`，不把两种调度合并 |
| `planning.matmul.gmm` | 组间/组内任务与地址映射独立说明，复用 MN 与归并原则 |
| `planning.under-fusion` | 保留 ID，展示为“融合与组合模式”，可以与基础算子族同时进入 |
| `implementation.vector-api.cast-control` | 保留路径与旧义兼容摘要，标为 deprecated；转换正文归新 `implementation.vector-api.cast`，循环/地址/常量控制归 `scalar-control` |
| 搬运、UB、流水与融合 | 数据移动、物理分配、完成顺序与计算组合分别有唯一主正文，通过同树 references 组合 |

旧 family/features 仍使用原 token。新入口由 `family` 中的 `indexing`、`moe-routing`，及 `features` 中的 `cube-api`、`scalar-control`、`fusion-composition` 选择。StreamK 和 GMM 另需 `features` 中的 `streamk_schedule`、`grouped_matmul`，避免仅因是 matmul 就默认推荐特殊调度。

融合知识区分三个维度：计算阶段怎样组合、数据怎样交换、不同 tile 怎样重叠。融合成一个 kernel 不保证消除 GM 中间读写；A3/2201 与 950/3510 的通路和 API 不能互换。局部事件生命周期归 pipeline-sync，buffer 复用归 buffer-lifetime，组合与交接由 fusion-composition 承接。

## 来源与事实边界

固定来源见 [来源身份](knowledge-sources-1.3.0.json)。五个仓库的相关完整文件与许可保存在各知识区 sources 的仓库/commit 子目录；sources.path 为包内相对路径，原 URL 仅作归属。相同文件在不同角色中引用时具有相同修订与字节身份，不能算作独立实验。

正文区分“来源明确描述”“源码直接确认”“本次归纳”。所有新增条目只完成来源审读，保持 source_reviewed_not_benchmarked。通用的任务/数学方法不自动证明每种硬件上的 API 可用；平台能力、SDK 条件、精度和容量仍须按任务核验，未知条件不填成已满足。

`dav-2201`、`dav-3510` 是路由使用的架构标识；产品名和编译分支不是一次实际运行的证明。架构范围命中后仍需核验具体 SoC/SDK/feature。尤其 `all` 表示可检索通用方法，不能把来源里的 950 示例授权为 910C 实现；StreamK 的目标实现事实单独设门禁。

正常环境使用包自带 runtime 与工具链适配。技能包不链接上游目录，不依赖下载目录、源码子模块或其他版本目录。片段是解释契约和局部实现的方法，不冒充已经在目标 SDK 编译过的完整工程。

## 覆盖与遗留问题

本版覆盖与条目清单由 [覆盖记录](knowledge-coverage-1.3.0.json) 给出；结构与独立目录检查见 [检查结果](knowledge-validation-1.3.0.json)。后者只记录 CPU 结构、路由、来源与自包含性，不是性能或发布验收。

Scan/Prefix 的前缀依赖、卷积各方向与窗口/池化方法是后续覆盖缺口；本版不建立空入口。950 RegBase/VF、SIMT 或片上 CV 通路的原理可作受限参考，不能转换为 910C 的实现资格。本轮逐项审查旧SPA并补条件化机制关系；缺少profiling依据的关联保留预测。参数训练和硬件对照实验不在本轮范围。
