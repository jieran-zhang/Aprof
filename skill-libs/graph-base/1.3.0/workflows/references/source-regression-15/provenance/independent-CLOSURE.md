# C 组独立复核闭合记录

日期：2026-10-21。复核对象：`/tmp/aprof-raw15-autonomous-c/case-11` 至 `case-15` 的修正后核心记录。本文件补充最初 REVIEW.md/ issues.json，不覆盖原发现。

结论：原 R2、R3、R4 三项已闭合，未发现这次修正引入新的阻断问题。闭合表示证据和条件分析已正确表达，不表示未知 API、物理写规则或完整数值语义已经获得实施许可。Action 无需更换。

## R2：精确证明定位已闭合

两轮 reasoning 中的已知 constraint 现引用各任务 `condition-audit.json` 的 `json-pointer:/known_conditions/<n>/basis`；数学映射事实引用 `/mathematical_facts/<n>/basis`。这些位置可以实际解析到对应证明段，证明条目进一步带原 kernel/tiling/host/oracle 文件 hash 和具体行号，不再指向 R1-analysis 的标题。

独立核对 10 份核心记录，解析 42 个证明指针，核对 58 个底层源码行号引用和合计 125 次文件引用/hash，均通过。代表位置：`case-13/R2-reasoning.json:380`、`:604`。相同证明已同步进入两轮 evidence 和 C1 内嵌 reasoning。

## R3：Transpose 物理写条件已闭合

`case-14` 两轮 `constraint.output_ownership` 均为 unknown；数学任务分割与布局映射仍保留已知。所选机会含该实施安全 unknown，并有 `required_before_implementation=true`、尚未执行的独立请求（`R2-action-decision.json:110`、`:337`）。

`case-14/R2-analysis.md:15` 给出的后继方案按真实物理粒度 A 分配连续物理块 owner，将矩形行段与 owner 字节区间求交；必要时同核汇集跨行片段，禁止跨 owner 补齐，末端须有已验证的有效尾写。明确 A 尚未知，32/64B 不能当设备事实。第 17 行的 2046B 行跨度例子正确：示例 A=64 时 `[1984,2048)` 含第 0 行末 62B 和第 1 行首 2B。

R2 已将整矩形源工作预测调整为 unresolved，明确裁切可能增加读取/发射，需要重新计算成本；性能预测仍 not_tested。这次反馈确实改变了条件方案及其判别状态。

## R4：完整数值等价与数学映射已分离

case-13、case-15 的 R1/R2 reasoning、evidence 和绑定路由均将 `constraint.semantic_equivalence` 保持 unknown，另用已知的 `source.element_mapping_equivalence` 记录可证地址与目标表达式。数值 unknown 具体涉及原 volatile FP32 运算边界、半精度/BF16 Cast、次正规数、NaN/Inf、正负零及融合/舍入；两任务均增加实施前必须补齐的完整语义请求。

代表位置：`case-13/R2-reasoning.json:356`、`:604`；`case-15/condition-audit.json:79`、`:96`。R2 反馈明确静态支持仅覆盖源工作/地址表达式，不再将其当作完整数值等价证明。

## 一致性与边界

10 份 C1 内嵌 reasoning 与对应独立 reasoning 完全相同；10 份 reasoning.context_snapshot 与对应 `R1-evidence.json` / `R2-evidence.json` 完全相同。source_context_ref 指向当前 source-authority 且 hash 相符，decision.reasoning_ref 和 R2.previous_decision_ref 均指向当前文件。case-13/14/15 两轮 routing-evidence 与 P-bound-route 的相关约束状态也同步为 unknown。

5 个 R2 都仍为 not_measured、result_ref=null，性能更新均 not_tested；父本仍是原源码。上述判断基于核心文件直接阅读和只读一致性断言，不依赖正在收尾的 CLI 汇总。未重复测试此前已闭合的 runtime 漏洞，也未运行硬件、构建、原算子 oracle、训练或联网。
