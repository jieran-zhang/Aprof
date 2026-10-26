# 15 项无硬件自主分析独立技术复核

审阅日期：2026-10-21。包：`/mnt/tidalfs-hwwh01/dataset/dots_infra/workspace/jieran/APROF/aprof-maintenance-soft-targets-20261019/skill-libs/graph-base/1.3.0`。原始输入：`/tmp/aprof-raw15-suoslncl`。执行产物：`/tmp/aprof-raw15-autonomous-{a,b,c}`。

结论：15 项已经能够依据当前源码和有来源的方法提出具体、有参数边界的条件方案，未以缺少当前性能实验否决这些方法。没有按 Action 数量或换动作数量评分。发现并复现了 1 个运行时反馈类型漏洞，主执行方已修复，独立复验通过。当前未发现必须否定这些静态方案的未修复阻断缺陷；C 组仍有 3 项需要收紧的证据/条件表述，不能因此把条件方案当作 C3 实施授权。

## 范围和方法

已阅读全部 15 项中文摘要/结果、两轮主要选择、候选成本比较、所选机会 unknown 和 R2 反馈。审查 `runtime/src/aprof_runtime/action_decision.py`、条件策略、选择文档与 decision contract。代表性深查包括原始 Mish/MaskedScale 的生命周期、Exp/AdamW/Foreach 的槽数与容量、Gather 地址解码、GELU 临时区、Maximum 比较语义、RoPE 逐步算术、Transpose 地址/owner、Resize 坐标和四项插值；抽查 P/O 正文定位和真实绑定路由。

没有读取历史硬件结果或包内测试 fixtures 来获得答案；没有构建原算子、运行 NPU/native/profiling、训练或联网。只运行了在 `/tmp` 临时副本上的 CPU runtime 反例，随后删除临时副本。未修改技能包或执行组产物。

## 阻断缺陷：发现时阻断，现已修复

### R1 / P1：性能预测可通过改写 kind 绕过未测反馈限制（已修复并独立复验）

原 `action_decision.py` 在性能假设只校验 `prediction_id` 存在，未要求该预测为 `kind=performance`；`_feedback` 又仅按前轮预测的 kind 禁止 `not_measured` 下的 supported/weakened。

具体复现：复制 C 组 case-13 到临时目录；将 R1 与 R2 所选机会 `o1-perf.kind` 从 `performance` 改成 `source_work`，保留 `performance_hypotheses[*].prediction_id=o1-perf`；把 R2 对应反馈改为 `supported`，引用真实 R2 静态证据，并更新 R1 decision 文件 hash。原 `validate_decision` 返回 `status=conditional, performance_claim=false`，没有拒绝该错误性能确认。再仅改前轮 kind 也必须受保护，不能只检查当前轮。

主执行方加入 `_performance_predictions`（当前文件约 105–109 行），在当前 opportunity 及 `_feedback` 读取的全部前轮机会中调用。独立复验结果：原 case-13 R2 仍通过并保持 conditional；“当前及前轮都改 kind”和“只改前轮 kind”均被 `性能假设必须引用 performance 预测` 拒绝。此处属于可机械检查的类型关系，不能交给自然语言语义复核兜底。复验没有执行包测试 fixtures。

## 重要限制：需要在交付记录中修正

### R2 / P2：C 组已知安全事实的 locator 指向标题，未定位证明

代表位置：`/tmp/aprof-raw15-autonomous-c/case-13/R2-reasoning.json:349` 的 `facts.constraint.semantic_equivalence.ref`、`:391` 的 `facts.constraint.output_ownership.ref`，均定位 `R1-analysis.md` 的 `lines:1`。该行只是 `# apply_rotary_pos_emb：R1自主静态方案`。case-11 至 case-15 的 true constraint、R1/R2 以及内嵌 evidence 中同类引用普遍如此。`condition-audit.json` 给出了更多解释，但 `original_evidence_ref` 仍回指标题。

这不是“全部 true 都无来源”：例如 case-13 原 kernel 第 15–20 行确有完整 row 输入输出与 half-mode partner，分析正文第 13/23 行也有结构说明；问题是冻结事实的精确定位没有指向这些依据。后续读者按 locator 无法复核，不应以 hash 正确或 schema 通过代替此项。应逐谓词指向实际证明段或带源码行号的证明对象，并同步 reasoning/evidence/C1/hash；无需添加硬件数据，也无需更换 Action。

