# graph-base 1.1.0：中文统一计时开发版

状态：未封版、未切换默认安装版本。本次完成协议、工具和中文工作流调整，没有启动新的 NPU 实验。开发包入口为 [1.1.0 README](../../../skill-libs/graph-base/1.1.0/README.md)，执行顺序以[角色与 contract 工作流](../../../skill-libs/graph-base/1.1.0/workflows/aprof-performance-workflow.md)为准。

下文保留此前各轮治理和验收记录；当前技能结构及最近一次检查结果以末尾“角色知识区治理”及其验收链接为准。

## 本次决定

代表 case 反馈与全量性能收尾统一采用 `single_role_l2_clean_task_v1`：每 case/实现一个新进程，5 次预热、20 次逐轮清 L2 的完整调用，逐轮汇总全部目标 Task 后取中位数。驱逐、输入准备、传输和输出检查不计入目标 Task 时长。

不再把这种方法限定为“快筛”，也不在收尾时重跑旧 Task v5、30 对样本或固定多进程流程。旧实现只保留历史回放用途；不能把旧 manifest 改名后送入新入口。1.0.1、历史证据和不可变图快照保持原有内容。

## 优化后的工作流

1. 冻结源码、完整 workload、输入/oracle、设备与工具链；预声明完整计时/正确性集合、代表集、比较父版本和复用/复验规则。
2. 基线构建并完成完整正确性。当前父版本 A 有有效记录就复用；先采代表集，后续只补缺少的 case。
3. 按需诊断和采机制 PMU，选择一个假设；复用未变的架构、并行计划与输入准备，在隔离副本中实施候选。
4. 候选完成审查、构建及完整正确性，再仅采 B。先看代表集与回归集；需要完整结果时按同一方法补齐其余 case。
5. 全集证据齐备后执行一次 `tools/aprofctl timing finalize --request <comparison.json> --output <new-result.json>`。反馈阶段合格的采集直接参与收尾，不再接旧 `candidate gate → episode finalize`。
6. 交付候选、比较父版本、覆盖范围、结果和成本。继续迭代时，上轮 B 的原始记录可作为下一轮 A；只有过期、身份/环境不兼容或触发预声明复验规则时才重新采集。

完整配置和可执行命令见[统一计时协议](../../../skill-libs/graph-base/1.1.0/skills/ascendc-aprof-profiling/references/unified-timing.md)。正式工程门槛为等权几何平均加速比 ≥ 1.03、任一 case 回归 ≤ 3%、轮内 CV ≤ 5%。过期、A/B 时间间隔超限或轮内波动过大返回 `inconclusive`。

这是中位数比的工程点估计，20 轮不是 20 次独立进程实验，不提供旧配对方法的 95% 置信下界。结果权限为 `performance_engineering_only`；不自动证明机制归因、生产范围、合法图动作或策略奖励。语义和范围等其他契约仍需分别满足。

## 已接通的工具

- `single_role_task.py`：调度预构建 native adapter；先生成完整正确性证据，再绑定它采集性能；保留设备探测、执行/导出/oracle 回执、原始 PROF 与 Task CSV。
- `device_single_role_task.h`：原生 5/20 调用时序与无 A/B 角色的采集身份。
- runtime 共享 Task parser：检查流、驱逐边界、完整 kernel 序列及 20 次完整调用，拒绝丢行或改用单个最长 kernel。
- `aprofctl timing finalize`：核验冻结文件和原始回执、重算输出判据、复用条件及性能结论；`timing verify` 用于按需审计，不默认紧接收尾重复回放。
- 同次采集共享不可变依赖快照，按 case 引用，避免重复复制相同源码、工具和输入。

skill、adapter、Agent wrapper、工作流、协议和当前使用说明已改为中文。命令、schema 字段、技术标识符及不可变历史材料保留原形式。

## 已有耗时与稳定性依据

exp 重测的[阶段成本记录](../../../../acceptance-vector-1.0.1-retest3-20261016T092909+0800/stage-costs.csv)显示：旧全 20 case Task v5 阶段，基线第 2 次为 1155.4 秒，候选第 1 轮为 1168.2 秒，约 19 分钟。后者整个 worker 为 1379.8 秒，Task 计时占约 85%；构建 9.3 秒、输入/完整正确性 57.8 秒、两侧机制 PMU 各约 63 秒。

已有 [L2 清理 5/20 实验](../../../../acceptance-vector-1.0.1-retest3-20261016T092909+0800/stability-study/CANNBENCH-ALIGNED-RESULT.md)在一台 910C/A3 的三个 case 上测得，每 case/实现的 native 采集加导出约 3.3 秒。20 个类似 case 的 B 计时约 66 秒，是基于已有 case 的估算，不含构建、完整正确性、新 controller 快照/输出回放或按需 PMU。首次 A 还要单独计入成本。

四次独立清 L2 进程的中位数 CV 分别为 foreach 0.85%、exp 0.63%、sigmoid 0.22%；同源码早晚两次比较仍观察到最高约 1.75%、1.04%、0.20% 的表观收益。因此协议可以统一，但不能把轮内稳定等同于所有设备、case 和长时间间隔都已完成漂移验证。三个保留原始 CSV 的完整调用中位数回放分别为 108.504、165.142、235.072 微秒，与历史记录一致。

