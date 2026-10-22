# 输入复用补齐：方法、路由与无硬件回归

本文记录输入驻留补齐阶段（O v0003、runtime 0.4.0）。后续组合过滤及自主回放已生成 O v0004、runtime 0.5.0，见[修复说明](autonomous-diagnosis-1.3.0.md)；下文数字与结论保留原阶段范围。

本次继续维护未封版的 graph-base 1.3.0。诊断 v0004、规划 v0002、runtime 0.4.0 和原 Action 前提保持原义；优化知识生成 v0003，集中路由生成 v0002，旧快照及旧配置继续可回放。默认版本不变。

## 缺口判定

原有资料能解释输入复用的部分条件，但没有完整覆盖“同一 kernel、同一 owner 内多个真实消费者使用原输入，保留 UB 原值并删去重复 GM 读取”。因此采用一个新主 recipe，并复用现有支持资料，不新增 family、branch 或 Action。

| 现有方法 | 已有覆盖 | 与本次方法的区别 |
| --- | --- | --- |
| `planning.elementwise.continuous` / `broadcast` | 输出分区、广播映射、尾块、owner 和容量 | 仍适合作为 C2 规划材料，无需新增一级分类 |
| `implementation.buffer-lifetime.reuse` | 不同值在不重叠存活期共用物理槽 | 不能单独解释同一原值如何跨消费者保留及删除哪次 GM 读取 |
| `implementation.memory-transfer.l2-reuse-order` | 遍历顺序和并发缓存工作集 | 保持逻辑读量，不等于删除重复请求 |
| `implementation.memory-transfer.cache-hint` | NORMAL / DISABLE 等缓存策略 | 不能证明 UB 原值仍存在，也不保证 HBM 流量减少 |
| `implementation.fusion-composition.vector_chain_residency` | 链组合、融合边界与中间 GM 物化消除 | 相关原值生命周期可复用；本次不要求增加融合区间 |

新主正文为 [input-tile-residency](../../skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/input-tile-residency.md)。正文包含双消费者实现、输入就绪与最后读完成、物理分配及队列深度公式、有效尾域和布局、别名与原地覆盖、缓存口径及 C2 边界。`references` 复用存活期、缓存、stride 和融合资料；同步与有效域要求在主正文中直接说明。

## Action 路由与使用

`reuse_input_tiles` 保留 `insufficient_input_reuse`、`reuse_domain`、`semantic_equivalence`、`capacity` 四项原前提。实例仍绑定对象、父实现、workload、目标阶段、参数和计划身份。

| 实例的实际变换 | O 候选范围 | C2 判断 |
| --- | --- | --- |
| 原输入片在本 owner 保留，多个消费者复用 | `input-tile-residency` 为主正文；buffer 共槽为支持资料 | 已许可的窗口、通路、顺序和预算内可 P_KEEP |
| 逻辑读取不变，缩短 L2 复用距离 | `l2-reuse-order` | 遍历超出原自由度则重规划 |
| 明确依赖缓存策略 | `cache-hint` | 核验 API 和平台；不据此许可删除 GM 读取 |
| 跨 owner、dispatch、融合区间或矩阵存储层改变 | 先检索相关 family／组合模式 | 重定所有权、同步、通路及预算，不能直接使用本地 UB recipe |

新 recipe 在原 Action 前提以外，还要求：

- `same_input_region`：消费者地址集合、布局、dtype 及有效尾域对应；同一基址不足以证明。
- `input_value_preserved`：原值在最后读完成前未被 in-place、alias、GM producer 或隐式写操作破坏。
- `dependency_lifetime`、`output_ownership`：真实完成依赖与输出独占成立。
- `plan_freedom`：由已确认、hash 绑定的计划产生；驻留窗口和完整物理容量位于许可范围。

unknown 允许条件化 C2 分析，不能授权 C3。方法 gate 为 false 也不能选择实施。Action ready 与方法 ready 分开记录，动作不可用不自动反证 Problem。

`reduce_memory_traffic` 的候选范围也复用本主正文，但保留其自身的饱和／可减流量等前提；相同物理改动按目标去重，不生成第二份收益。原路由中将重复读取删除归给 L2 顺序的描述已纠正。

## 无硬件测试的判定口径

全部指标、架构容量和审读结论均为显式合成假设。测试实际调用诊断、内部 P/O router 和交接校验，记录点读正文及身份；仅形成文档选择和条件分析，不生成虚假的 C3 已实现记录。

回归既保留原“小搬运发射成本／带宽饱和”场景，也补充真正被两个消费者使用的重复输入。旧示例中未被消费的第二次 CopyIn 只能支持死加载审查，不能单独验证本方法。容量按全部物理 InitBuffer 与深度求和；多阶段逻辑存活期不重叠不能自动消除已独立分配的物理内存。

