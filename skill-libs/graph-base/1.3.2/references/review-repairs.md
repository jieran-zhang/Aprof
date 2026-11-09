# MR 555 评审修复与验证

## 本轮实现

本轮在 graph-base 1.3.2 交付上补齐评审参考、独立 reviewer、指标工具和算法注入。原始来源字节、知识快照和 schema 继续由现有校验维护。

## 验证记录

- 本地针对性测试通过 19 项，覆盖算法 oracle、输入域、重复值和指标缺失/无效值。
- CANN 8.5 / dav-2201 实际完成 probe 及四份算法 kernel 的编译与设备 ELF 链接。
- 两个算法的 baseline/injected 共四份实际 kernel 在 Ascend910 / dav-2201、CANN 8.5 上通过固定 128 元素输入的完整输出校验，TopK 同时核对索引。Softmax 最大绝对误差约 1.70e-8。
- 生成的 ACL runner 同时检查退出码和输出 oracle。设备验证使用纯 AIV 编译，盲测 alignment 仍待独立执行，远端门禁按新提交结果记录。
- SCA 人工审核与 A5 性能验证单独跟踪。

## 逐项修改位置

### 1. 插件元数据中的项目网址无法访问

原评论 ID `192837470`。

插件网址已改为真实 GitHub 来源和 asc-tools 目标仓库。

[修改依据](../.claude-plugin/plugin.json)

### 2. 安装与调用方式不应限定 Cursor

原评论 ID `192838002`。

安装器支持显式宿主目录，提供 Claude/Codex/AGENTS 入口，不限定 Cursor。

[修改依据](../tools/install.py)

### 3. 中文版注入说明的正文却是英文

原评论 ID `192838346`。

现行注入技能正文与 recipe 说明均使用中文。旧英文正文的中文入口随旧版交付移除。

[修改依据](../skills/ascendc-aprof-inject-problems/SKILL.md)

### 4. 确认 kernel 编译命令和工具链参数

原评论 ID `192842414`。

在 CANN 8.5 实测发现旧 --asc-aicore-lang 无效。脚本按 help 选择语言选项，增加 C++17 和 host 架构 include，probe 与四份算法 kernel 均完成编译链接。dav-3510 需要支持该 ISA 的 SDK。

[修改依据](../skills/ascendc-kernel-direct-invoke/references/build-kernel.md)

### 5. 确认 DAV_3510 / 950 离散计算使用 SIMT 的适用性

原评论 ID `192843756`。

新增 3510/SIMT 说明：非规则索引/控制可比较 SIMT，但必须匹配 ISA、SDK、线程、寄存器、访存和同步条件。是适用性回答，不是该离散算子的实测结论。

[修改依据](../skills/npu-arch/references/regbase-simt.md)

### 6. 英文文件名对应的正文仍是中文

原评论 ID `192844250`。

旧 api-algorithm-diagnosis-metrics_en.md 假英文副本未导入；本轮明确只保留中文，不伪造翻译。

[修改依据](../IMPORT.md)

### 7. 规范确认：skills 目录无需中英双份 Markdown

原评论 ID `192871312`。

遵循评审确认的 skills 无需中英双份，不再生成重复 _en 文档。

[修改依据](../IMPORT.md)

### 8. 安装命令及路径与 asc-tools 目录布局不一致

原评论 ID `192876096`。

包安装根及来源映射明确，完整包安装器按 registry 的包内路径建立链接。

[修改依据](../tools/install.py)

### 9. 工作流依赖的 CANNBot skill 无法直接获取

原评论 ID `192876765`。

workflow 依赖列表为空，所需支持技能及固定 CANNBot 来源随包提供，不要求获取私有 cannBot skill。

[修改依据](../skills/registry.json)

### 10. 安装注册的 diagnosis skill 名称与实际名称不一致

原评论 ID `192877557`。

注册名和真实 SKILL 的 name 均为 ascendc-aprof-diagnosis。

[修改依据](../skills/registry.json)

### 11. 要求独立 reviewer，但没有对应 agent 文件

原评论 ID `192878042`。

新增 aprof-reviewer 独立角色并登记 workflow、插件和 agent 注册表。协调者调用独立上下文审查，C3 产物绑定最终源码及计划 hash。

[修改依据](../workflows/agents/reviewer.md)

### 12. 建议遵循仓库的 SKILL + references 组织方式

原评论 ID `192900103`。

顶层及各技能采用 SKILL 加 references 的阅读入口。版本化 graph/knowledge 与 runtime 由明确链接进入，原始身份由导入校验维护。

[修改依据](../references/README.md)

### 13. 解释 hypotheses / metrics 最多三条的依据

原评论 ID `192921720`。

不再强制最多三条 hypotheses/metrics，也没有固定 top-k；要求按事实和未解释观测展开必要候选。

[修改依据](../skills/ascendc-aprof-diagnosis/SKILL.md)

### 14. 触发条件应覆盖输入源码，不限于仅有 kernel 源码