## 验证与落地边界

本轮完成 CPU 模拟采集/导出/原始回放、缺 case 与身份拒绝、输出/CSV 篡改检测、B 原样转作 A、过期与噪声判定等测试；C++ 原语通过带 ACL/profiler stub 的模板实例化语法检查。它们验证代码与契约，不代替硬件实测。

静止文件状态下最终补测 32 项通过：新协议 29 项（parser 7、collector 11、timing 11）和归档回归 3 项。较早全套测试为 86 项通过、3 项因并行编辑改变包身份失败；这 3 项已在最终补测中全部通过。未封版结构、不可变 v0002 图和全部 21 个技能入口的结构检查通过。

当前通用 controller 仍需算子工程提供完整调用与真实清 L2 callback、设备状态 probe 和对应配置。支持的数值 oracle adapter 为小端二进制 float16/32/64、整数和 bool 的冻结逐元素容差；BF16、自定义格式或其他误差判据必须接入保留原精度标准的 adapter，不能删 case、放宽精度或改用旧计时来完成验收。源码和二进制被绑定与回放，不代表 runtime 重新编译证明了两者对应关系；构建来源仍需工程审查。

后续在恢复 NPU 实验后，应覆盖完整 case 集与实际设备、验证跨时段同源 A/A 漂移和 A/B 复用时限，并计入快照与输出回放的端到端成本。单轮反馈低于 600 秒仍是待实测目标。本次没有以这些待验收项为由保留第二套默认计时流程。

## 工作流目录治理

已从 1.1.0 移除远程 adapters、安装开关和 paramiko 依赖。原顶层 agents 与专业 skill 内 Agent 定义合并为 workflows/agents 的协调者、诊断、规划、优化、采集五个角色；插件和能力注册均指向这些文件。原顶层 references/contracts.md 迁至 workflows/references/runtime-contracts.md。

主 workflow 用角色节点和 C0—C5 阶段 contract 连线表示接入、补机制证据、计划复用/重规划、候选验证、计时补齐、runtime 收尾与继续迭代。公共交接使用 Markdown + YAML 头部并引用现有 JSON；每次调用保留独立阶段实例与请求/结果/缺项/下一步，机器证据 schema 与计时实现未改变。它是 Agent 的交接约定，不是新自动调度器或 Markdown 机器验收器。

治理后的 20 个技能入口、111 个当前 Markdown 本地链接/锚点、图快照和开发包结构检查通过；新增 5 项安装/注册回归通过。测试在临时宿主目录验证技能发现及幂等安装，并检查陈旧插件路径、角色身份或缺少 contract 时能拒绝不完整包；没有向用户宿主安装或切换默认版本。

本次静止文件状态下完整 CPU 回归为 **100 项通过（177.89 秒）**。独立角色接续试走确认代表集补齐、B 作为下一轮 A、缺正确性/构建失败停止等交接成立；离线示例的 Context 与文件引用通过检查，没有构造虚假机器采集回执。前向检查还补齐了明确授权图外实验的 unadmitted 交接规则。未运行 NPU。

## 角色知识区治理

workflow 技能入口改名为 coordinator，五个角色、十二项辅助能力统一在 skills/registry.json 登记。诊断图迁入 diagnosis/graph；规划和执行知识分别归属 parallel-planning/knowledge、optimization/knowledge。删除三项重复辅助入口，原 NOTICE、来源原文、历史图及案例按字节隔离保留。

新图 v0003 有 55 个 symptom、28 个 problem、28 个 action、84 条边。每个节点/边独立 Markdown，以 1/2/3 专家分数初始化，GRAPH.md 与运行时快照自动构建。规划树含五个主要类别及 Sort/TopK、布局转换，初版 15 个模板；执行树含六分支、10 个实现方法。新增内容为中文，来源固定到 cannbot-skills 的批准修订，保留原许可。

C1/C2/C3 使用独立 aprof.handoff/v2 与知识路由快照，C4/C5 关联推荐、选定、实际执行及统一计时。旧 episode 和 policy 不跨版本套用。共享路径、安装、registry 和发布检查兼容新旧目录，但没有执行发布或切换默认版本。

最近一次完整 CPU 回归 **127 项通过（379.91 秒）**；最终来源和迁移清单调整后，知识专项 **27 项通过**。共享工具旧布局回归 18 项、0.4.1 policy 回归 11 项通过；20 组旧图/policy 路由与迁移前冻结结果一致。独立副本从缺少 YAML/jsonschema 的环境完成依赖引导、17 项技能幂等安装，原生虚拟环境命令与清除外部 Python 路径后的验证通过。

完整逐项清单、初始化结果和边界见 [治理验收记录](../../../skill-libs/graph-base/1.1.0/workflows/migration/VALIDATION.md)。本轮未运行 NPU；初始分数尚未校准，模板只经过来源审读，不声明性能已验证。
