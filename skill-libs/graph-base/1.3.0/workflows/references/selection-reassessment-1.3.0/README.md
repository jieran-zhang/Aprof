# 工作量比较、覆盖与轮次复盘：1.3.0 维护记录

本次维护继续使用未封版 graph-base 1.3.0，runtime 0.7.0，诊断 v0006、P v0003、O v0006、路由 v0005。没有修改默认版本，没有新的硬件实验、边权训练或 memory 收集。结构检查与源码回归不证明真实瓶颈、加速比、HAP 或因果正确性。

## 选择与 R2 行为变化

[Action 选择流程](../action-selection.md)先要求读取完整路径、实际 workload、必要机制和 P/O 骨架，再比较候选。新增 [decision v2](../action-decision-v2.md)把同一份路径分域、工作量、覆盖、代价和残余通过 ID 连接到最终选择；禁止用保留工作冒充减省收益，已识别的最强替代不能从选择理由中消失。公式的符号、单位与依据分开记录，不把字节、操作和同步相加成通用性能总分。

性能尚未测量不阻断源代码与知识支持的方案。必要的地址、数值、依赖、API 和资源条件仍在实施前成立；这些条件可由源码和参数公式补齐。检查器不能判断自然语言估算是否真实或最优，因此自主回归后另作语义复核，不以字段齐全代替分析。

R2 分别核对结构是否实现、正确性是否有效、真实测量范围、机制判断和归因限制。它可以修复、继续、调参、回到 C2 重规划、回到 C1 比较机制或补证据；没有强制换 Action。候选、父本和 workload 绑定到反馈证据。原域只测部分 case 时保存精确 case 集，不扩大覆盖、不回填旧记录。有效反馈还须将前轮冻结的逐 case 完整 workload 与捕获 payload 对照，不能凭同名 case ID 借用不同 shape、参数或精度限制的测量；详见 [workload 绑定审阅](review-decision/workload-binding.md)。无效/未测/正确性失败不能证明性能假设。

Tiling Key 仍是已论证方案的分派实现；先比较通用或参数化骨架及其不足。case ID 只定位测试成员，不作为分派条件。本轮没有新增以 Key 数量或动作多样性为目标的规则。

## P/O 知识变化

| 范围 | 补强或新增 | 对选择的作用 |
|---|---|---|
| P elementwise/continuous | 逻辑计算、必要GM、tile次数分账，短行组合与真实展平，buffer/任务/尾部取舍 | 区分减少核内调用与减少独立任务，避免“tile越大越好” |
| P elementwise/broadcast | 每元素、每段、源块驻留三种骨架，广播合轴与复用轴，源尺寸和输出尺寸分别预算 | 比较解码减省、源读取减省及驻留/并行度代价 |
| P layout/transpose | 输入输出矩形、局部转换、offset表生命周期和GM中转 | 不从成本中漏掉中间GM写读，比较源连续性与输出连续性 |
| P reduction/split | producer/merge、partial状态与流量、归并数值顺序 | 任务数不能脱离合并工作和资源成本比较 |
| P indexing（新增叶） | `coordinate_neighborhood`：G/B/H/F语义槽位、空间块、复用轴×空间块、有界源窗口 | 通用采样骨架；来源组成+机制推导，不冒充上游完整采样实现 |
| O vector-api（新增叶） | `compare_select_tail`：具体重载、模式、predicate、A2/A3的256B整块、8KB临时UB、950隔离 | 比较批处理减少的调用和增加的padding/初始化/临时存储；修正旧count泛化 |
| O memory-transfer / precision-boundaries | 短行组合与平坦连续、GM/UB不同单位；三元选择和Max数值语义 | API或数值不等价必须调整实现，不能靠性能假设绕过 |
| O pipeline-sync | tile×slot、物理slot与队列depth、等待/发射及占用 | 有queue不等于重叠；多buffer可能挤小tile或驻留区 |
| O buffer-lifetime / scalar-control | 原始值、派生值、重算和存储复用分开，寄存器/UB与活跃范围成本 | 不把任意数学派生计算套入控制外提或输入复用Action |
| O tiling-tail/dispatch | 通用/参数化先比较，语义或资源分域、fallback、代码代价 | 不把新增Key当收益来源，不用case特判替代骨架 |

四条已有 P 叶、八条已有 O 叶得到补强，新增各一条叶；不新增一级 family/branch，也不自动生成 Action。来源来自五个固定仓库。完整上下文、许可及 hash 归档，正文可独立使用。详见 [P覆盖](planning/DELIVERY.md)、[O覆盖](optimization/COVERAGE.md)与[新增来源清单](../knowledge-sources-selection-v2.json)。

## 独立复核与兼容

[知识复核](review-knowledge/REPORT.md)检查固定源码、host/tiling/kernel路径、平台与API边界，修正固定核数下增tile不减少独立task的表述。[运行时复核](review-decision/REPORT.md)重放并修正跨候选证据、测量范围、补证据伪装实施、同名预测覆盖和合法绝对计时引用等问题。复验记录只证明这些边界的结构行为。

旧 schema 与冻结图保留原字节；D5继续要求decision v1，D6要求v2。每条预测更新的证据也单独核对尝试身份，不能绕过结构/机制回执的范围检查。

旧知识正文按原hash归档，只有通过冻结owner/record成员检查的知识引用才允许读历史正文。旧来源总清单不修改，新增来源另立清单，避免破坏D4/D5历史身份。

## 尚未解决的知识与证据

- 固定来源未提供完整通用三维采样的 host/tiling/kernel 链。已有二维插值API和Triton staging经验不能补齐当前全部语义；新骨架必须绑定本任务的坐标、边界、邻域、权重与消费顺序。
- 派生几何/权重结果复用若不属于已注册意图，保留比较机会与知识提案，不放宽 `reuse_input_tiles` 或 `hoist_invariant_control`。本轮没有凭收益想象自动新增Action。
- 不同dtype、短tail的最优实现、实际spill、缓存/并发行为和时间贡献仍需后续目标平台证据。没有统一性能阈值，也不能从源码操作次数直接推出加速比。
- 自主回归只检查知识如何影响假设和条件方案，不将文档召回率、Action种类或结构通过率当性能评价。

CPU与独立目录验收完成：435项测试分批覆盖434通过、1跳过；新旧各15任务、30轮记录回放通过。完整结果见[检查报告](checks/README.md)，逐算子选择与实际文档见[自主回归表](../selection-regression-15/README.md)，语义问题及修复见[独立复核](review-autonomy/REPORT.md)。
