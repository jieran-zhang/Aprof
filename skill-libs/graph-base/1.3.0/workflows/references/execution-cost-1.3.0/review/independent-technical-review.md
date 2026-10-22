# 1.3.0 执行事实与完整代价：独立技术复核

复核日期：2026-10-22。复核对象为当前工作稿及其相对于 `/dev/shm/aprof-execution-cost-130-20261022/before` 的本轮变更。复核只读包内容，仅在本 review 目录交付报告；未运行硬件、网络或模型评测，未修改包。

## 注册结论

两项新 Action 可按 `reviewed_with_limits` 注册为 D7；相关 P4/O7、routing6/policy2 可继续构建。发现的两个 P1 在注册前已由协调者修正，复读修订后均解除。此结论支持有明确边界的来源知识注册，不表示目标 SDK 编译、NPU 异步正确性、算子精度或收益已经验证。

### 已解除的 P1：C1 依赖尚未形成的计划自由度

初稿两 Action 将 `constraint.plan_freedom` 放入硬前提，但 `action_decision_v3._validate_schemes` 的成员就绪来自原始 reasoning，`bindings_v4._context` 只在 O 路由 context 中从 C2 的 confirmed_plan 生成此谓词。普通首次单 Action 没有合法先行步骤来兑现该条件，C2 新计划本身不能自动解除原始成员 missing；会诱发为准入伪造现有源码事实。

已复核：两 Action 的 preconditions 和 policy 新增 safety/added 谓词均已删除此项，正文仍要求超出 C2 自由度返回规划。计划及实际实现的许可边界继续由 v4 的共同计划、joint compatibility、参数域和 actual compatibility 检查，未因此放松。

### 已解除的 P1：全槽初始化后仅排空用过的槽

初稿静态租约 Action 与 O leaf 允许初始化所有 q 槽空闲 token，却要求仅 drain 实际做过工作的槽。q=2、0/1 tile 时会遗留未用槽的初始化 token，重复调用再次 Set 违反固定文档的配对约束。原 Add 双缓冲恰好是最终无条件四次 Wait，消费全部已初始化 token。

已复核两处修订：以“已发布且未消费”作为 drain 依据；全 q 槽初始化时，0/1 tile 也回收未用槽的初始 token；按需初始化/首轮免等仅等待真正已发布的 token。无发布不可 Wait。现在与原文二值标志语义一致。

## 固定来源及冻结边界

直接阅读 `/tmp/aprof-knowledge-sources-1SHAlx/direct/SOURCE_REVISIONS.json`，按其五仓库固定修订检查原文件，并独立比对新增 manifest 的全部 9 项：归档文件与 direct 源完整字节一致，长度与 SHA256 一致。没有以 handoff 或 selfcheck 的文字结论代替原文。

对 202 条 D、45 条 P、53 条 O 的所有来源独立重算完整文件与行片段 hash，均一致。对 before 的 D6 全部 200 条记录检查 ID、kind、learning、invariants，保持不变。`runtime/src/aprof_runtime/knowledge.py`、旧 `knowledge-sources-1.3.0.json`、旧 `knowledge-sources-selection-v2.json` 与 before 精确字节一致。

本轮 D6→D7 前提迁移是版本化策略变更；不能把 D7 的安全/性能拆分回填成历史 D6 的新原义。新 Action 没有旧前提，policy 的 legacy_preconditions/legacy_dispositions 为空，新增安全条件逐项声明，符合此边界。

## 正文技术核对

- 派生复用：固定 RoPE `rotate_interleaved_split_bs.h:108-225` 确有按 int32_t 字节数 InitBuffer，Process 循环外生成 Gather 偏移，再 ReinterpretCast 为 uint32_t 供 seq/batch 消费。它仅证明该分派的派生偏移复用，不证明通用 GridSampler/Resize 数值链。新正文明确完整依赖轴、纯函数/副作用边界、失效窗口、全部消费者最后读完成、Scalar 私有数组的寄存器/栈/spill 未知，并将跨核 GM 表与 owner/发布协议送回 C2。
- 静态租约：直接核 Add `add.asc:188-240`、LocalTensor 构造全文和 SetFlag/WaitFlag 全文。addr 是物理存储起始地址，tileSize 是元素数；源码按字节地址构造，API 文档要求 32 字节对齐、addr+tileSize 字节量不超过存储。正文以 offsetBytes/sizeElements 和完整 arena 区间核算，保留 padding、临时区、ping/pong 与 API workspace，没有把 view 当分配器。
- 完成关系：四类边 V_MTE2、MTE2_V、MTE3_V、V_MTE3 与输入最后读、输入可读、输出最后读、输出可读关系一致。Set 不阻塞源流水，Wait 消费并清零，event/ID 必须匹配；静态 ID 建议 0–5，TPipe 范式从 Alloc/Fetch 获得，6/7 不直接挪用。正文明确同核 Vector 与跨核 FA slot 不等同，ISASI 不保证跨硬件兼容。
- 生产消费与坐标：P 的四类重算/片上保存/GM 表/融合比较保留真实输入读取、外部消费者、布局准备 P(Q)、实际对齐与同时存活资源；G(Q) 是分类型逻辑操作量，Q*s 是字节，不把它们换成硬件时间。coordinate 骨架绑定 G/B/H/F、真实 stride、dtype/边界及局部加权次序后才可完整使用，950 SIMT 不迁移为 A3 的合法 GM Gather。
- cache：固定 SetL2CacheHint 文档将 rwMode 标作预留，应使用默认 RW；NORMAL/DISABLE 与尚不支持的 PERSISTENT 界限正确。输出/GM 派生表后继复用属于策略分析，正文没有承诺独立读写控制、驻留、一致性或同步，也没有把逻辑读量直接写成实际 HBM 流量。
- 数值：小 K 加权和保持乘法/累加 dtype、舍入、FMA、次序及 finalCast；严格 `<` 与 `<=`、逐元素/聚合、NaN 和零参考值分别绑定 oracle。Compare+Select 非短路不能代替非法访问/除法保护，额外 mask/Cast/缓冲/同步计成本。没有凭 API 名称推导未写明的 NaN payload/符号零行为，也未预设通用容差。

