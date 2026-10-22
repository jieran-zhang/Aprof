# profiling：计时与机制采集交接

生产者：[采集角色](../agents/profiling.md)。消费者：协调者；机制结果再交诊断。使用 [公共契约](common.md)，`stage=profiling`、`role=profiling`。

## 请求类型与前置条件

请求正文必须写明 purpose，不能仅写“跑 profiling”：

| purpose | 输入 | 产物与用途 |
| --- | --- | --- |
| `timing_baseline` | preparation 或当前父版本的已完成 candidate；同源 binary/输入/完整正确性、声明和 config | 父版本缺少 case 的 capture/collection，供比较时作为 A |
| `timing_candidate` | 已完成 candidate、完整正确性、声明/config、对应父版本 A 引用 | 候选缺少 case 的 capture/collection；可产生单 case 反馈 |
| `mechanism` | diagnosis 中的假设/指标需求、目标源码/输入/正确性、后端和选择器 | 原始机制报告、capture manifest、normalized profile 与来源回执 |

A/B 只存在于请求的比较关系，原始采集 artifact 不保存永久角色。上一候选作为新父版本时，直接引用它原有的正确性和采集，不改名改 hash。

每次请求指定实际实现、case 集/指标、当前已覆盖和拟复用的记录、缺少或失效的部分、执行范围及剩余预算。代表/回归集在 preparation 中已声明。需要补齐时只请求缺少 case；过期/不兼容则按预声明策略更新相应 A 或 B。

## 必需结果

- 实际目的、实现/源码/二进制/输入、设备与工具来源。
- 协议或机制后端、实际 case/指标覆盖、执行命令与回执。
- 新采集、复用、失败和仍缺少的 case 分别列明；复用附匹配与新鲜度依据。
- 原始 capture/collection、Task CSV/PROF 或机制原始文件、解析结果的引用。
- 计时反馈中的每 case 中位数与比较关系；机制结果中的字段/单位、缺失值与解释限制。
- 实际成本、异常、波动和需复验的条件。

计时的唯一方法见 [统一协议](../../skills/ascendc-aprof-profiling/references/unified-timing.md)。复用既有完整正确性，不为每个采集视图重新执行完整测试；采集器仍对实际计时输出核验。机制数据按其独立采集与来源契约处理，不混入计时样本。

## 完成与退回

请求的子集/视图已完成且来源可核验即可 completed，正文必须说明完整声明集合尚缺多少。性能回退不等于采集执行失败；如实报告反馈，由协调者决定是否继续。

非零退出、缺 Task、来源或输出核验失败用 failed；缺同源完整正确性、adapter、工具或输入用 needs_input，并停止依赖采集。不存在的证据不能用 summary 或自填 passed 替代。

代表集结果不能直接触发全量 accepted。协调者汇集各次合格 capture、声明和两侧正确性，创建比较请求并调用 `timing finalize`；采集角色不另发一次旧正式计时。

## 正文填写模板

```markdown
## 请求
purpose、实际实现/比较父版本、输入和正确性引用：
本次 case/指标、已有覆盖、拟复用记录、缺少部分：
协议/后端、完成条件、授权范围与原任务剩余预算：

## 结果
实际执行与身份/来源：
新采、复用、失败和仍未覆盖项：
原始记录/collection/解析/回执引用：
单 case 反馈或机制指标（含单位与限制）：
实际成本：

## 缺项与失败
失败命令/退出码、缺视图、异常与复验需求：

## 交接建议
补齐 case、交回诊断、可收尾或停止；附输入引用：
```

## 知识记录关联 C4

计时请求引用本候选的 C3 及其 C2/C1 链；统一计时 schema 保持原义，不塞入知识字段。C4 外层 outputs 引用原始 timing artifact 与知识 handoff，明确本次测的是哪个源码/实现和实际执行的 actions。推荐或仅命中的方法不能标成已执行；mechanism 证据与 timing 结果分开。
