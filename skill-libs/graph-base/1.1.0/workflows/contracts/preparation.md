# preparation：任务接入与准备

生产者：[协调者](../agents/coordinator.md)。消费者：诊断、规划、优化和采集。外层格式使用 [公共契约](common.md)，`stage=preparation`、`role=coordinator`。

## 请求与必需内容

请求带入现有算子、用户目标、执行范围和预算；先利用已有字段，缺少影响执行的信息才补充。

结果正文必须填写：

| 字段 | 内容 |
| --- | --- |
| 任务目标与允许阶段 | 优化、仅诊断或仅规划；实际允许的硬件、修改和执行范围 |
| 工程与谱系 | 完整 op_dir、原始基线、当前比较父版本、隔离候选位置 |
| 语义与 workload | 数学语义、shape/dtype/layout/属性、动态域、尾块、fallback、精度标准 |
| 执行环境 | 真实设备、架构与工具链证据；未知项明确列出 |
| 执行命令 | build/verify/run argv、cwd、必要环境；算子 native adapter 的完整调用/清 L2/输出接口 |
| 采集声明 | 完整 timing/correctness case 集、输入/oracle、代表/回归集、比较关系、复用及异常/临界复验规则 |
| 准备状态 | 构建、输入、完整正确性、已有 A 的覆盖和新鲜度；每项注明证据或缺项 |
| 预算 | 原始截止时间和候选/构建/计时等限制，复用与新执行都计入原任务 |

## 输出引用与完成条件

`context_ref` 绑定可校验的 Context。执行优化时 `outputs` 至少引用源码/工程快照或清单、输入与 oracle 清单、构建回执、完整正确性和统一计时 declaration；已有 A 则引用原 collection/capture 或相应 profiling 阶段。

完整 correctness 的 JSON 来自 [统一采集器](../../skills/ascendc-aprof-profiling/references/unified-timing.md) 的 correctness-only 路径，或引用同协议下仍匹配的既有证据；普通旧正确性日志不能冒充该格式。代表集与复验规则写在本文，不向严格 declaration JSON 添字段。后续只补缺少的 A，不要求准备阶段采全 case。

只有 kernel 时用 [直调技能](../../skills/ascendc-kernel-direct-invoke/SKILL.md) 接入完整工程。未知硬件、缺 adapter 或 oracle 不兼容，返回 needs_input，不能用旧计时回退。

仅诊断/规划范围内，完成已请求的准备可标记 completed，未执行构建/正确性/采集明确列在缺项中；其下游只能进行允许的分析，不能据此直接计时。

## 正文填写模板

```markdown
## 请求
目标与允许阶段：
现有工程、原始基线、当前父版本：
预算与执行限制：
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