### R3 / P2：Transpose 新矩形 owner 尚未证明物理写边界

位置：`/tmp/aprof-raw15-autonomous-c/case-14/R1-analysis.md:11`、`:21` 与 `condition-audit.json:26`；`R2-reasoning.json:368` 仍将 `constraint.output_ownership=true` 解释为逻辑无交输出矩形。

所引用知识 `skills/ascendc-aprof-parallel-planning/knowledge/families/layout/templates/transpose.md:53` 明确要求不同 owner 不因对齐 DMA 触及同一物理块；不能仅证明逻辑矩形交集为空。当前列出的 target_api 缺项（R1-analysis:29）只明确局部 Transpose/Gather 位宽支持，未明确搬出物理边界。

复现用原矩阵 case-7（1023×1023 float16）：输出行跨度为 2046 B。候选 16 列片宽 32 B、32 列片宽 64 B，都不能令不同输出行/片的边界天然满足某个 64 B 独占规则；若目标搬出接口以该物理粒度更新，相邻 owner 可触及同一块。这里不假定设备必然出错，而是已知存在必须核对的具体合法性条件。

可保留矩形思路，补“真实写粒度 A 下的物理 owner/有效尾写”证明或 unknown/request；可按原物理 owner 裁切，或将共享边界块交给同一 owner。不要把尚未确定的 A=64 当平台事实。A 组 SwiGLU 已用 `C2-output-boundary-addendum.md` 区分数学 owner 与物理写许可，是可参考的现有做法。

### R4 / P2：RoPE/Resize 的完整语义等价 true 与数值 unknown 需要一致

位置：`/tmp/aprof-raw15-autonomous-c/case-13/condition-audit.json:5`、`:7` 与 `R1-analysis.md:33`；case-15 同类 `condition-audit.json` 和 `R1-analysis.md`。二者把 `constraint.semantic_equivalence=true` 限定解释为表达式/地址映射成立，同时 `constraint.numeric_order=unknown` 明确承认目标 Vector 的舍入、特殊值及 Cast 等价未核验。

当前 policy 对 `constraint.semantic_equivalence` 的含义包括完整数学、异常值、精度、地址和值可见性。原 RoPE kernel 第 18 行使用 volatile float 中间结果；Resize 第 10 行有手工 half 特殊值/次正规数解码，第 15 行为原四项乘加。逐元素代数映射和 owner 证明不能单独支持这个完整谓词为 true。

这不是要求必须先做实验：可以用足够的 API/编译语义来源证明；在现有证据下应保留完整语义谓词 unknown，并继续记录已证明的地址/操作序列事实。现有 numeric_order 请求仍阻止 C3，故目前不是已实施错误，但避免让将来补证据的执行者误以为完整精度条件已经满足。Maximum case-12 已将完整 semantic_equivalence 保留 unknown，是更一致的处理。

## 可接受项及逐任务结论

