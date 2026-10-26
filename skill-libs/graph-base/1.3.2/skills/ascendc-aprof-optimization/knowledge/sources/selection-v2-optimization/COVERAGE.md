# O 知识补强来源与覆盖表

状态：正文和包内来源已完成；公共 router、REGION、冻结树和版本由主 Agent 集成。仅 CPU 源码/引用/容量检查；没有 SDK 编译或新的硬件实验。

## 已有资料没接好，还是知识真缺口

| 现有条目 | 可用内容及问题 | 本次结果 | 代表来源 |
|---|---|---|---|
| vector-api/batch | 已有repeat/mask/stride、尾块与容量，但错误泛化count都能完整处理前n个元素 | 修正泛化；以指针链接新Compare/Select正文；补调用减少与初始化增加的比较 | asc-devkit Compare/Select 文档及dav_c220实现 |
| vector-api/compare-select-tail（新） | 原树缺少该API组合的独立适用、模式、尾部、内部scratch完整契约 | 新叶，A2/A3整256B、mask无效、predicate、Select模式和8KB，950差异、数值边界、短段代价 | asc-devkit d378849完整API文档与实现 |
| precision-boundaries/numeric | 已有特殊值，但未把三元选择与Max替换明确连接 | 加语义检查、链接新叶；不声称固定Max特殊值一定错误 | Compare、Select、Max |
| memory-transfer/strided-pad | 已有多行搬运、GM/UB stride单位与dummy；选择阶段未比较行组合/扁平连续/初始化 | 补短行布局两种空间公式、只初始化未定义读取域、物理边界证据；避免“所有尾写必须64B”的无据规则 | DataCopyPad两方向文档 |
| pipeline-sync/pipeline | 已有队列与真实事件，执行时“有queue”被误当充分 | 补tile×slot下发射/等待比较、符号化理想时间模型与限制、950样例不冒充910C | cannbot double_buffer；cann-samples RMSNormQuant host/kernel/CMake |
| pipeline-sync/slots | 有slot生命周期，需要联动tile与resident预算 | 补物理slot、队列depth、驻留区和失去重叠的代价 | 同上 |
| buffer-lifetime/reuse | 已有同地址存储复用；缺清晰区分值复用/派生复用/重算 | 补构造次数/驻留字节/读取代价、寄存器与UB分账、Action语义边界 | ops-transformer RoPE SplitBS host/entry/kernel/common；cannbot scalar |
| scalar-control/constant-lifetime | 已有活跃范围、spill、有限特化，容易误扩成任何派生数学外提 | 补依赖轴与三种状态范围比较，完整成本归属buffer-lifetime，不重复正文 | cannbot scalar；RoPE |
| tiling-tail/dispatch | 已有C2表到entry接线，缺进入此配方前为何分域 | 补先比较通用/参数化、机制域/fallback、代码与维护代价；R2回归不默认加Key | ops-nn SquaredRelu host/entry/kernel；ops-transformer RoPE host/entry |
| tiling-tail/valid-length | 已有有效长度、allocatedSpan、输入/输出对齐分离 | 本次不重复改写，其适用正文继续被新叶与搬运叶引用 | 复用现有包内来源 |

## 固定五仓库的提炼角色

- asc-devkit d378849769f9ee610af9d0ac38db2b3b6bed3209：Compare/Select/Max/两方向DataCopyPad/PipeBarrier；特定实现确认A2/A3 Compare整块。
- cannbot-skills 41377d0a442cd5b1c2356874873a3dda591c6633：Scalar活跃范围与double buffer设计；上游经验陈述不当成实测证明。
- cann-samples 17c948bb961fc6a660e4fcab45f6bf217c9c6239：RMSNormQuant gamma驻留、输入输出双槽；同文件含host tiling/launch，CMake明确dav-3510，不能直接移植A3 Reg/VF。
- ops-nn 8b42e125134fa9abf1e42a67e6b2792f78c26be5：SquaredRelu dtype-key-entry完整链。仅解释分派接线，不推广Key带来收益。
- ops-transformer d7e6a7c6c1450c040049486845336c77f3100406：RoPE SplitBS按UB/dtype选择批量，预计算Gather索引、cos/sin地址复用与同步。不是GridSampler数学的替代证据。

24个完整原文及5仓库许可保存于 `skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization`；其中19个源码/文档、5个LICENSE。`SOURCE_MANIFEST.json` 保存revision、原路径、完整行区间及hash；`CLAIMS.json`逐项区分明确陈述、直接源码事实、机制推导与精确定位。正文不要求打开来源才能操作。

## 公共集成建议

新ID `implementation.vector-api.compare_select_tail`：放入现有vector-api router，条件候选、非fallback，优先级可与cast同级2。正文适用于比较/选择等结构，不按算子名、case或失败状态召回；Action范围可在已合法允许Vector批处理、Scalar循环向量化、广播重构的范围内登记该实现叶。需 semantic_equivalence/capacity/plan_freedom/target_api；若是可能的方案咨询可保持缺条件，不注入事实冒充实施ready。新叶依赖dtype/CMPMODE/重载能力，不因scope含all而跳过正文约束。

对 `hoist_invariant_control`、`reuse_input_tiles` 不放宽到任意派生数学状态复用。若现有意图不适用，允许机会尚无注册Action，登记提案；本轮没有新增Action。新叶为比较选择实现，不应自动路由所有Action或自动强制读取。

相应旧叶版本均1.2.0，新叶1.0.0；树版本由主Agent更新。没有编辑公共router、REGION、索引、旧snapshot或knowledge.py。

## 剩余缺口与限定

- 尚未冻结新的目标SDK编译回执。固定API文档支持实施方案，不证明所有产品/SDK重载一致，更不证明NPU收益。
- 不同dtype/任意短tail最优实现不在现有来源中形成统一答案。新叶提供合法整块比较思路及代价，不能以padding方案替代所有条件选择。
- Scalar与DMA跨核混写的具体cache一致性需目标API及架构证据；不把旧个案外推成64B普遍门槛。
- 派生状态复用的通用Action语义仍是提案边界，不能只加O正文便声称正式C1交接闭环。
- 无硬件无法判断短行组合、slot深度、驻留与重算、初始化缩减的真实优先级；可形成有来源的条件方案而非统一收益分数。

## 已完成检查

本轮CPU来源与正文检查：9个改动record全部source hash/excerpt hash、来源行区间、正文局部链接及half/float padding/predicate边界公式通过。检查结果为 passed；运行脚本与详细日志保存在维护工作区，技能使用不依赖它们。这不是SDK API执行测试。
