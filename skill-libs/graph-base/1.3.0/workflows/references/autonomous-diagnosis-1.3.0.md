# 组合过滤、正文展开与自主诊断回放

本轮维护未封版的 graph-base 1.3.0，runtime 为 0.5.0；诊断知识 v0004、规划 v0002 保持不变，优化知识生成 v0004，路由配置生成 v0003。历史知识、来源清单和交接保留，默认版本不变。

## 三项修复

L2 顺序配方增加 `constraint.l2_cache_enabled` 方法前提。该事实必须绑定当前实例的目标、原始配置及来源：已核验 NORMAL 为 true，DISABLE 为 false，配置或分派不明为 unknown。false 和 unknown 都不能使配方就绪，C3 沿现有严格校验拒绝实施。同 owner 的 UB 输入驻留不依赖此条件。NORMAL 不保证命中、容量或收益；不能由路由提示补造这个事实。

`diagnosis retrieve` 继续提供全量轻目录和邻接线索。Agent 自主决定要读的 Problem，使用 `diagnosis expand` 取得完整正文、分析、来源及其精确身份，并记录阅读理由、触发因素和未解释观测；`diagnosis verify-expansion` 回放核验。展开不产生机制总分、不替 Agent 选择 Problem 或 Action。正文阅读记录可作为 C1 的现有 artifacts 交接，旧 schema 原义保留。

`aprof_runtime.observation_checks.validate_and_derive` 核对原始时间、计数层级和派生依赖。逻辑 GM 与 HBM 分开计算；缺项保留 unknown，明确矛盾为 invalid。L 的旧记录冻结不改，后继使用窗口 2800 μs、MTE active 2750 μs、互斥 issue 40 μs 加 steady 2710 μs，HBM 读写各 1 GiB，得 active-window HBM 混合带宽约 780.903 GB/s；逻辑请求带宽另算，不能与 HBM 基准混比。

## 使用与回放

先从原始观测和源码构造带来源的 Context，执行检索。根据机制差异、反证和未解释观测选择正文，按需展开后再比较候选；列出了候选、要排除机制或据其提出 Action 时，不能只凭目录摘要。读者可以补充候选或保留临时机制，不要求凑齐固定数量。

新的观测或条件形成后继证据与推理快照，不回填历史记录。P/O 路由只采用同范围已核验事实和已确认计划；文档就绪、Action readiness、计划有效性及实际实施分别记录。

本轮先用 CPU 校验三项修复，再由独立 Agent 只接收中性命名的原始输入、源码、workload 和当前计划，自主读取知识并形成结论。不给 Problem、Action、recipe、预期答案或旧分析。实际阅读正文、展开请求、候选取舍及 P/O 路由均保留记录。详细结果见[检查报告](autonomous-diagnosis-validation.json)。

本轮没有 SDK 编译、硬件实验、性能计时或边权训练，也不产生 implemented C3、case_support 或性能结论。

## 七个原始输入的自主回放

三个新 Agent 分别接收 2／3／2 个中性编号输入及正常 workflow 入口，任务上下文未提供目标 Problem、Action 或 recipe，也未提供旧场景分析与维护报告。各自先审读源码和原始计数，检索全部 28 项轻目录，再决定展开；没有固定正文清单。每例的初稿、补充绑定后继、最终展开和阅读理由分别保留。主 Agent 独立回放最终交接、展开及 O 路由，并将阅读记录与包内文件、正文 hash 对照。读取清单见[逐例阅读审计](autonomous-diagnosis-reviews/readings.json)，身份和状态见[逐例回放审计](autonomous-diagnosis-reviews/replay.json)。

下表 Problem 简名均对应 `problem.<简名>`，Action 对应 `action.<简名>`。P 的 `continuous`／`fallback` 为 `planning.elementwise` 下条目；O 的 `coalesce`、`input-tile-residency`、`l2-reuse-order`、`cache-hint` 位于 `implementation.memory-transfer`，`reuse` 位于 `implementation.buffer-lifetime`。表中“读”指执行 Agent 记录的正文语义阅读，runtime 为校验加载整图不算阅读；“采用”均仅为纸面方案。