| 任务 | 源码/方法适用性与本轮判断 |
|---|---|
| 01 Exp | 两路 raw 双物理槽加低精度两块 FP32 scratch 的 `16T` 数据区公式与 InitBuffer 一致；保留乘加/Exp/Cast；没有将 base=1 擅自变成常数输出。流水收益仍未知合理。 |
| 02 Mish | FP32 的 fi=in、fo=out 可在目标 alias/API 允许时删除两块 4T 分配，保留 work 与原两次 +0；`12×3392+512=41216` 正确。未将数学 +0 当可无条件删除的数值操作。 |
| 03 MaskedScale | 原 xf 最后读为 Mul 的输入，复用 outFp 的思路有实际生命周期依据；节约 4T 与 dtype 公式吻合；保留两次乘法、NaN/Inf、RoundMode，直接 int8→float 被正确列为另一个 API 待核候选。 |
| 04 SwiGLU | S=1/7/50 的多小段成本具体，packed 映射 `2rS+j` / `2rS+S+j` 与原式一致；未知 shuffle 与物理边界没有伪装已解决。实际 Action 绑定 P 回执确含 continuous/transpose，transpose 为 needs_evidence；正文 51–86 支持映射/owner 原则，不授权小 C API 的泛化。 |
| 05 AdamW | 四输入双槽/输出单槽得到 FP32 36T、低精度 38T，与原队列和 5 个 FP32 buffer 数量一致；R2明确不能照搬旧 ubFormer 翻倍；特殊恢复路径不被盲目 alias。 |
| 06 Gather | 原 kernel 每元素 rank 次除/模与 xStride 映射明确；odometer 维持非 gather 轴真实源 stride，rank1 简化合理。无新增 UB 时不应因未知 UB 阻止该静态地址方案；实际写安全仍按原/新 owner 单独核验。 |
| 07 StridedSlice | 连续 run 与原 owner 求交的条件明确，run=127 未夸成整输出连续；size1 轴不阻断合轴合理；DataCopyPad/容量 unknown 具体。 |
| 08 GridSampler3D | channel 无关的几何计算是可用的源码不变量；R2识别奇数空间长度的物理写边界，削弱原全覆盖节省预测，改为原64B owner 内完整平面复用。这是实质反馈，不是形式换轮。 |
| 09 GELU | tanh 分支不使用 erfTmp/mask，删除无用分配可省 `20×1024+256=20736B`；保留 none 的 saved 复用及 tanh 的 2^-23 RINT。容量节约未被说成加速。 |
| 10 Sigmoid | 物理 num=2 与 depth=1 分开；DeQue 后再预取最多一个未消费项；T4096 数据区65536B正确，未借原注释192KiB作容量证明。 |
| 11 ForeachAddcdiv | 原三输入一输出及低精度四 FP32 scratch 支持双槽 `8Us+16U·I16`，U2048为65536B；host chunk 不等于每核多 tile，当前实际核数未知被保留。最强替代的延后 Cast/复用 fc 未被当作无代价。 |
| 12 Maximum | 按广播映射分组有源码基础；case11/12/13/20 的分段路径与 sameShape 路径分开；int64 不因测试值小改为 float；原 ternary 与 Vector Max 的 NaN/±0 差异保留 unknown。 |
| 13 RoPE | half-mode partner 在连续半区、row owner 和 cos/sin 复用域均有具体来源；不混入 interleaved 或跨 seq 驻留。36RD+10RD 的保守分配可解释。完整数值 true 与引用定位需按 R2/R4 修正。 |
| 14 Transpose | 原逐输出 rank 解码/按位拷贝有明确成本；suffix/二维/可合轴/fallback 分组合理；int64 两32位通道只作为条件方法，不做数值 Cast。物理 owner 需按 R3 补齐。 |
| 15 Resize | 原 FP32 ResizeCoord 直接计算、四项乘加和边界重合只复用读取的边界明确；整2倍下采样与8倍上采样的读取复用价值不同；未把逻辑访问字节当 HBM。完整数值 true 与 locator 需修正。 |

## 知识、路由、unknown、R2 总体判断

代表正文定位不是单纯填路径：vector-api/batch:85–97 支持 count/stride/alias/GM 边界约束；pipeline:62–74 支持物理槽与队列深度区分及容量；input-tile-residency:121–133 支持同原值、同 owner、完整窗口及部分重叠不可直接删整次加载；transpose:51–86 支持布局映射和物理所有权，不承诺全部 SoC API。具体 T/R 候选是任务侧基于成本和公式提出的试验域，不应被解读为正文已验证这些最优参数。

A 最新 reading-record、B 各结果及 C route-selection-status 已区分完整树咨询、Action 绑定候选、条件采用、正式 C2/C3。抽查 A/case04、B/case09、C/case14 的真实 P 回执：候选确实命中，状态仍为 needs_evidence，不能把 active 知识条目解释为 ready 计划。O 未有 confirmed_plan 时做知识咨询可接受，没有据此声称已执行 C3。

各任务保留任务指定 910C/A3→dav-2201 作为来源清楚的目标适用域，没有冒充设备探测，也没有因无设备探测清空目标平台。容量、目标安装 SDK/API、数值和物理边界是不同问题。主要 unknown 大多具体且可以改变参数/方案；性能未知没有被自动升为实施安全门禁。

所有 R2 仍是原父本上的静态后继，未声称已实施/编译/测量。15 个性能反馈均为 not_tested；GridSampler 的静态预测被 weakened，其余是新增地址、容量、生命周期或特殊值分析支持结构模型。相同 Action 保留是可接受结果。C 组部分 comparison 自我重复，部分 knowledge_use 混入其他算子示例，降低阅读效率但未改变本轮合法性；应清理文字，不应通过强制换 Action 修饰。

可接受这些产物为后续实施提供依据的条件分析。真实 API/物理写规则、完整数值契约、候选正确性与收益仍需后继验证；本审阅没有替这些工作出具结论。
