# 1.1.0 技能库治理验收记录

本轮只修改 1.1.0 草稿及兼容新布局的共享工具。未封版、未切换默认版本、未向用户宿主安装；没有启动 NPU 实验。完整流程见 [角色与契约工作流](../aprof-performance-workflow.md)。

## 交付范围

| 对象 | 当前内容 |
| --- | --- |
| 角色与辅助能力 | coordinator、diagnosis、parallel-planning、optimization、profiling；12 项辅助能力逐项登记角色与触发时机，共 17 个技能入口 |
| 诊断图 v0003 | 55 个 symptom、28 个 problem、28 个 action、84 条边；每项一个 Markdown，图和初始化报告自动生成 |
| 规划知识树 v0001 | 33 项：8 个 router、8 个 fallback strategy、15 个模板、2 个历史案例；五个主类别及 Sort/TopK、布局转换补充分支 |
| 执行知识树 v0001 | 29 项：7 个 router、7 个 fallback recipe、10 个实现方法、5 个历史案例；覆盖六个执行分支 |
| 迁移清单 | 256 个原文件、1,230 个旧节点/边/矩阵行/路由规则；逐项保留原文、hash、去向和理由 |
| 交接 | C1/C2/C3 使用 aprof.handoff/v2；C4/C5 区分推荐、规划选择、实际执行并关联统一计时 |

初始化详情分别见 [诊断图](../references/development-records.md#skills-1-3-2)、[规划树](../references/development-records.md#skills-1-3-2)、[执行树](../references/development-records.md#skills-1-3-2)。节点正文、来源和分数以各知识区维护文件为准。

## 已完成的验证

| 检查 | 结果与边界 |
| --- | --- |
| 完整运行时 CPU 回归 | `python -m pytest runtime/tests -q`：127 项通过，379.91 秒；包含统一计时、原始证据回放、归档、规划、知识与安装回归 |
| 最后来源定位与迁移整理后的补检 | `python -m pytest runtime/tests/test_knowledge.py -q`：27 项通过，20.63 秒；该集合包含在上面的全量集合中，不重复计数 |
| 共享工具兼容 | registry、release binding、publication 校验测试 18 项通过；旧 0.4.1 policy 测试 11 项通过；1.1.0 registry/plugin 检查通过 |
| 历史图与 policy | v0001/v0002 原字节核验通过；20 组含/不含旧 policy 的路由与迁移前冻结结果逐项一致；没有用新采样生成旧配对 episode |
| 构建与非法输入 | 三个知识区重复构建结果一致；拒绝重复 ID、非法/悬空边、树环、父节点错误、无来源、坏 hash、非安全 YAML、重复 YAML 键、无效权重及跨版本参数覆盖 |
| 路由 | 小 workload 与欠并行的区分、带宽饱和与小搬运开销的区分、反证、证据去重、未知/profile 缺失、proxy、跨平台字段缺失、硬前提失败和多分支/fallback 均覆盖 |
| 五类契约演练 | Elementwise、Reduction、MatMul、欠融合、FlashAttention 均沿 C1→C2→C3 生成并校验快照；下游使用交接快照，不要求访问上游角色内部知识目录 |
| 结果关联 | 使用 FakeRunner 的 CPU 协议产物验证 C3 源码与统一计时结果绑定；拒绝不同源码、坏引用 hash、非选定动作和错误父记录 |
| 独立安装 | 完整包复制到仓库外，从缺少 YAML/jsonschema 的 Python 环境安装声明依赖；虚拟环境原生 aprofctl 可校验/路由三个知识区；17 项技能安装幂等 |
| 外部依赖隔离 | 清除继承的 PYTHONPATH/PYTHONHOME 后，独立包结构、v0003 快照和 pip 依赖检查通过；运行不需要 cannbot 上游仓库 |
| 技能与链接 | 17 个 SKILL.md 通过 skill-creator 校验；活动 Markdown 的本地文件及锚点检查通过。冻结 archive/history/sources 保留原字节和原布局语义，不当作活动导航 |

独立角色接续审读还覆盖了 FA decode 与逐元素融合、C0/Context 引用、缺少证据时保持 needs_input、空 split-KV 的稳定合并语义。演练使用明确标记的纸面/CPU 数据，不是硬件性能记录。

## 已明确的限制

1/2/3 是未校准的专家顺序分数，不能解释为概率或预期收益。18 个新增机制的来源定位到具体问题行；84 条边分别说明赋值理由。十条原有主动作边的初值与批准方案一致；旧 2.4～2.8 logit 只保存在历史与迁移记录。

模板和方法完成固定来源审读，包含方案骨架、公式、伪代码与 Ascend C 关键片段；尚未在目标 SDK/NPU 上作为完整算子编译并验证性能。上游固定修订为 `c60a48af8f0ff2374e1491a313d9f26b02620d1e`，原许可证、来源与修改说明随包保存。

未实现的 extractor、未知平台分母和缺失 profile 保持未知。统一计时的跨时段漂移、复用时限和完整端到端成本仍需要后续硬件验证；本轮没有添加自动训练或发布任务。