原评论 ID `192998308`。

诊断输入包含当前父版本源码、host/tiling/kernel 理解、workload 和已有证据，不要求只有裸 kernel。

[修改依据](../workflows/contracts/diagnosis.md)

### 15. 源码路由文档不应混入 profiling 阶段描述

原评论 ID `193004610`。

新增纯源码观察参考，描述有效域、循环、API、dtype、分派和所有权，后续交接链接现行 C1。

[修改依据](../skills/ascendc-aprof-diagnosis/references/source-observations.md)

### 16. 删除路由文档中无关的 CANNBot 加载说明

原评论 ID `193006349`。

当前入口使用本地已固定来源和真实技能路径；旧 source-hypothesis-routing 中无关的外部 CANNBot 加载要求不再是当前路由入口。

[修改依据](../skills/ascendc-aprof-diagnosis/SKILL.md)

### 17. Scalar 现象的源码判定条件不清晰

原评论 ID `193008544`。

Scalar 源码现象已分解为逐元素 Scalar 循环、有效域/API/地址依赖和 dtype/分支/别名条件；不把源码观察直接认定为热点。extractor 仍明确未实现。

[修改依据](../skills/ascendc-aprof-diagnosis/graph/symptoms/symptom.source.scalar_element_loop.md)

### 18. 算子专属规则与通用路由规则混用

原评论 ID `193018097`。

通用诊断记录事实/机制；具体算法方案进入 P 的 family 路由及模板，并要求核对平台/workload。模板可检索不代表对所有算子适用。

[修改依据](../skills/ascendc-aprof-parallel-planning/knowledge/families/sort-topk/ROUTER.md)

### 19. 输出要求与 diagnosis_hypotheses JSON 契约不一致

原评论 ID `193021320`。

补充旧 hypotheses.id/summary/confidence 到稳定假设 ID、机制摘要和证据判断的迁移关系，明确现行 C1 及 strict schema 版本入口。

[修改依据](../skills/ascendc-aprof-diagnosis/references/output-contract.md)

### 20. 增加到 diagnosis_hypotheses 契约定义的链接

原评论 ID `193022841`。

诊断 SKILL 直接链接现行 C1 contract、选择规则和图格式，不再要求读者自行寻找输出契约。

[修改依据](../skills/ascendc-aprof-diagnosis/SKILL.md)

### 21. 统一各文档使用的证据等级定义与枚举

原评论 ID `193026597`。

当前声明依据统一为 source_statement/code_fact/mechanism_inference/case_support/legacy_seed，schema 明确定义；旧直接/派生/Trace 等历史措辞不再冒充同一现行枚举。

[修改依据](../skills/ascendc-aprof-diagnosis/graph/FORMAT.md)

### 22. 明确证据等级由谁使用、如何影响后续判断

原评论 ID `193033885`。

C1 的协调者/规划/采集和 C2/C3 消费证据；证据影响实施条件、性能假设和未知状态。派生事实不能算独立支持，合成输入不升级为硬件证据。

[修改依据](../workflows/contracts/diagnosis.md)

### 23. 区分 bias table buffer 与 Fixpipe buffer，并说明 BT 容量用途

原评论 ID `193068124`。

分别定义 BT bias 与 FP Fixpipe/量化用途，提供 BT 按 bias tile、物理槽及对齐计算容量的公式和实例，FP 容量独立核实。

[修改依据](../skills/npu-arch/references/buffers-and-frequency.md)

### 24. 明确 Current Freq / Rated Freq 对应的频率域

原评论 ID `193070959`。

按官方 OpBasicInfo 定义解释 Current Freq 与 Rated Freq，明确记录 clock domain、核类型、单位与采集窗口，定义可比条件和周期换算。

[修改依据](../skills/npu-arch/references/buffers-and-frequency.md)

### 25. 明确 GM / L2 / L1 带宽以及读写方向

原评论 ID `193072153`。

观测 contract 要求计数 layer、同窗口和 read/write 方向；logical_gm 与 hbm 不可混算，带宽参照须同层级同口径，缺实际层级不能称饱和。

[修改依据](../workflows/references/observation-checks.md)

### 26. Compute 主导判定需覆盖 Cube，或明确 Vector 范围

原评论 ID `193078447`。

入口明确现有硬件证据范围。计算主导与 MTE 判断按 Vector、Cube、混合三类分别核对引擎指标、核类型和关键路径。

[修改依据](../skills/ascendc-aprof-profiling/references/metrics.md)

### 27. workspace 属于 GM，不应作为片上内存指标混写

原评论 ID `193086875`。

当前 P/O 模板将 GM workspace 与 UB/L1/L0 容量分别记账；如 split reduction 的 GM partial 写读和 epilogue 的 GM 槽位均明确。

[修改依据](../skills/ascendc-aprof-parallel-planning/knowledge/families/reduction/templates/split.md)