反例覆盖原值破坏、输入版本更新、跨 owner、容量未知／不足、不同尾域／stride 和生命周期未知。另区分 CACHE_DISABLE 对 L2 路径的限制与 UB 保留合法性，以及逻辑 GM 请求、L2 命中和实际 HBM 字节三个口径。删去逻辑读取不推导实测性能。

详细覆盖、独立阅读复核、CPU 结果和历史身份检查见 [本轮检查记录](input-reuse-validation.json)。本轮不运行 SDK 构建、硬件正确性、计时或边权训练；真实收益、架构上限及因果解释仍待后续任务验证。

## 双消费者的实际文档链

合成正例的公式是 `y=round(round(scale*x)+round(x+bias))`。原先两次 GM 读取都供真实消费者使用，输入原值在该 kernel 内不变；每 owner 独占连续输出。假设数据表明 64 KiB 大块传输接近同条件可达带宽、发射等待占比很低，故不把这个场景判成小搬运发射成本。诊断读取 `tiny_transfer_setup_amplification`、`memory_bandwidth_saturation` 和 `insufficient_input_reuse` 的机制正文，区分成本表现与可消除的重复原值读取。

实例使用 `action.reuse_input_tiles`。C2 点读 `planning.elementwise.continuous` 核对已有输出所有权和尾块方案；完整父计划已许可局部搬运及输入生命周期调整时，实际 P 选择为 KEEP，点读文档不登记为新规划。O 由内部 router 返回新主 recipe，保留原 x 给两个消费者，各自运算和最终加法顺序不变，删除第二次 GM 读取。不能直接把参考片段中的 `scale*x+x` 当作本输入公式，丢掉 bias 或原舍入边界。

这里一个输入窗口 W=1 GiB，原逻辑流量为两次读 x 加一次写 y，共 3W；删掉一次已证冗余的输入读取后为 2W。这是逻辑请求演算，不能据此声称 HBM 减少 1 GiB 或获得任何加速。每 tile 为 16384 个 FP32 元素：原 x1、x2、y、z 四个独立物理区共 262144 B；若实际移除 x2 的分配，并以三个合法物理区安排原输入与两支结果，数据区为 196608 B。仍须加入工程其它分配及预留，且等真实读者完成后才覆盖。

最终扩大至 21 个合成场景，结构／路由检查 28 项通过：

| 覆盖组 | 实际行为 |
| --- | --- |
| 小搬运；大块且流量已最小；仅 MTE 占比 | 分别给出搬运合并文档、阻断不可减流量 Action、保留机制 unknown |
| 真双消费者；DISABLE；L2 已命中 | 新驻留主正文就绪；不把 L2 命中或逻辑删读解释成 HBM 收益 |
| 同域短尾；同域 stride | 可给新主正文；stride 另点读搬运辅助资料，保留已合法的原物化路径 |
| 原地覆盖；版本更新；不同 halo／stride；读完成未知 | 保留方法 unknown／反例或原 Action 阻断，不整删必需读取 |
| 容量 unknown／false；计划超容量 | 分别条件化 C2、阻断原 Action、拒绝非法计划 |
| 跨 owner；条件化迁移 owner；P_KEEP 偷改 owner | 分别阻断直接 UB 共享、允许条件分析、拒绝伪装 KEEP |
| 950 平台；Context 缺少搬运技术域 | 不激活受限主配方，不由 Action hint 补造属性 |

脚本导入了 9 个不同知识正文并核对其身份；另有独立 Agent 只接收三份中性原始输入，比较正常复用、原地覆盖及 halo 不同域的文档适用性。数据表、源程序和计划之间的冲突单独审查，不能仅凭 schema 通过或 `reference_ready` 判断材料自洽。所有输出停留在文档选择与条件分析，不生成已实现 C3。

CPU 回归最终按用例去重为 178 项通过、1 项可选开发入口跳过，其中 20 项是新增输入复用测试。首次全量运行发现两处测试仍固定旧知识版本：未来分类把 O 后继写死为 v0003，离线集成仍假定当前 O 为 v0002。前者改为从当前版本递增，后者明确 P v0002／O v0003，分别定向复测通过；运行时实现和 schema 无需更改。原始失败与后继通过记录均在检查摘要中保留。

整包另复制到独立目录，以审计钩子拒绝网络、原工作树、上游和原场景目录读取，重建得到相同优化索引，并回放双消费者 C1→C2、检索新主正文。旧 A/B/C 通过原配置回放仍使用 O v0002，路由完整 hash 不变。来源／同步技术复核另有 13 个路由场景及 30 组尾部整数边界检查。

## 后续扩展

新 family／branch 或 recipe 不自动生成 Action。同一输入复用意图下的新方法先补唯一主正文、方法条件、来源及内部路由，再扩展中央候选范围；固定旧知识与配置身份后生成后继快照。若需要不同硬前提或独立意图，提交知识提案，不放宽旧 Action。跨 owner 驻留、跨 dispatch 状态与矩阵驻留继续使用各自规划与实现材料，本 recipe 不作通用授权。
