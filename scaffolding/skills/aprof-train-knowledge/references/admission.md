# 从记忆到知识的准入与有效性验证

“已保存”“可学习”“验证通过”是三个状态。文件完整性不证明归因正确，轮内低噪声不证明跨 workload 有效。本规范给出初版可执行验收条件；阈值尚未由新协议的跨任务实验校准，不能声称保证全部算子受益。

## 数据冻结

Teacher run 保存 base skill-lib/三个知识区/override、数据集指纹、纳入与排除清单、模型/prompt、策略文件、预算、scope 与比较计划。每个剔除记录给原因：非 train、重复、缺原始证据、版本不兼容、proxy、归因混合、执行失败或量测未知。忽略的数据也保留在统计分母报告中。

先写 `run-plan.json`，冻结上述内容及 train/validation 任务清单，再生成候选；在提案的 before_refs 中引用该计划，并在 evaluation 报告中记录相同文件 hash。参数增量轮另在计划中记录 anchor/parent override 和已消费 observation 指纹。修改计划生成新版本并保留旧 hash，不用结果出现后的文件替代预先比较计划。

数据按 operator/group 和 baseline 谱系隔离；同算子换 shape、seed、候选或重命名不能跨 train/validation/test。train 用于提出和拟合，validation 只选冻结候选/停止，test 最终冻结后一次性评估。查看 validation 后修订属于下一轮选择，记录累计查看次数；不能继续称其为未见数据，最终结论需未用过的 acceptance/test。当前历史 test 暴露需要单独披露。

所有学习先限定到已有证据的 SoC、SDK/toolchain 和 workload 条件。不同环境分层处理；只有一台设备的证据不授权跨硬件推广。

## 四层门槛

| 层次 | 必需条件 | 可以输出什么 |
| --- | --- | --- |
| L0 原始 memory | 严格 schema、引用 hash、split、完整候选集合；缺项/失败显式保留 | 可审阅记录；partial 仍可归档 |
| L1 条件性案例/纠错 | 至少一条可核验来源；实际实现与结论对应；原协议、条件、反例保留 | 候选 example/recipe 修订；不提升通用权重，不宣称泛化收益 |
| L2 通用内容/参数候选 | 至少 3 个独立 train 算子组支持相应命题；边界/反例已审读；归因与角色匹配；CPU 检查全通过 | 新节点/边/路由/模板候选或保守 override |
| L3 有效性验证 | 冻结候选在独立 validation 比较中通过下述收益/正确性/回退约束 | validated_candidate；保留 scope、完整报告与回滚引用 |

针对单算子专用、来源纠错或 bug 修复，允许 L1 范围内进入候选内容，标明其证明的是限定可行性/正确性；不强迫为正文修错制造加速证据。小范围材料不能绕过 L2/L3 变成通用性能建议。没有足够留出算子就 deferred；若要改变评估范围/门槛，必须在看到新评估结果之前另冻策略，保留变更理由。

## 性能证据

仍用 `single_role_l2_clean_task_v1`：独立角色、5 预热、20 次逐轮清 L2、完整调用 Task 汇总后取中位数。复用 A 需符合原协议的源码/环境/有效期约束；候选先完整正确性，收尾补齐完整 case。这里不增加旧配对采样方法。

以选定 runtime 的 `timing verify` 结果为准，当前工程阈值为等 case 几何平均加速 ≥1.03、任一 case 回退 ≤3%、轮内 CV ≤5%。保留 threshold、metric、单位、采集时间、A 复用、全部原始 case。CV 超限、缺 case、跨环境或无法重放保持 inconclusive，不能算 stable_no_gain。20 轮是同一采集内的重复，不是 20 个独立优化任务。

单次 accepted 仅用于限定任务的正向观察。训练升级的最终问题是“使用候选知识，agent 在相同预算下是否能更好地优化”，不能只回放 memory 上的排序当作答案。

## L3 初版比较计划

固定基础模型、prompt、时间上限、候选/构建上限、设备与计时协议。比较 base knowledge 与 candidate knowledge；每个 validation operator 至少 3 次独立优化运行，按相同任务与预算对齐。模型支持 seed 时记录 seed，否则记录独立 run_id 和采样配置，不伪造可复现 seed。A 有效复用仍按统一协议，不引入旧 A/B 交错计时。

默认至少 5 个独立 validation 算子组；跨算子族主张至少覆盖 3 个 family，单族主张需明确 scope。每个任务都有完整正确性/边界与完整性能 case。优化失败回退原始正确 baseline 并计入成本/失败率，不通过删掉失败任务改善均值。

对相同任务分别取两组最终可交付实现的完整 case 性能，形成 `T_base_skill / T_candidate_skill`；先在算子内汇总重复运行，再等算子加权。通过条件：

- 平均收益比 ≥1.01，按 operator/group 聚类重采样的 95% bootstrap 下界 >1；预先固定 2000 次重采样和 seed。
- 每个评估任务的最终代码完整正确；候选组无新增正确性/runtime 逃逸，正确交付率不下降。
- 不发生声明 scope 内任何 case >3% 的未接受回退；失败/回退和不确定结果全部披露。
- 成本在同一预算内，报告时间/token/构建/计时次数；CPU 路由回放、来源、硬前提与 fallback 回归全通过。

上述置信区间针对**知识版本造成的跨任务结果差异**，不把单进程 20 轮包装成独立样本。小样本区间只作保守筛选，记录全部点估计和支持规模。顺序尝试多份提案需记录选择次数，并用最终未使用的 acceptance/test 复核；不能挑最好的一个区间当独立结论。

schema、来源、hash、树环/悬空边、负权/非有限值、代理证据误准入、unknown、跨平台字段缺失、硬前提失败、重复证据计数、同分稳定性，以及 Elementwise/Reduction/MatMul/欠融合/FlashAttention 的 C1→C3 隔离演练属于 CPU 检查。相关构建/route 能力复用基础包，不能另建一套图语义。

## 输出与权限边界

报告分开写：机制识别变化、推荐/选择/执行变化、性能、正确性、成本和知识规模。只改参数也保存确切 base_hash、version、数据/producer/policy hash；内容/结构变化保存 MD diff、来源、版本 lineage 与生成产物。

共享记录校验器验证 metadata，不执行硬件 gate，也不颁发 L3 资格。Teacher/evaluator 必须保存实际命令、输入和输出的证据。没有硬件授权时只完成 CPU 检查，evaluation_ref=null、status=candidate；不能写 validated_candidate。最终发布不属于 memory 整理或离线提案的隐含副作用。
