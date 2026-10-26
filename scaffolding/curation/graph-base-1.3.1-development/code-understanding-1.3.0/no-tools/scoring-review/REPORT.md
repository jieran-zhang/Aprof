匿名独立复核已完成。建议 **0 处得分变更、0 个新增或撤销 cap**；发现 **1 处仅引文转录修正**，原 correct 判定与分数保留。无待裁决的实质评分问题。

本次只使用 blind-review 内的协议、计划、选择表、匿名 candidate/annotation/gold、题目源码及固定 reference-corpus。未读取条件映射、skill、旧结果、原始调用元数据或条件汇总；未运行设备、编译算子或修改任何输入材料。

范围与结论

- 随机指定的 8 份全部完成实质复核：逐一检查 **79 个 gold fact 与 24 个显式 cap**。reviewed.json 为每个 fact 记录覆盖程度、保留判定、独立复核理由、逐字连续证据；为每个 cap 记录触发检查结果。8 份均未出现显式触发。
- 对全部 24 份做注释结构、状态及连续引文校验，共 236 个 fact；全部 fact 恰好出现一次，原注释为 223 correct、13 partial，wrong/omitted/unsupported/critical 均为 0。因此“所有 wrong/unsupported/cap”的追加复核集合为空。
- 对 CU01.H04、CU04.H04、CU06.E03/H01/H04，按同一 fact 统一复查对应 case 的所有 4 份匿名答案，共 **20 个一致性检查**，其中 **9 个 fact、7 份答案**在全量8份之外。这样覆盖了全部 13 处 partial；未发现可升为 correct 的漏判，也未发现同类规则应降分的 correct。

| answer_id | case | 全量fact / cap数 | 算法 / 执行 / 硬件（前后相同） | 复核 |
|---|---|---:|---|---|
| answer-db6886002780 | case-01 | 10 / 2 | 10 / 10 / 10 | 保留 |
| answer-7598a3e11e05 | case-02 | 9 / 3 | 10 / 10 / 10 | 保留 |
| answer-d04520e096b7 | case-03 | 10 / 3 | 10 / 10 / 10 | 保留 |
| answer-ff6063e966a6 | case-04 | 10 / 3 | 10 / 10 / 10 | 保留 |
| answer-5bde3bbae7a7 | case-05 | 10 / 4 | 10 / 10 / 10 | 保留 |
| answer-bd2e07a9a34e | case-06 | 10 / 3 | 10 / 10 / 7.5 | 保留 |
| answer-0a4165fcbbeb | case-06 | 10 / 3 | 10 / 8.5 / 7.5 | 保留 |
| answer-426d84c805bd | case-06 | 10 / 3 | 10 / 10 / 7.5 | 保留 |

关键裁决依据

- 第1题的变换后shift、BF16/FP32转换、8340元素分核和尾字节、单槽及UB容量均有具体解释。两个 CU01.H04 partial 仅泛指可能补齐或GM 32B边界，没有给出 local 物理块的32B对齐契约；不将这种保留当作完整平台事实，也不加cap。
- 第2题正确区分52B数据、12B pad、32B UB间隔与GM的28B/20B间隔。UB行距96B及五个0xA5输出间隔均具体；无字节/元素/32B块单位混淆。
- 第3题正确追踪实际half分派和P的两次x2[0:3]请求，区分4B物理分配与tensor view；对P仅给静态非法范围及有条件局部比较，不将它改判为确定完整输出或已测故障。
- 第4题明确float L0C先转half落GM再half激活，2AIC/4AIV的半块覆盖、2201的Zz/Zn及完整事件链均正确。两个 CU04.H04 partial 缺3510的L0A NZ格式；只说“排布不同”不等同明确格式。
- 第5题的KiB起点加容量已无歧义确定全部物理字节区间，前10轮切片表也等价给出槽序列，均保留满分。正向ready与反向reuse边、UnitFlag2/3以及variant的保证缺失/未测设备后果均分清，不因缺显式M_FIX扣分。
- 第6题全部4份均缺3510=Ascend 950PR/950DT的具体映射，所以 CU06.H01 保留partial；全部4份只给一般可移植性/实测保留，没有A3/A2与950的CrossCoreWaitFlag阻塞流水差异或另一同等精确的额外契约，所以 CU06.H04 保留partial。answer-0a4165fcbbeb 的 CU06.E03 缺L0C NZ及Fixpipe NZ→ND物理链，其他3份有明确格式说明，判分一致。
- 不因缺最后一个已被具体表达式、单位和范围唯一确定的数字扣分。AIV行起点乘128、KiB槽起点加容量等表达均按语义等价认可。不以长度、引用数或术语密度加分；遗漏不触发cap。

唯一修正

answer-5bde3bbae7a7 / CU05.A02：原 annotation.answer_span 在段首 `device` 前多录一个ASCII空格，故原引文不是候选答案的连续子串。corrections.json 提供删除该转录空格后的逐字原文；original_status=suggested_status=correct，3分保留。未改原 annotation/candidate/gold。

交付

- reviewed.json：8份逐fact/cap完整记录、20个同fact检查、全24份结构/引文审计与输入哈希。
- corrections.json：仅上述1条引文修正建议，不包含任何得分或cap变更。
- 本报告不含条件推测或A/B汇总；可由主agent在解盲前应用修正并锁定。
