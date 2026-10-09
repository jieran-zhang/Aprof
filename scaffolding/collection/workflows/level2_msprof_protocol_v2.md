# Level2 完整调用测量协议 v2

版本：`msprof_task_time_exploration_v2`；原始采集器：
`msprof_kernel_time_study_v2`；分析：`msprof_exploration_analysis_v2`。
角色动态库继续使用 `SC_ABI_VERSION=1`。Level1 v1 的 runner、固定 repeat 和解析要求不变。

本协议的主指标是 **每次完整算子调用的设备任务耗时之和**
（`operator_task_sum_us`），单位为 µs。它不是端到端墙钟延迟。
当前真机方法验证环境为 Ascend910_9392（910C/A3）、CANN 9.0.0。

## 计量范围

| 操作 | 主指标是否计入 | 核验方式 |
|---|---|---|
| 选中入口的每个计算 kernel，包括归约、转换、finish 等 | 是 | `op_summary` 中真实符号、类型、持续时间；与 `task_time` 逐条交叉核验 |
| scatter 每次调用从原始输入复制到输出的 D2D reset | 是 | `task_time` 的 `MEMCPY_ASYNC`；必须出现在该次计算序列之前 |
| unsorted_segment_sum 每次调用清零累加器 | 是 | 本环境中 `aclrtMemsetAsync` 同样记为 `MEMCPY_ASYNC`；语义由绑定的适配器源码和调用契约确定 |
| 算法新增的 transpose、清理、转换等设备 kernel | 是 | 必须显式列入该 tiling key 的真实 kernel 序列；遗漏或额外任务使采集失败 |
| 准备输入、输入 H2D、分配输入/输出/workspace/tiling | 否 | 在完整调用计时之前准备；资源大小和地址记录在 native journal |
| 导出输出的 D2H、主机输出布局转换、文件写入、CPU oracle | 否 | native 正式样本完成后执行；输出与验证记录独立保留 |
| 主机提交、主机同步开销和设备任务之间的间隔 | 否 | 单独保留 ACL event、task span 和 inter-task gap，不能替代或混入主指标 |
| warmup 中的计算和 reset | 否 | 同样逐条匹配并计数，随后按 native journal 从正式统计中排除 |

设备任务必须在同一设备、同一 stream 中串行且不重叠；解析器核验任务
ID、起点、持续时间和 kernel 符号，拒绝缺失、重复、额外或未知任务。
每个正式 sample 保留计算 CSV 行号以及辅助 DMA CSV 行号。两个原始 CSV
都进入证据哈希闭包。当前已验证的计算任务类型是 `AI_VECTOR_CORE`；
未验证的计算类型会明确拒绝，不能据此宣称 Cube、混合 kernel 或其他架构已通过。

候选的 `dispatch-launch.json` 放在源目录旁边，由构建 manifest 哈希绑定；
其工作负载条件只使用 shape、dtype、layout 和语义属性。
`verified_dispatch_hits` 只有在实际 profiler kernel 序列匹配后才产生，
不能仅凭预测的 tiling key 宣称入口命中。

## reset 规范化与 standalone 的关系

原始 scatter 的同步 D2D 和 unsorted_segment_sum 的同步 memset 在本环境中
没有出现在 `task_time` 中。prepared 适配器把这些操作规范化为在 runner
明确 stream 上调用 `aclrtMemcpyAsync` / `aclrtMemsetAsync`，并显式同步，
从而保留每次调用的原始状态语义，同时使 reset 的设备成本可计量。
原始算子源码和独立 standalone 入口没有因此改变。

这项规范化只支持与同一 prepared 协议下的基线进行比较。ACL event 与
standalone 端到端时间可能因提交、同步和准备边界不同而变化，不能把
任务耗时之和解释成 standalone 延迟。新的 reset 类型或不同 SDK 的任务
分类需要重新核验；缺失成本不得静默忽略。

## 重复、顺序和输出正确性

- 每个比较使用 6 个独立 native 进程。进程是统计重复单位。
- 每个 case、每种 normal/swapped 配置先为 A/B 各执行 10 次完整 warmup，
  再执行 30 对交替 AB/BA 样本；加载顺序、首对顺序和配置顺序按预先冻结的
  六进程设计变化。每进程、每 case 共 120 个正式 role samples。
- 每个 sample 内的 repeat 按该 case 的原始 prepared 单次 ACL event pilot
  冻结：超过 10 ms 为 1，否则为 10。pilot 为一次 warmup 后一次测量，
  只用于冻结 repeat；A/B、六个进程及后续迭代沿用同一逐 case 策略。