### 28. API/Scalar 规范内容与算法选择主题不匹配

原评论 ID `193100101`。

当前规划材料已有真正的算法/数值结构：静态 Split-K、StreamK、attention partial 合并、统计归约；API/Scalar 实现材料另有自己的技能/branch。此结论不包含算法注入评测。

[修改依据](../skills/ascendc-aprof-parallel-planning/knowledge/families/matmul/templates/splitk.md)

### 29. 区分 npu-arch 技能入口与实际硬件数据来源

原评论 ID `193103990`。

npu-arch 明确为技能入口；实际值来自 PlatformAscendC、设备探测或有来源的 SDK 配置，保留原始值和 provenance，不把 /npu-arch 本身当硬件测量。

[修改依据](../skills/npu-arch/SKILL.md)

### 30. 核利用率 metric 的定义重复，需要统一维护位置

原评论 ID `193105855`。

建立现行指标统一维护位置与消费者，诊断、规划、优化和采集入口均已引用。历史冻结模板的计数定义按其版本保留。

[修改依据](../skills/ascendc-aprof-profiling/references/metrics.md)

### 31. 注入工具文档中 22 处命令和引用缺少 tool-ops-optimize 路径层

原评论 ID `193109211`。

现行命令从完整包根使用 skills/ascendc-aprof-inject-problems/tools/inject_case.py；在 asc-tools 根运行时前缀为 skills/tool-ops-optimize/。旧 skills/aprof 路径不再作为活跃入口。

[修改依据](../skills/ascendc-aprof-inject-problems/SKILL.md)

### 32. 六篇 tiling 注入文档没有被索引登记，成为孤儿文档

原评论 ID `193109221`。

采用原意见允许的删除处置，旧六篇 tiling recipe 及英文镜像未恢复。现行两个算法 recipe 均由 SKILL 和 registry 登记并链接。

[修改依据](../skills/ascendc-aprof-inject-problems/references/algorithm-recipes.md)

### 33. api_algorithm 评测仅覆盖 API/Scalar，缺少算法选择 recipe

原评论 ID `193109227`。

新增 full_sort_for_topk 与 two_pass_softmax，生成 baseline/injected Ascend C kernel、清单和 CPU oracle，说明复杂度、读写遍数、诊断判据和隔离标签的 alignment 方法。

[修改依据](../skills/ascendc-aprof-inject-problems/references/algorithm-recipes.md)

### 34. [P0] 核并行策略缺少减核和空闲核早返回方向

原评论 ID `193126982`。

统一可达核数为 min(block_dim,total_tasks,available_cores)，增加过开核减核、动态 shape 重算和有同步参与者约束的空闲退出，提供脚本检查与测试。

[修改依据](../skills/ascendc-aprof-optimization/references/task-parallelism.md)

### 35. [P1] 路由条件重叠，缺优先级、阈值、术语定义和 playbook 链接

原评论 ID `193126988`。

明确判定顺序，区分过开核、启动不足、MatMul 欠并行与末轮碎片，给出不均衡筛查阈值、术语解释和模板链接。

[修改依据](../skills/ascendc-aprof-optimization/references/task-parallelism.md)

### 36. [P1] 容量模型缺可代入公式，枚举、命名和核数分母不一致

原评论 ID `193126995`。

补齐每核有效字节门槛、同时存活 UB、Split-K 和 Split-KV workspace 公式，分别声明核类型、输入来源和历史术语迁移。

[修改依据](../skills/ascendc-aprof-optimization/references/task-parallelism.md)

### 37. [P1] Required Evidence 缺数据来源与证据等级

原评论 ID `193127005`。

逐项映射 OpBasicInfo、PipeUtilization、TilingData 和平台 API 的真实字段及单位，记录直接/派生/trace 与现行 basis 的关系。表头变体显式绑定，缺项保持 unknown。

[修改依据](../skills/ascendc-aprof-profiling/references/metrics.md)

### 38. [P0] 缺前后检查、失败交接和固定 strategy_id

原评论 ID `193127012`。

补齐 pre_patch_checks、post_patch_checks、failure_handoff、固定 strategy_id 和新旧身份映射。精度、运行、挂起和缺采集分别交接对应技能，搬运/流水根因转出本族。

[修改依据](../skills/ascendc-aprof-optimization/references/task-parallelism.md)

### 39. [P1] Metric Delta 缺可判定阈值、容忍度和具体字段

原评论 ID `193127016`。

按减核、增核、均衡与 split 场景给出具体指标、方向、量化目标和回归容忍度。字节成本先换算为时间，比较完整调用并保留实际阈值。

[修改依据](../skills/ascendc-aprof-optimization/references/task-parallelism.md)

### 40. [P2] _en 文件与中文逐字相同，英文入口链接也不正确

原评论 ID `193127020`。

未继续提供字节相同的假 _en 文档。当前中文入口引用中文正文，按评审建议采用只维护中文这一选项。

[修改依据](../IMPORT.md)