## workflow 与选择规则

`workflows/references/action-selection.md` 的新增三部分具有可执行的判断用途：

1. 数据相关路径把输入范围→判断条件→触发粒度→影响输出→工作量连起来。整 plane 扫描触发的软件路径应计 I+S*K，而非命中输入数*K；范围跨阈值只证明可能触发，无分布不得称罕见。使用已有矩阵/生成器，不额外要求读遍输入或 PMU。
2. 新增准备比较区分 API 调用、descriptor block、有效/补齐字节、workspace 和未观测 HBM；按完整调用与真实复用摊销。有可信同父本阶段时间时只给节省粗上界，重叠阶段不直接相加中位数。无时间证据仍可符号竞争和假设试验，不能凭“可能抵消”结束比较。
3. 正确性修复新增整域回退、扫描、软件算术或阶段、明显改变覆盖时，C3 即使未越 C2 边界也要回 C1 保存 decision/交接后继；普通不影响关键预测的等价修正可复用旧分析。C2 越界仍返回规划。

这些规则复用已有 path_overview/work_delta/coverage/tradeoffs 和自然语言选择依据，没有增加日常表单、成本执行器或固定运行步骤。完整方案允许必要多因素联合变更、无需构建中间候选；缺消融限制单项归因，不否决整体候选。性能 unknown 可由假设试验检验，没有强制换 Action、固定候选数或把性能 unknown 一律转实施安全门禁。

自然语言是否真的据这些量作出合理选择，仍需技术审阅；runtime 的字段/hash 不能自动证明推理正确。这是明确的产品边界，不宜为“自动判定所有成本”扩充解析器。

## runtime 核对

`action_decision_v2.workload_case_payloads` 从一个共享实现读取完整 cases[{case_id,workload}]，后继反馈的 v2/v3 均复用。D7 选择用 `missing_workload_mapping` 检查首次选择前冻结的 workload_ref；规范 bare 清单仍可在 C2 返回 conditional，C3 明确拒绝，计划保证不能补齐测前身份。D6 分支返回空 missing，不追加 D7 字段，保留历史准入语义。

混合 wrapped/bare 或半份 payload 被明确视为损坏格式，GraphError 拒绝；不按已有子集准入。若需要纯分析应使用规范 bare 矩阵。这一边界已与协调者确认，不作为未修缺陷。

`action_decision.validate_handoff_decision:444-451` 已独立检查非空 c1.scheme_id 必须等于 decision 所选 scheme.id，并核验精确 scheme hash，再把该 ID 传给方案 validator。防止手工构造空/错 ID 而仅靠 hash 进入交接；不依赖 `_decision` 测试替身完成这项保障。

另独立运行真实 v4 链的三个测试函数：D6 单成员/多成员真实 decision 路由交接、两个不同注册 Action 各自条件/路由、前置保证直到 C3 最终源码核实前仍保持 unknown。共 4 个参数化用例全部通过（138.15 秒）；这些用例使用真实 decision 验证，未将 `_decision` 替换成通过结果。D7 的首次映射门禁仍须在最终真实冻结 bundle 上另行回归。

## 开发 CPU 模型

只导入调用 `check_execution_models.py` 的函数，未执行 main 写其检查文件。对 slots=1/2/3、0/1/q−1/q/q+1/多轮、两种初始化方式的去重后 30 个组合，各执行两次 invocation。所有 token 配对闭合，Set 次数等于 `2*((initialize_all ? 2*q : 0)+4*tiles)`；旧 used-only drain 在 0/1 tile 均触发反例。

这与 Add 的四事件协议及 Set/Wait 二值标志语义一致，但不模拟异步延迟、指令发射时序、并行重叠或物理存储访问。guard_work 仅模拟 R14 的有限且 abs(x)>=32 的整 plane 触发，Inf/NaN 不触发也只限该模型。邻居 slot 变换恢复 k 次序，不证明浮点误差或减少必要邻域读取。脚本停留开发目录，没有接入用户日常 workflow 门禁。

## 未验证范围

未运行目标 SDK、编译器寄存器/栈分配、设备/NPU、异步并发、实际算子精度、计时或模型评测。最终冻结的 D7/P4/O7/routing6/policy2 的构建身份及真实链回归由协调者/运行时工作流完成，本报告注册结论不替代那些检查。
