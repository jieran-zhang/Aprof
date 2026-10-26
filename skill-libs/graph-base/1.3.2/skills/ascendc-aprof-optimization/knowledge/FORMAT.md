# 知识树格式与维护

本树与另一角色知识树共用 [knowledge-record schema](../../../schemas/knowledge-record.schema.json) 的身份、版本、适用域、来源和学习字段，分别版本化。一个条目一个 Markdown，中文正文按需读取。入口 [ROUTER.md](ROUTER.md)，全量初值见 [../../../workflows/references/development-records.md#skills-1-3-2](../../../workflows/references/development-records.md#skills-1-3-2)，来源及许可见 [NOTICE.md](NOTICE.md)。

| 字段 | 定义 |
| --- | --- |
| schema_version / id / kind / version / status / title | 格式版本、稳定英文 ID、类型、语义版本、active/deprecated、中文标题 |
| scope | platforms/workloads/dtypes；all 只表示检索不限，不证明平台支持 |
| sources | path、original_path、固定 revision、lines 闭区间、文件 sha256、片段 excerpt_sha256；运行不依赖上游仓库 |
| learning / seed_reason / tags | 叶条目初始 learning={}；身份可训练替换；路由权重在 routes 中。理由必须具体 |
| parent | 唯一主归属 ID；仅根 router 为 null |
| references | 同一树内跨分支复用 ID；不形成第二父节点 |
| evidence_status | source_reviewed_not_benchmarked，历史案例另保留原状态/协议 |
| routes | 只在 router 中维护 target、match、exclude、required_evidence、prior_score、fallback、seed_reason |

kind 可为 router、strategy、template、recipe、example。router 子路由覆盖其全部直属条目，父子无环，每条目只有一个主归属。跨分支只通过 references 复用。一个任务可以同时进入多个分支；同分按 ID，默认确定性路由。

match/exclude 条件为 `{field, op, value}`，字段取 attributes，op 为 eq/contains/in；match 全部满足、exclude 没有命中才进入。条件字段缺失不假设匹配。required_evidence 从 facts 取真值；未知/false/proxy 均返回 needs_evidence，不能静默授权执行。

prior_score：3=明确适用且可直接比较；2=条件性资源/成本取舍；1=探索或历史参照；通用 fallback=0，每个 router 恰有一条，仅在没有普通分支匹配时使用。路径分数为各层 prior_score 之和，不能比较不同树的分数或解释为性能收益。

## 叶条目要求

planning 的 template/strategy 给出适用域、算法骨架、任务所有权、归约/同步、容量与成本公式、参数空间、替代方案、fallback、证据状态及关键代码。模板不是完整工程，API/平台能力仍须核实。

optimization 的 recipe 给出适用条件、步骤、关键代码、验证和失败特征，保持 C2 语义与所有权。example 保留原硬件/协议/范围、成功和失败，不迁移性能资格。

## 扩展与训练

新增条目先固定来源、许可证和修改说明；检查现有同义项，选唯一主归属并在父 router 增加路由。平台常数和经验阈值必须带适用条件。执行 `tools/aprofctl knowledge build --root <包> --owner <角色>`，再 validate，审阅生成的 index.json 和初始化报告。

构建产物带全部 Markdown hash、生成器 hash 和 schema hash，相同输入字节产生相同结果。索引包含正文快照，运行时根据命中路径点读；sources 是冻结档案，不是另一套 router。

`aprof.knowledge-override/v1` 绑定 version 和 base_hash；parameters 中 router ID 的值是 `{target_id:新分数}`。只允许覆盖现有非 fallback 路由；值须有限非负；不能覆盖树结构或跨版本使用。内容/结构变更通过新版本构建。本轮只提供加载、校验、路由记录及结果关联，不自动训练。

## 当前格式示例

完整根记录直接见 [ROUTER.md](ROUTER.md)，其 `routes` 覆盖当前所有一级分类。避免维护第二份容易与实际树分叉的完整 YAML；叶条目从本树已有 template/recipe 复制 frontmatter 后更改身份、来源和适用域。记录字段保持上述 schema，方法正文遵守本节要求。

知识区的版本与 owner 在 REGION.json 维护，记录在构建来源 hash 中；变更知识版本时保留已冻结版本，覆盖参数不可跨 hash 使用。

输入片保留方法另用 `constraint.same_input_region` 检查消费者的地址集合、布局、dtype 和有效尾域，用 `constraint.input_value_preserved` 检查原值在最后读完成前不被 in-place、别名写入或 producer 更新破坏；两者不能由 `reuse_domain`、Action 名称或缓存命中率推断。这些方法谓词按现有 facts 映射扩展，无需修改解析器枚举。C2 尚无这类事实时保留 unknown；补证据后形成新的 Context／推理／交接快照。

## 1.3.0 中文内容与自包含要求

正文按“来源明确描述 / 源码直接确认 / 本次归纳”标明事实层次；必要公式解释符号、单位和适用域。原始工程变量先抽象成方法参数，不复制固定核数、容量和未经校准的阈值。片段声明输入布局、有效元素、临时区与同步边界，不保留上游私有 include/工具函数的隐含依赖。来源档案可保留原语言与许可，但使用说明优先中文。

同一树内 references 只能引用已存在的 ID；跨角色通过 C2 必要内容快照衔接，不增加跨树 ID 引用。来源位于本 skill 的 sources/仓库/固定修订/原路径，必须是真实文件，不是符号链接；同名上游文件的新修订不覆盖旧来源。新说明写在 README/FORMAT 或 workflow 引用文档，不能在知识区放无 frontmatter 的普通 Markdown。

新增路由复用现有 facts，不改 schema。以下 constraint 名称表示本次任务有原始依据的检查事实，而不是新的 profiling 症状：

| fact | 检查含义 |
| --- | --- |
| constraint.target_api | 当前 SDK/SoC 支持正文使用的 API、重载及单位 |
| constraint.invariant_scope | 外提或常量缓存值在相应循环/调用域内确实不变 |
| constraint.duplicate_index_semantics | 唯一/重复目标、覆盖胜者与归约顺序已经明确 |
| constraint.index_mapping | 索引方向、范围、反向映射与有效行规则符合算子语义 |
| constraint.tiling_abi | Host 序列化布局、Kernel 读取类型/偏移及本次分派的 Tiling ABI 一致 |
| constraint.read_only_lifetime | Tiling/缓存元数据在声明的读取域内存活且不被异步修改 |
| constraint.static_layout_lifetime | 固定布局覆盖全部 dtype/layout/feature 分支，物理区间、峰值容量及复用完成边已证明 |
| constraint.static_dynamic_tiling | 常量化范围与实际 base/singleCore tiling 一致；部分常量、动态尾、batch 和 nullptr 契约各自保持。 |
| constraint.local_accumulation_lifetime | 同一输出 tile 的首片初始化/后片累加/bias 次数/尾 K/累加顺序及 L0A/B/C 完成边已证明。 |
| constraint.output_layout_stride | Fixpipe 源 NZ、目的 layout/stride/dtype、字段单位/范围、有效输出矩形和目的无重叠已证明。 |
| constraint.unitflag_pairing | unitFlag 关闭时保留原完成边；开启时 Mmad/Fixpipe 配对、计算方向、完整读写范围及标记复位均已证明。 |

已有 semantic_equivalence、capacity、task_ownership、plan_freedom、l1_l0_budget、precision、fusion_boundary、dependency_lifetime、workspace_ownership 和 cross_engine_dependencies 继续沿用。知识树只把全部已核验前提的条目标为 reference_ready；它不是执行授权或性能证明。只有 kernel 计数或利用率变化不能代替这些事实。

## Action请求与扩展

当前跨树使用[两阶段交接](../../../workflows/references/diagnosis-v4.md)：提示只缩小候选范围，本树router根据真实上下文选择。新family/branch不自动产生Action，新叶可进入检索，但采用前核对Action、目标、计划和方法前提。实际组合在选择后记录，旧交接保留原版本/hash。
