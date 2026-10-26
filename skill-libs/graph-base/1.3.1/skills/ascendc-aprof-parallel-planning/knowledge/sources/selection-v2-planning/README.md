# P 知识补强交付

本轮仅修改 1.3.0 活跃知识叶，未改共享 router/REGION/index、历史快照、runtime、1.2.0。使用 ponytail 的最小完整改动原则：四条已有叶补强，一条确有语义缺口的条件化新叶；不新增 family，不自动新增 Action。无硬件实验。

## 已有条目—来源—缺口—修改

| 叶 ID | 原有可用内容 | 固定代表来源 | 原缺口与本次变化 |
|---|---|---|---|
| planning.elementwise.continuous | 均衡分区、尾块、UB、队列 | asc-devkit Add TPipe/TQue host+kernel 同文件 | 加逻辑算术/必要GM/tile次数分账；短行组合 vs 可真正展平的区别；更多buffer或queue不证明重叠；残余路径反馈 |
| planning.elementwise.broadcast | 合轴位图、零stride、UB/NDDMA平台边界 | cannbot-skills patterns；ops-transformer RoPE README+interleaved host+kernel入口+BSN实现 | 加每元素/每段/源块保留三骨架；源B尺寸与输出尺寸分开；跨owner不自动共享；r行并存 vs 顺序消费预算；真实源复用域与容量/任务数取舍 |
| planning.layout.transpose | 源/输出stride、局部转换、offset表 | ops-nn GatherElements README+tiling+transpose | 中间GM写读不能从成本删去；矩形方向影响输入/输出段数；offset表保留的生命周期代价；consumer布局替代 |
| planning.reduction.split | AR/ARA、partial所有权、合并树 | cannbot-skills group-reduce、multi-axis | 全路径producer/merge分账，GS partial状态及2GSb字节，task与数值树取舍，复用与重算 |
| planning.indexing.coordinate_neighborhood（新） | 原GatherElements不能解释完整坐标/邻域流程 | ops-nn GatherElements组成；ops-transformer RoPE共享参数组成；cann-samples generalGather平台对照 | 显式机制推导的输出空间块/复用轴×空间块/有界源窗口，完整函数槽位、stride、所有权、语义、容量、成本和重规划边界 |

## 新叶的严格身份与适用范围

`planning.indexing.coordinate_neighborhood` 为 conditional template；`evidence_status=mechanism_inference_from_reviewed_source_not_benchmarked`。固定五仓检索没有发现可用的 GridSampler/Resize 完整实现链，必须保留此缺口，不能说“从仓库移植了插值方案”。GatherElements 与采样语义不同；RoPE只证实共享输入分区，并不证明派生几何可合法复用。

正文通过 G（坐标）、B（边界）、H（邻域/权重）、F（有序消费）函数槽位限定。若这些槽位未绑定当前任务，或无法证明源地址/容量/输出独占/数值语义，只能 partial consultation，不能 adopted_full。绑定完成后是完整的所有权和循环骨架，不是可以直接编译的插值kernel。最近邻K=1与加权邻域分别条件化；跨channel/其他轴复用必须证明G/B/H不依赖该轴。

## 路由集成建议（主Agent裁决）

- 新叶 parent `planning.indexing`，不新增 family。
- 仅在真实Context `family=indexing` 且经源码确认 features 含 `coordinate-neighborhood`（名称可按现有命名统一）时召回；如果语义属另一既有family，可允许真实feature走indexing咨询，但不能改写事实family。
- 新route仍要求 `constraint.semantic_equivalence`、`constraint.capacity`、`constraint.task_ownership`，exclude沿用 excluded_templates。**这些是骨架合法性的必要条件，不是已经绑定全部语义槽位的证据**；是否full采用需在选择记录明确槽位与scope。不能自动注入true。
- 把 GatherElements 的正文限制保留；不能为了召回采样新叶放宽GatherElements语义或把它标成完整采用。
- 建议此时先以已有Action条件路由+Action适用性判断接入；若Action并不承载派生重算/复用，保留意图缺口及知识提案，不能修改旧Action硬前提以迁就本叶。

## Action语义审查

- `reuse_input_tiles`：原始输入值保留可适用；坐标/几何结果为派生数据时不能自动适用。
- `hoist_invariant_control`：地址、控制不变量可适用；包含插值权重计算和浮点重排不能仅凭名称套用。
- `batch_vector_api_calls`/`vectorize_scalar_loop`：连续段/批量计算候选仍需原条件；本次叶不证明目标API可执行或Compare/Select等价。
- `dispatch_by_workload`：本次所有骨架先比较参数化通用方案；没有以增加Key为目标，无case ID分派或经验阈值。

## 来源与许可

包内 `knowledge/sources/selection-v2-planning/manifest.json` 包含15个文件的固定revision、原路径、行范围、整文件hash、excerpt hash和5份LICENSE hash。所有文件逐个与 `git show REV:path` 验证字节一致，完整上下文和版权头保留。正文自足；无需读取源码或原工作区才能理解。

| 仓库 | 使用角色 | 平台边界 |
|---|---|---|
| cannbot-skills 41377d0a | 广播合轴与分区、分段/多轴归约 | 明确区分DAV2201和3510；来源示意常数不成为性能阈值 |
| asc-devkit d3788497 | Add队列及实际字节分配 | README A2/A3及950版本范围；队列存在不等于有效重叠 |
| cann-samples 17c948bb | general Gather host分派+kernel，行/输出所有权对照 | 950-only SIMT，不导入A3能力 |
| ops-nn 8b42e125 | GatherElements host/tiling/Scalar/transpose路径 | README A2/A3，950不支持；GM中转与局部Gather分清 |
| ops-transformer d7e6a7c6 | RoPE interleaved分区、共享cos/sin、dtype临时区 | 读具体非arch35路径；README全产品支持不自动给所有组合API资格 |

## CPU检查与仍缺内容

`verification.json`：5叶schema有效、47个来源引用hash/行范围有效、162组输出矩形所有权与几何次数公式检查通过。没有编译源码、数值或性能验证；没有以CPU公式测试证明插值算法正确。

仍缺：固定来源完整采样实现/API组合；目标平台寄存器/栈/spill成本；通用时间权重；派生几何复用的合法注册Action是否需要提案；所有控制/数值槽位由当前任务证明。新知识不自动填充这些unknown，也不因缺少硬件收益而否决合理条件试验。