| 输入与原始区别 | 自主展开的 Problem 正文 | 实例化 Action | P 实读正文与实际选择 | O 实读正文与纸面选择 | 结果及边界 |
| --- | --- | --- | --- | --- | --- |
| 01：128 B 逻辑小请求，issue 52／active 75 μs；HBM 仅参照的 13.98% | tiny_transfer_setup_amplification；后续 memory_bandwidth_saturation、noncontiguous_access | coalesce_contiguous_transfers | continuous；P_KEEP 完整原计划 | coalesce；纸面建议合并。strided-pad 只是命中，未读未采用 | conditional。小请求机制 plausible；给定窗口饱和、骨架跨轴访问被排除。真实 wrapper 的 MTE 指令／stride 与同方向时间线未提供，两项原复合硬前提保持 unknown。 |
| 02：64 KiB，同 tile 原输入供 Muls 和 Adds 两个真实消费者，NORMAL | insufficient_input_reuse、memory_bandwidth_saturation；后续 tiny_transfer_setup_amplification、cache_policy_mismatch | reuse_input_tiles | continuous、fallback；P_KEEP | input-tile-residency、coalesce、l2-reuse-order、cache-hint、buffer-lifetime/reuse；只采用驻留 | 合成合同内 ready。原值、同区间、owner、完成边和完整物理分配闭合；SDK／收益未验证。L2 重排没有新的可交换外轮次，未采用。 |
| 03：与 02 相同的双消费者，显式 DISABLE | 同 02 的四项，逐例应用到本输入 | reuse_input_tiles | continuous、fallback；P_KEEP | 同 02 五项；只采用驻留 | 合成合同内 ready。`l2_cache_enabled=false` 原样保留；L2 配方 needs_evidence，表示已知不兼容，不能实施。UB 驻留仍可用，不借此更改 cache hint。 |
| 04：L 的自洽后继，第二读全 L2 命中；HBM 780.903 GB/s | insufficient_input_reuse、memory_bandwidth_saturation；后续 cache_policy_mismatch | reuse_input_tiles | continuous；P_KEEP | input-tile-residency、l2-reuse-order；只采用驻留 | 合成合同内 ready。HBM 接近同口径参照；复用只保留为局部 GM→UB 机会。第二读已全 L2 命中，不能预测删除 1 GiB HBM；额外关键路径成本 unknown。 |
| 05：双消费者，但 helper 未展开、容量账与最后读完成未知 | 同 02 四项；额外展开 pipeline_serialization | reuse_input_tiles | continuous、fallback；P_CHANGE 条件规划 | 同 02 五项；驻留仅条件参考 | conditional，O needs_evidence。保留 capacity、reuse_domain、最后读／局部兼容等缺项；原计划不完整有效，不能表示为 P_KEEP。流水正文也只支持待查，不能因容量未知认定容量压力。 |
| 06：第二输入区域为 n+1，含 halo；与第一段 n 部分重叠 | insufficient_input_reuse、memory_bandwidth_saturation；后续 cache_policy_mismatch、tiny_transfer_setup_amplification | reuse_input_tiles | continuous 已读但其同 shape／同下标算法不适用；P_KEEP 保留原 halo 计划 | cache-hint、input-tile-residency、l2-reuse-order；无已选直接 recipe | conditional。正文使 `same_input_region=false` 显式保留，拒绝整段删第二读。公共区／独有 halo 的分段方案仍缺；不是 O_KEEP 或 NOOP。 |
| 07：同区间双消费者，首个 Muls 原地改写输入 UB 槽 | 同 06 四项，按本源码应用 | reuse_input_tiles | continuous；P_KEEP | cache-hint、input-tile-residency、l2-reuse-order；驻留仅条件选用 | conditional。保留原始 x 的新布局、最后读／写完成和 SDK 合同未证明；不能让第二消费者读已修改值，也不能把逻辑死亡等同物理空间可回收。 |

02／03／05 还实际读了 `reduce_memory_traffic` 和 `align_cache_policy` Action，06／07 读了 `reduce_memory_traffic`，均未实例化：避免对同一删读重复记收益，也未在 SDK 未核验时推进 cache 变换。各例停止理由和未继续展开的范围在阅读审计中；没有将未读机制直接排除。

## 一个场景如何实际调用

以 01 为例，先由源码中的 `c+=32`、FP32 每次 32 元素和同窗口原始计数构造带 hash／locator 的事实，重算 128 B／逻辑调用、111.848 GB/s HBM 混合带宽。它们共用原始依赖，不能重复计独立支持。`diagnosis retrieve` 返回完整目录后，Agent 第一轮只请求小搬运机制；读到替代解释，再请求带宽饱和与不连续访问。正文要求物理 MTE 和同方向时间线，因此没有把聚合 issue 时间变成已满足的 profile Symptom。

阅读 Action 正文后，实例保持四项原硬前提，绑定当前 tile、地址集合、原 FP32 两步舍入和参数；缺项保持 unknown。C2 调用内部 router、读 continuous 并核对完整原计划，选择 P_KEEP。O 在该计划下调用内部 router；Agent 只读 coalesce，将其作为后续合并的分析资料。最终 C1→C2 为 conditional，且没有构造实施 C3。这个结果说明“能提供相关资料”和“资料已足以授权当前变更”是两件需要分别判断的事。

## 当前仍需补齐的内容

- 公共区／union／halo 的输入加载与消费者视图、逐段所有权和完成边方案；现有同区间驻留 recipe 不能直接授权。
- 破坏性消费者下保留原值的不同布局、复制成本与生命周期证明；不能仅因同地址就删除读取。
- 任意 wrapper／SDK 源码的真实 MTE 参数、对象级时间线、L2／HBM 口径映射仍需任务证据。提取器未实现；当前由 Agent 人工建立可追溯事实，不把假设变成真实采集。
- false 与 unknown 在旧 P/O 路由都显示 needs_evidence，使用者仍须查看原事实和正文。已知不兼容必须阻断采用，不能改成 unknown。

本轮没有新增 Action 或 recipe；补的是现有方法的兼容前提、诊断正文阅读能力和观测算术检查。新 family／branch 的维护方式不变，实际采用仍需当前实例与计划的兼容依据。

## 检查结果

CPU 回归最终按用例身份去重为 262 项：261 通过、1 跳过、0 失败；观测数值模块最终为 52 项。独立复核另检查了 L2 四种事实状态、8 项展开反例、10 份展开及 5 组交接回放，以及 252 项数值字段类型组合；无剩余阻塞。数值修复后的新 L 与冻结派生结果整对象相等。跳过项是可选开发仓库的旧归档入口，技能包运行不依赖该入口。

完整包复制到独立目录后，以 audit hook 禁止网络、原工作树、上游／`/tmp` 和原任务路径访问，重建 P/O 内容与冻结产物一致，D 校验通过；03／04 的展开、交接、O 路由和观测重算可在复制任务中回放。旧 40 个 JSON schema、旧快照、固定来源及 `knowledge.py`／`diagnosis.py`／`bindings.py` 保留字节；结构检查只表示未封版包自洽，不是发布或性能验收。明细见[CPU结果](autonomous-diagnosis-reviews/cpu.json)、[独立复核](autonomous-diagnosis-reviews/independent-review.json)、[独立目录结果](autonomous-diagnosis-reviews/standalone.json)。