- 每个调用都包括必需 reset 和完整 kernel 序列；不能仅重复最后一个入口。
- 保留所有正式样本，不删除离群值。PMU 核时间缺失时为不可用，不能填零。
- 正式采集验证每个 case/config/role 的最后一个正式 sample 的最后一次输出；
  不声称检查了每个中间输出。独立 standalone correctness 另行执行。
- 多输出算子导出具有固定名字和顺序的 bundle；每个成员独立记录长度、路径
  与 SHA-256。rotary、cummin、dynamic_quant 的全部输出都交给原始 oracle。

## 资源地址对照的当前边界

输入和 tiling 保持在各自角色；normal/swapped 交换输出和 workspace 的物理
地址，并在配置之间保留同一批物理槽位。当前实现要求 A/B **可变资源的
数量、种类和字节数完全匹配**。输入/tiling 可以具有各自不同的布局，但其
角色内身份必须保持不变。改变全局 workspace 布局的候选会被明确拒绝，
需要先审查和验证新的测量资源策略。

未来可采用按种类和序号配对的 workspace 容量并集：为每个槽分配两份
`max(A需求, B需求)` 容量，缺少该资源的一侧保留未使用容量，只绑定实际
存在的角色资源；输出仍要求完全同形。journal 必须记录需求、预留容量、
未使用侧和交换映射，并重新资格验证 A/A 和非对称 workspace 场景。
**这个并集策略尚未实现**，本轮不能假定它已经可用。

## 原始 oracle 的本地临时目录

`unsorted_segment_sum` 的原始 verifier 在 metadata 旁创建可写 mmap，
在共享文件系统上实测会阻塞于 `balance_dirty_pages`。适配器把 metadata
的原始字节复制到 `/tmp/aprof-oracle-uss-*`，让未改动的 verifier 使用该
真实路径；metadata 中所有输入和输出路径保持不变。

证据记录真实 argv、原始 metadata 哈希、归档的 `executed-metadata.json`、
所有 oracle 依赖、复制回来的 `result.json` 哈希，以及临时目录清理状态。
只读 report 验证两个 metadata 字节完全相同和结果复制闭包。
此机制用于 pilot、prepared 采集及复用原 oracle 的 standalone/diagnostic
路径。不得把实际临时路径伪装成原始 argv。

## 原始 profiler 文件的采集位置

`local_tmp_full_copyback_v1` 可将 msprof 的原始输出写入本机 `/tmp`，
以避免共享文件系统的小文件写入影响采集进程退出。native 输出与其他证据
仍写入 campaign。该路径保留真实 argv；采集结束后对全部原始文件和目录
建清单、校验哈希、复制并同步到 campaign，持久化证明完成后才清理临时目录。
失败时保留临时原始数据和实际开销，不自动重试。

采集位置、实际文件系统和 transport producer 哈希参与校准身份。本地采集
必须使用新的显式 epoch，并先取得同一方式的六进程 A/A；原有共享文件系统
A/A 不能用于本地 A/B。`level2_raw_method.py` 的单进程验证只核验采集、
完整调用、输出与证据重放，不能充当六进程校准或优化收益。

## 已取得的方法证据

下列目录位于 `.aprof/runs/level2-skill-graph-base-20261005/`；它们是方法
验证，不是六进程优化收益或正式准入证据。

| 方法验证 | 真实捕获与结果 | 证据目录 |
|---|---|---|
| maximum，case 1，repeat 1 | 160 个计算任务，0 reset；120 正式 samples；normal/swapped 的 A/B 输出通过原始 oracle | `maximum-smoke-measurement-02/`；严格双表只读重放见 `method-replay-task-time-v2/maximum-smoke-measurement-02.json` |
| scatter，case 14，repeat 1 | 160 个计算任务 + 160 D2D reset；全部四个最终输出通过原始 oracle；重放将 reset 成本纳入样本 | `scatter-async-auxiliary-smoke/`；`method-replay-task-time-v2/scatter-async-auxiliary-smoke.json` |
| unsorted_segment_sum，case 20，repeat 1 | 320 个计算任务 + 160 memset reset；四个最终输出经本地 metadata 重放全部通过，每次 oracle 约 0.24–0.27 s | `uss-async-auxiliary-smoke/`；`uss-async-local-oracle-replay-v1/replay.json` |

scatter 的首次 async 采集在尚未实现辅助任务解析时失败；USS 的原始采集
在 native 正常结束后因共享文件系统 oracle 阻塞而由 owner 终止。
这些失败记录保留不变，后续只读解析和独立 CPU oracle 重放另建目录。
它们没有被改写为一次成功的正式采集。
