# preparation：任务接入与准备

新任务必须按 [soft_targets_local_v1](../references/execution-policy.md) 执行：耗时仅为软目标，baseline 默认 assumed，新候选完整验证一次，按全输出内容复用；所有运行产物留在 /dev/shm。

生产者：[协调者](../agents/coordinator.md)。消费者：代码理解、诊断、规划、优化和采集。外层格式使用 [公共契约](common.md)，`stage=preparation`、`role=coordinator`。

## 请求与必需内容

当前 C0 是外部范围、父本与 workload 的来源。新建或更新角色上下文时由这些冻结引用和当前适用证据构造，不整份复制上一轮 Context 的 facts、剩余额度或父本。scope 更新保留前版、授权来源与累计尝试；不能用重建上下文重置预算。完整 workload 映射及历史表示边界见[方案决策格式](../references/action-decision-v3.md#完整-workload-的测前映射)。

请求带入现有算子、用户目标、执行范围和预算；先利用已有字段，缺少影响执行的信息才补充。

结果正文必须填写：

| 字段 | 内容 |
| --- | --- |
| 任务目标与允许阶段 | 优化、仅诊断或仅规划；实际允许的硬件、修改和执行范围 |
| 外部迭代约定 | 用户/外层驱动给定的轮数、目标、达标停止条件、重试范围及来源；未指定项明确未配置，不能代填推荐值 |
| 工程与谱系 | 完整 op_dir、原始基线、当前比较父版本、隔离候选位置 |
| 语义与 workload | 数学语义、shape/dtype/layout/属性、动态域、尾块、fallback、精度标准；影响数据相关路径的已有值域/特殊值与生成条件，不能用本批范围缩小合法输入域 |
| 执行环境 | 真实设备、架构与工具链证据；未知项明确列出 |
| 执行命令 | build/verify/run argv、cwd、必要环境；算子 native adapter 的完整调用/清 L2/输出接口 |
| 采集声明 | 完整 timing/correctness case 集、输入/oracle、代表/回归集、比较关系、复用及异常/临界复验规则 |
| 准备状态 | 构建、输入、完整正确性、已有 A 的覆盖和新鲜度；每项注明证据或缺项 |
| 预算 | 冻结 policy 引用（如有）、原始单调起点/总软目标、C0 阶段软目标、候选/构建/计时等限制；按[阶段预算绑定](../references/workflow-details.md#stage-budget-policy)统一传递和计费 |

## 输出引用与完成条件

`context_ref` 绑定可校验的 Context。执行优化时 `outputs` 至少引用源码/工程快照或清单、输入与 oracle 清单、构建回执、baseline assumed 声明（或显式要求时的真实正确性）和统一计时 declaration；已有 A 则引用原 collection/capture 或相应 profiling 阶段。

完整 correctness 的 JSON 来自 [统一采集器](../../skills/ascendc-aprof-profiling/references/unified-timing.md) 的 correctness-only 路径，或引用同协议下仍匹配的既有证据；普通旧正确性日志不能冒充该格式。代表集与复验规则写在本文，不向严格 declaration JSON 添字段。后续只补缺少的 A，不要求准备阶段采全 case。

只有 kernel 时用 [直调技能](../../skills/ascendc-kernel-direct-invoke/SKILL.md) 接入完整工程。原精度不是逐元素容差时使用 [原始 oracle adapter](../../skills/ascendc-aprof-profiling/references/original-oracle.md)，先对全部 case 做不含数值计算的 capability preflight；仅新候选或显式要求验证的 baseline 执行完整正确性。上层已有匹配包/adapter/环境的能力证据时复用，不重新调查共同缺项。

未知硬件或缺 adapter/环境返回 needs_input，并在正文记录具体 reason 与缺失能力；只有原 oracle 对本次实际输出返回 false 才称 numerical_mismatch。不能用旧计时回退或放宽精度。开发包修复另立版本/快照，已冻结任务不原地换包。

仅诊断/规划范围内，完成已请求的准备可标记 completed，未执行构建/正确性/采集明确列在缺项中；其下游只能进行允许的分析，不能据此直接计时。

轮数、是否达标停止和允许的重试由本次外部任务决定。未指定多轮范围时，只完成当前明确请求的方案并报告状态及后续机会，不自行无限迭代或建立连续失败停止规则。既有正确性/计时有效性/工程判定不变；accepted 不自动等于任务终点。修复/重试保留独立 attempt，成本连续累计，不借换名扩大范围。

准备后先交 [code-understanding](code-understanding.md) 恢复实际算法与实现，再进入 C1；已有适用理解报告直接复用。C0 负责冻结输入和执行条件，不重复撰写完整理解正文，理解也不以性能采集齐备为前提。

## 正文填写模板

```markdown
## 请求
目标与允许阶段：
现有工程、原始基线、当前父版本：
预算与执行限制、外部轮数/达标停止/重试约定及来源：
完成条件：

## 结果
语义、workload、输入/oracle 与容差引用：
设备、工具链与命令引用：
完整 case 集、代表/回归集与复验规则：
构建、完整正确性、已有 A 的覆盖/复用依据：
输出与成本引用：

## 缺项与失败
缺失字段、未执行范围、阻塞后续的具体条件：

## 交接建议
允许进入的阶段、接收角色与证据引用：
```
