# graph-base 0.5.1 稳定版验收记录

## 当前修订（2026-10-15，优化与事后归档分工）

**0.5.1 已封存并成为默认版本。** 根据用户明确的职责边界，本版已验证协议为
`shared_buffer_msprof_task_window_v4`：优化 agent 在任务临时目录采集和解析原始数据，
不复制 profiler 目录，不建立证据 CAS。完整正确性、Task 归属、前后控制和在线验收
仍计入优化预算；只有在线回放完成且未超时，才能产生通过的任务终态。

任务结束后如训练需要 trace，由收集或训练 agent 显式归档；归档和独立归档审计
分别计时，不计入算子优化成本。发布仍要求完整证据及独立审计，事后工作不能补采、
调整参数或改写任务结论。普通优化交付最终源码和简明报告，临时 profile 仅用于
当前任务；没有收集需求时，不要求长期保留。

此次只改变职责与成本边界，保留 v2 的 10 ms pilot、全部 cases、六周期、正确性、
控制阈值和单任务上限。历史失败仍为失败。

v4 的一次性六槽硬件确认已全部通过：exp、sigmoid 各完成 20 case、120 个正式周期，
以及 exp case 1/9、sigmoid case 1/4 的四项独立观察；外层任务正常退出。
全部 case、周期及汇总控制的最差值如下，阈值保持不变：

| 算子 | 在线采集及完整准入耗时 | 最大 A/A 角色偏差 | 最大跨会话漂移 | 最大 CV |
| --- | ---: | ---: | ---: | ---: |
| exp | 1106.973 秒 | 0.189% | 0.661% | 3.687% |
| sigmoid | 1029.735 秒 | 0.230% | 0.383% | 1.456% |

结果位于工作区 `validation-graph-base-0.5.1-20261014/production-task-window-confirmation-v4-local/`。
这些 A/A 结果支持测量方法资格，不是优化规则的收益证明，也不单独确定旧偏差的硬件根因。
任务后的六项证据归档由独立收集 agent 完成，共 3749.452 秒（约 62.49 分钟），
全部单独计入事后收集成本，没有计入上述在线优化耗时。

第一次真实封存审计在 816.816 秒后失败：历史离线导出研究要求旧版 `traces.py`，
顶层历史清单遗漏了已存在的源码归档索引，回放因此读取了当前版本并拒绝哈希不符。
失败回执保留于 `release-seal-v4-local-v1/`。新补充入口只提供精确旧源码引用，
继续执行原独立 publisher 和原 sealer 的全部检查；冻结包、旧清单、实验数据及
硬件阈值没有改动。第二次完整审计耗时 1315.049 秒，通过历史和本轮完整 campaign
重算后，在四个 observation terminal 的引用比较处拒绝：实际路径和 64 位哈希
相同，`sha256:` 前缀表示不一致导致直接字典比较失败。失败回执保留于
`release-seal-v4-local-v2/`。补充入口仅对固定四条引用规范化前缀，仍重算真实文件
哈希并拒绝缺项、重复或内容改动；原 publisher、安装 probe 和硬件数据未改写。
18 项定向检查与独立审查通过。第三次完整审计在 `release-seal-v4-local-v3/`
正常退出，通过全部历史与本轮回放、独立安装副本的两算子回放以及发布检查，
真实总耗时 1793.080 秒。该耗时属于任务后的发布审计，不计入优化成本。

稳定 manifest 为 `skill-libs/graph-base/0.5.1/release.json`，SHA256：
`1beca6ff9ea1fa3cda83904c8637ce5d047860cbefe86b3ad4d247ff22309b1b`。
包含 214 个文件，runtime 0.2.2；catalog 和两个宿主 marketplace 默认入口已切换。
封存来源为原 HEAD `0add412ad53041bbedbe325a80c6cbda6d7adbaa` 上的工作区完整文件库存；
manifest 明确保留 `committed_payload_claimed=false`，没有声称这些改动已提交或推送。
1.0.0 仍是候选，本次测量方法资格不授予优化规则晋升。

封存后的发布库存校验再次通过：0.5.1 为 214 个文件，0.5.0 的 200 个文件
保持原字节；默认 registry/宿主入口一致性检查通过。独立收集 agent 保存了
51 个 producer 源码（1,082,793 bytes，4.374 秒），供后续脚手架修改后的历史回放。
索引位于 `post-seal-producer-snapshot-v1/snapshot/index.json`，SHA256：
`00c10986cb3e8fdde7c519bd37911288ed131c7f207db5de17f46879510dc39e`。
确认所有任务后归档及封存成功后，已删除本轮四个任务自有 `/tmp` 根目录；
清理回执为 `post-task-task-window-v4-local-20261015/temporary-cleanup.json`。
持久证据与全部历史失败记录保留；优化 agent 不承担这些归档操作。

## 历史候选（2026-10-15，完整 CAS 存储）

**0.5.1 仍未封存，默认仍为 0.5.0。** 新候选协议
`shared_buffer_msprof_task_window_v3` 保留 v2 的 10 ms 校准目标、全部 case、六个周期、
正确性、控制阈值及包含独立回放的 3600 秒预算，仅改为完整 CAS profile 持久化。
捕获和导出的完整清单、原始文件、CSV、数据库与日志均保留，去掉额外的持久目录副本。
删除临时 profile 前仍完整校验源文件和 CAS，并同步相关 CAS 目录项。

软件检查已完成：24 项 CAS 边界检查与 35 项完整回放检查通过；采集器、资格检查、
发布检查及测量入口另有 52 项集成检查通过。这些测试没有硬件准入权。
固定两个历史 profile 的 old/new/new/old 离线对照完成八槽，完整 CAS 重建均通过，
但串行 CAS 校验的成本高于旧复制方案：case 1 的相关组件均值为 6.342 秒对 2.644 秒，
case 9 为 5.646 秒对 1.958 秒。该实现不支持启动硬件验收；其后完成过保持完整读取的
并行校验与数据库批量读取修订，现已转向任务本地方案。该对照不是新性能样本，
也不是完整采集成本证明。
完整源码归档和全部八槽结果保存在
`validation-graph-base-0.5.1-20261014/evidence/task-window-v3-cas-cost-v1/`。

## 历史结论（2026-10-14，Task-window v2/10 ms 终局）

**0.5.1 仍未封存，默认版本仍为 0.5.0。** 本轮 exp 采集在 3600.361 秒预算处超时，
保留 114/120 个正式周期；sigmoid 在 3538.9007 秒内完成 120/120 周期采集，
随后原预算内的独立回放超时 60.0284 秒。两槽终态均为 failed，四个依赖观察槽
均为 not_run，整轮 `accepted=false`。后来对冻结的 sigmoid 数据进行只读历史回放，
162.6897 秒通过（20 case、120 周期，`stable=true`）；这不追认原流程，
也不证明 3600 秒预算可完成全量资格。53 个 producer、完整 213 文件候选包、
实际终态和部分 scratch 已独立归档；失败 leaf 保留两种不同的失败原因，
只授予历史回放身份，不授予测量或发布准入。

## 历史结论（2026-10-14，Task-window 首轮结束）

**0.5.1 仍未封存，默认版本为 0.5.0。** `production-task-window-confirmation-v1`
采用 baseline-only pilot 冻结 50 ms 目标窗口、每 case 六个独立周期，两个算子均因
3600 秒预算超时停止：exp 实际 3600.928 秒，保存 76/120 个正式周期；sigmoid
实际 3600.350 秒，保存 78/120 个正式周期。各自 20 个 pilot 已完成。已保存周期
的采集控制均通过，但全量采集和独立准入未完成，不能据此宣布测量方法合格。

两个 confirmation 的终态均为 failed；四个依赖观察槽均为 not_run。
外层 controller 正常结束，只代表失败流程收尾成功。独立六槽回放实际耗时
7.623 秒，返回 `complete=true, accepted=false`。原阈值、全部失败记录和未完成
profile 保留，下一轮不续跑本轮数据。

修改前的 52 个 producer 源码和完整 213 文件候选包已归档于工作区
`validation-graph-base-0.5.1-20261014/measurement-task-window-v1-failure-evidence-20261014/`。
源码 index SHA256 为 `42d02a1df4aa0b8b7d88bd934249597371dc09511e781b6b57b273efabd00f71`；
独立回放结果 SHA256 为 `bbcaef469db0126bc718ecfd2dd0c166287f9024ae0bba2cebf7a9d8e3f8a091`。
已完成冻结依赖读取的离线成本对照，结果及新的固定窗口候选见下一节；尚无证据证明
整轮预算已满足。动态 profile/CAS 的 metadata-proof 提案已撤回：真实
测试发现同尺寸改写可能发生在同一个文件时间戳刻度内，stat tuple 不变。
profile/CAS 继续完整读取校验。冻结依赖只有经本地单调时钟隔开至少一秒的两次
完整哈希一致后才允许复用，等待时间本身不能升级旧 proof；其支持范围限定为
当前 Linux overlay/JuiceFS。无 sleep 的固定 32 次新复现全部拒绝改写（其中
29 次 stat 未变），此前 32 次中漏检 30 次的原实现与复现也保留。

## Task-window v2 候选修订（尚未硬件准入）

固定 old/new/new/old 四槽离线来源校验对照已完成。旧实现耗时
13.7487/12.9777 秒，新实现为 6.8226/6.6336 秒；除预登记的 collector 源码哈希外，
完整输出一致。每槽实际读取量由 5.279 GB 降至约 2.009 GB。此处只测来源库存
校验，不包括 profiler、CAS、oracle、独立回放或硬件运行；不能据此宣称整轮已满足预算。
对照第一轮在计时前因两种独立哈希函数的计数覆盖不全停止，零性能样本，原记录保留；
修正后的第二轮才产生上述四槽结果。

该节省量不足以弥补 50 ms 方案的整轮成本。因此新候选使用独立的
`shared_buffer_msprof_task_window_v2`：把固定预测目标改为 10 ms，仍用新 baseline-only
pilot 一次选择每 case 的 R，不能读取 v1 的 R 后继续采样。保留全部 20 cases、六个
新进程周期、30 对正式样本及前后各 30 对 A/A、原正确性与控制阈值、完整 Task 归属、
失败即停止和 3600 秒上限。新目标尚未证明稳定或满足预算，须重新完成硬件资格确认。

修改前完整 213 文件候选已再次归档于
`validation-graph-base-0.5.1-20261014/task-window-v2-10ms-design/pre-change/`，
index SHA256 为 `acefc7f3e51336db89cb4f94f39e2e7b860a05cf9ec0f3a6bd2bacba697959df`，
逐文件与离线对照冻结清单相等。旧 50 ms 失败叶回放继续独立绑定并明确不可发布。

## 历史进展（按发生顺序保留）

状态：未封存候选。旧 Event v2 独立生产确认中，sigmoid 全部 20 case 及两条时间线通过；
exp 在 case 10、第三个进程周期触发控制失败。整轮 `accepted: false`。
根据 kernel 优化目标，候选已将主性能指标改为完整目标任务的 `Task Duration`。
关闭 PMU 的独立任务诊断已完成；首次全量 Task 确认因成本预估提前中止，
保留 14 个控制通过的完整周期和第 15 个周期的部分证据，尚无全量准入回执。
离线存储对照已支持本地导出降本；Task v2 的本地工作目录、完整证据迁移、
回放和独立安装已通过软件检查。新的全量硬件确认中，exp case 1、cycle 3
在前后 Task Duration 共同漂移约 2.29% 时按原 2% 门槛停止；sigmoid 的 20 case、
120 个周期完整采集并返回 stable=true，采集器 2698.25 秒正常退出。
父进程的无缓存独立回放另耗时 1182.82 秒仍未结束，root 按成本中止，外层退出 143；
完整原始数据和采集回执保留，sigmoid 父回放终态、四个插桩对照和 campaign 汇总未完成。
该轮不满足发布条件，失败样本不删改。只读 CAS 文件校验缓存修复后，
历史 sigmoid 全量独立回放用时 82.12 秒并通过；仍不补造旧父流程终态或观察对照。
固定额外预热的单因素诊断已完成：原流程在一个周期复现 2.10% 漂移；
增加 25×400 次前置调用后六周期的控制均通过，但逐任务证据仍在主测量区间出现阶跃。
按预登记解释规则，固定预热不作为生产修复。首次诊断因周期校验错误中止，
旧源码、原始结果及 scratch profile 完整保留；修复仅传递实际 cycle，第二轮二进制字节不变。
同 workload 的 R100/R7300 对照已完成：exp case 1、10，各六个新进程周期，共 24 槽，
保留全部 2,693,328 个 Task；正确性通过，整轮耗时 1054.80 秒。四个条件本轮均通过
原控制阈值，不能覆盖此前 R100 的失败。case 1 的最大周期内漂移从 1.366% 降至
0.034%，case 10 从 0.919% 降至 0.202%；但跨周期 formal 均值 CV 没有降低，
长窗口的均值分别高约 1.289% 和 0.213%。长窗口改变了持续提交负载，不能仅解释为
精度提高，也没有确认唯一根因。case 10 长窗口的 Event 为 126.420–253.836 ms，
其中完整 Task 总时长仅为 44.777–46.532 ms，再次说明 Event 区间不能直接当作
完整 kernel Task Duration。24 槽的独立原始回放已通过，用时 88.07 秒；
其来源链和冻结 producer 已单独归档，结果始终不可发布。
下一步准备 baseline-only Task pilot 一次冻结窗口的可回放实现，并先核算原预算内的成本。
该实现和本次诊断都不构成发布准入；尚未启动新的全量生产确认。
新纯解析模块的 21 项定向检查已通过，旧两个纯解析文件保持原字节。
成本估算提示 50 ms 目标直接接入可能超过 3600 秒，不能据诊断通过直接启动封存。
常驻 oracle 的成功请求改为批量登记产物，21 项定向检查通过；固定旧→新各十请求
CPU 对照的结果完全一致，总耗时为 20.97/13.63 秒。该单次顺序对照仅支持此处
工具开销改善，不能外推正式预算已满足。
离线导出对照已完成：reports-off 的四槽试验保留相同的 220,222 行 Task CSV，
97 个 raw/metadata 文件字节不变，默认输出约 499 MB、关闭 timeline 后约 284 MB。
默认两槽总耗时约 32–33 秒，reports-off 约 29 秒。其先前一轮因严格日志校验停止：
CANN 正常以 a+ 追加 collection 日志，97 个原始文件与 CSV 未变；失败和未运行槽保留。
修正仅允许两个指定 collection 日志保留原字节前缀后追加，不放行 raw 改写。
随后固定的 reports-off/summary/summary/reports-off 对照同样全部通过原始文件与
完整 CSV 字节核验，耗时 106.63 秒。官方 `msprof.py export summary -dir ... --format csv`
两次导出为 13.16/13.26 秒，reports-off 为 19.34/18.32 秒；完整槽耗时分别为
23.46/23.76 和 29.10/28.56 秒。summary 仍保留全部汇总 CSV、数据库和原始文件。
新 Task-window 草案据此选用 summary 为唯一导出入口；原数据和旧协议不修改。
新资格入口保留机械插桩源码和原 input/oracle，按一次 Task pilot 冻结每 case 的 R，
其后六个独立周期使用同一 R。独立回放成本纳入资格槽预算。该协议仍需冻结候选、
在真实硬件上完成采集和独立回放，尚不能认定 3600 秒预算已满足。
上述历史回放与诊断均不能替代全量确认，也不能追认旧轮。
新草稿增加成功 session 的临时副本回收：校准/控制检查通过并写入 checkpoint 后，
完整核验 local、persistent 和 CAS transfer 清单，再释放 local/profile；失败路径保留。
五项 CPU 检查通过，包括七个 session 回收后完整 CAS 回放。正式容量与时间预算尚待实测；
已有 sigmoid Task 时长的规划估算提示，50 ms 窗口仍可能超过 3600 秒，暂不启动全量确认。
Task-window 历史桥的完整递归回放已通过，用时 822.40 秒；包括旧硬件拒绝、取消、
窗口诊断、四类离线导出尝试与 CPU oracle 成本证据。回执明确保持 accepted=false、
eligible_for_publication=false，不能替代新确认。证据在外部目录
`validation-graph-base-0.5.1-20261014/task-window-method-history-full-replay-v1/`。
随后固定的两组四槽存储对照完成：同一份 123 文件、283.8 MB 的完整证据，
CAS 写入与索引串行耗时 15.85/17.68 秒，四线程预持久化后完整索引为 6.85/6.99 秒；
完整目录复制串行为 8.59/11.18 秒，四线程为 5.67/4.26 秒。完整字节与索引均通过。
新草稿只在采集结束后的文件写入阶段使用四线程，保留完整 hash、fsync 与原子发布；
14 项 CPU 检查通过。该小型顺序成本对照不证明整轮 3600 秒预算已满足。
仓库默认入口继续指向 0.5.0。

## 范围

本候选从已封存的 0.5.0 完整文件清单复制，面向测量方法修复。
runtime 更新为 0.2.2，新增原始测量证据准入和历史 0.2.1 只读重放。
全部 schemas、v0001/v0002 图及阈值合同保持原始字节；gate 算术保持不变，
仅在入口增加原始测量证据回放。
本版不导入 1.0.0 的 Wiki、Teacher 提炼知识或新优化规则。

0.5.0 基线指纹保存在工作区外部证据目录
`validation-graph-base-0.5.1-20261014/release-preflight/0.5.0-baseline.json`，
包含原发布 manifest、200 个 payload 文件、45 个受保护文件及当前默认入口的哈希。
这是发布前状态记录，不是硬件验收回执。

## 封存前必须完成

1. 修复后的计时工具、所需 header 和回放依赖随包独立可用；复制到无研发目录的安装位置验证。
2. 冻结最终候选 payload、采集工具与预注册协议后，完成独立硬件控制实验；保存完整原始样本、时间线与所有失败尝试。
3. 独立 verifier 重算测量准入结论并核对来源绑定；报告必须明确返回 `accepted: true`。
4. 核对 0.5.0 原字节、0.5.1 runtime 指纹、冻结 schema/graph、registry、插件版本和包内链接；不得更改既有机器门槛。
5. 用 `release_skill_lib.py seal --measurement-validation <report>` 封存 0.5.1。
   `--validation-run` 仍仅用于 1.0.0 的 Teacher 与 45 次等预算比较，不能替代本版方法验收。
6. 封存与独立安装检查通过后，才更新 catalog、两个仓库 marketplace 和 README 的默认版本入口。

安装器拒绝覆盖其他版本的宿主链接；如需切换宿主，先核对并移除原先受管理的链接。
历史 campaign 保留原 `skill-lib.json` 绑定，不重新绑定为 0.5.1。

## 当前验证状态

### 定位实验

2026-10-14 在 910C/A3、CANN 9.0.0 上完成固定的 72 组实验：
exp case 9 与 sigmoid case 4，各六次新进程/分配周期，覆盖共享缓冲区、
同进程两套设备缓冲区角色交换、第二进程驻留，以及逐对落盘/周期结束后落盘两个因素。
全部执行及原正确性 oracle 通过；总计约 2013 秒。
矩阵包含 840 对、1680 个计时样本、96 个新进程及 120 次独立输出校验。

| 共享同一缓冲区的条件 | exp 总体角色偏差 | sigmoid 总体角色偏差 |
| --- | ---: | ---: |
| 逐对落盘 | 0.015892% | 0.004245% |
| 周期结束后落盘 | 0.001117% | 0.032328% |

上述四组的总体及全部六个周期都通过原 2% 角色偏差与 5% CV 控制。
exp 的双进程方案在移走落盘后仍有六个周期全部失败；汇总偏差仅 0.675576%，
但 CV 达 7.478485%，说明不同周期的相反偏差可以在汇总中抵消。
sigmoid 对应双进程方案的总体偏差为 0.433301%，但仍有五个周期失败。
两套缓冲区交叉交换结果支持分配相关偏差；尚不能认定 L2、HBM 或某个 context
资源是唯一原因。定位矩阵包含故意保留的失败对照，不能把整体标为全部通过。

两条独立任务时间线均恢复精确的 510 个 kernel task（10 次预热、400 次 prime、
100 次测量），并通过独立输出 oracle。exp 的 100-call event 区间为 19.299700 ms，
首末 kernel 跨度 19.297024 ms，kernel 总时长 19.223168 ms；sigmoid 分别为
33.418060、33.415936、33.413684 ms。这些是单次独立 profile 的区间核对，
不作为未插桩性能估计。

原 profile 尝试缺失任务数据，失败已保留。预登记的设施修正仅将 application
改为直接执行原生程序，并复用已有 `task_time_l1_pipe_utilization` 配置；
两条各执行一次，未重采 72 组控制，也未对单个 flag 作因果归因。
预登记见 `scaffolding/curation/graph-base-0.5.1-measurement-diagnosis-anchor.json`
和同目录的 `graph-base-0.5.1-measurement-diagnosis-profile-amendment.json`；
原始证据在工作区 `timing-method-diagnostics-20261014/`。

### 独立生产协议确认

最终采集器已按两算子各 20 case、每 case 六个周期及四条独立时间线的
固定计划启动确认，并在下面的必需控制失败处停止。定位样本未复用为确认样本。

第一次固定确认在 CLI 解析配置时失败：历史特殊值 case 的 `value_range`
含非标准 JSON 的 `-Infinity`、`Infinity` 和 `NaN`，runtime 严格解析器正确拒绝。
两个算子均未启动原生进程、未采集 NPU 样本，四个后续 timeline 均记录为
`not_run`。完整六个终态及冻结 producer 原字节保存在
`validation-graph-base-0.5.1-20261014/production-confirmation/`。
后续仅修正 workload 描述的非有限数字表示，并保留此轮为发布前置失败证据；
不改变原 metadata、输入、oracle、计时协议或阈值。

JSON 修正轮的 exp 在 case 6、cycle 4 触发真实控制失败，按计划停止。
后置 A/A 的 baseline 五条 100-call event 区间为
`[0.611680, 0.610240, 1.340720, 0.611660, 0.611780] ms`；
CV 为 43.077%，角色偏差为 14.566%，前后 baseline 均值漂移为 23.991%。
异常 event 的 native 区间为 1.416521 ms，首末 CPU 都为 7；
增加的停顿发生在 event 覆盖区间内，不能由样本外落盘或 IPC 解释，
也不能据此确定是主机提交中断、设备执行还是 event 边界问题。
该样本保留，没有删点或重采。exp 两条后续 timeline 为 `not_run`。

sigmoid 随后在 case 7、cycle 4 的前置 A/A 同样触发控制失败：
baseline 的第二条 100-call event 为 1.282000 ms，其余约 0.697 ms；
CV 为 32.104%，角色偏差为 11.551%，前后漂移为 14.391%。
对应 native 区间 1.322701 ms，首末 CPU 都为 162，与 exp 的 CPU 不同。
sigmoid 两条后续 timeline 同样为 `not_run`。本轮共保存 exp 35 个、
sigmoid 41 个完整周期；六个执行槽全部有终态，但确认均未准入。
调度器成功写完终态不等于测量通过，本轮不满足封存条件。

此前失败的 sigmoid case 4 已完成新协议的六个周期且全部通过：
最大角色偏差 0.1114%、最大 CV 0.1310%、最大前后漂移 0.0918%。
这支持共享缓冲区修复该 case 的持续角色偏差；新增的孤立长 event
仍需独立定位，不能从样本中删除。

### 提交停顿诊断

另行预登记 exp case 6 的六个新进程周期，每周期 500 对，共 6000 条 event；
全部保留，并执行一份独立的五对任务时间线。使用相同 baseline kernel、输入、
oracle、共享缓冲区及 repeat=100；诊断 header 仅增加提交与同步边界的
单调时钟、线程 CPU 时间、上下文切换和页错计数，不在单次 launch 内插桩。
这不是正式确认的重采，也不产生发布准入。执行约 162 秒，14 次输出 oracle 通过。

预登记的描述性长尾标准（超过本周期 event 中位数 10%）识别到三条样本。
其中两条大长尾为 1.181660 ms 和 1.195220 ms，分别约为中位数的 1.92 和 1.88 倍；
对应 100 次提交的 wall time 为 219.222 和 215.531 μs，线程 CPU 时间为
219.660 和 215.920 μs。提交期间的自愿/非自愿切换、minor/major fault 均为零，
start/end event record 也没有相应长停顿。额外等待出现在同步阶段，
不能把其中七次自愿切换当成主机提交被抢占的证据。该结果不支持直接采用
CPU 隔离或实时调度作为已经验证的修复。

独立 profile 核对到精确的 1422 个 kernel task，但十条 event 未复现上述大长尾。
各 100-task 组的 kernel 总时长为 650.188–653.224 μs，首末跨度为
670.092–737.016 μs，最大任务间隙为 6.320–17.576 μs。
正常 profile 不能解释未插桩长尾的具体位置；需要进一步设备时间线证据。
预登记在 `scaffolding/curation/graph-base-0.5.1-submission-diagnostic-anchor.json`，
完整原始数据在工作区 `submission-timing-diagnostics-20261014/`。

### 长任务时间线诊断

在新的预登记下，沿用上述原生二进制和 header，以相同 profiler 配置执行
六个新进程周期、每周期 500 对。全部 6000 条 event、602532 个完整 kernel task
及 12 次输出 oracle 保留，执行约 1091 秒。此诊断通过命令文件驱动，
与交互采样存在样本间空闲时间差异；profile 插桩本身也改变提交和执行条件。

按同一描述性标准共识别 97 条长尾。最长 event 为 1470.920 μs，
kernel 总时长 667.336 μs，首末跨度 1441.388 μs，最大任务间隙 379.928 μs。
同对另一角色 event 为 1298.740 μs，kernel 总时长 667.192 μs，
首末跨度 1296.788 μs，最大间隙 588.212 μs。这些具体的 profile 样本中，
增加的时间主要表现为任务间隙，不能解释为 kernel 总执行时间翻倍。

但 profile 的 event 中位数为 777.470 μs，未插桩诊断为 622.140 μs；
提交 wall time 中位数分别为 768.027 μs 和 225.492 μs。
profile 大长尾同时伴随较长提交，未插桩的两条大长尾却没有该特征。
因此不能把两组相似幅度的长尾认定为同一根因，也不能用 kernel 时长总和
替换原 ACL event 指标、删慢样本，或重新跑确认直到偶然通过。

预登记在 `scaffolding/curation/graph-base-0.5.1-long-task-timeline-anchor.json`，
完整证据在工作区 `submission-long-timeline-diagnostics-20261014/`。
尚缺能在未插桩长 event 同次执行中关联设备任务派发、运行时后台线程与等待的证据；
目前没有足以支持透明计时修正的新结论，全部诊断均不授予发布准入。

### 发布保留检查

诊断结束后重新核对：0.5.0 的 200 个 payload 文件、原默认入口均保持字节不变；
0.5.1 的 34 个 schema、图源文件、图快照和机器合同与原版一致。
0.5.1 未生成稳定版 `release.json`。检查记录在工作区
`validation-graph-base-0.5.1-20261014/release-preflight/post-diagnostic-hold.json`。

软件测试中的合成或桩回执只证明拒绝路径和发布工具行为，不构成方法有效性或性能收益证明。

## 固定预测窗口研究与 v2 准入准备

`event-duration-study-20261014` 使用预登记的 50 ms 预测目标。每 case 一个独立
pilot 进程采三次 baseline-only event（每次 repeat=100），按中位数一次确定 R，
随后六个全新进程/分配周期确认，未调节 R、删样本或追加重采。

| case | R | 汇总最大 CV | 汇总最大角色偏差 | 汇总最大前后漂移 |
| --- | ---: | ---: | ---: | ---: |
| exp 6 | 7900 | 0.75477% | 0.01218% | 0.00938% |
| exp 9 | 300 | 0.18612% | 0.01086% | 0.00579% |
| sigmoid 7 | 7000 | 1.02285% | 0.01079% | 0.01139% |
| sigmoid 4 | 200 | 1.26503% | 0.01302% | 0.02328% |

24 个确认周期、720 个事件、48 次输出 oracle 全部通过；各周期独立控制也通过。
确认外层耗时 550.073 秒，其中原生进程区间 107.590 秒，oracle 433.945 秒。
部分实测窗口低于 50 ms，按预登记保留：50 ms 是预测目标，非新增硬门槛。
该指标是连续批次的完整算子均摊时间，不是单次孤立调用延迟。

首次启动因 root anchor 使用裸 hash 而非 `sha256:` 前缀，在 native 启动前失败。
旧执行/anchor 保留；修复只改变 anchor 格式及新 job 输出路径，原计划、二进制和输入不变。
完整结果、真实 bounded jobs、修复记录及历史拒绝均由
`scaffolding/curation/graph-base-0.5.1-duration-v2-transition.json` 绑定。
旧 producer 字节已归档，仅用于历史只读回放；新采集仍严格绑定当前 producer。

v2 还将 pilot 预热固定为 20 次 baseline，并用每次 collection 独立的持久 Python
oracle 进程复用 imports。原校验数学、每个输出的校验、失败即停、原机器门槛均保留。
这些生产变化仍须随完整 40 case 与四条独立时间线共同验收；四 case 研究不是发布回执。

### v2 完整生产确认结果

固定六项确认在 `production-confirmation-duration-v2/` 完成，总耗时 3232.983 秒。
exp 的 20 个 pilot 和 57 个确认周期保存了 1770 条 event、154 次原 oracle 校验；
sigmoid 的 20 个 pilot 和 120 个确认周期保存了 3660 条 event、280 次校验。
全部输出校验通过，但这不能代替计时控制。

| 固定执行项 | 结果 |
| --- | --- |
| exp 全量确认 | case 10、cycle 2 控制失败，按计划停止 |
| exp case 1 / 9 时间线 | `not_run` |
| sigmoid 全量确认 | 20 case × 6 周期全部通过 |
| sigmoid case 1 / 4 时间线 | 完整任务覆盖与两侧原 oracle 均通过 |

exp case 10 为 FP16 `[2049, 513]`，baseline pilot 固定 R=7300。
其前两个周期 event 约 248–250 ms，第三个周期的全部 30 条样本分为
13 条约 150.45–150.95 ms 和 17 条约 249.72–251.13 ms。
两档同时出现在两个角色、各阶段及两种执行顺序，不能归为持续角色偏差。
前置 A/A 最大 CV 为 28.56%、角色偏差为 18.34%；后置 A/A 同样失败。
这些原始样本完整保留，未追加采样、删除异常点或调整 R。

连续 7300 次调用的实测区间明显偏离 100 次 pilot 的线性预测。
现有证据尚不能区分提交阻塞、设备任务间隙或运行时等待；
第一次 sample 已出现较长区间，因此 Event 复用也不能单独解释全部现象。
随后独立诊断对同一 case、相同 R 和完整调用顺序增加主机阶段时钟及
每 100 次提交的检查点，固定一个周期；诊断结果不授予发布准入。

原始终态及回执索引见工作区
`validation-graph-base-0.5.1-20261014/production-confirmation-duration-v2/campaign-outcome-summary.json`。
外层 job 的 exit 0 只表示六项终态已完整落盘，不表示整轮确认通过。

### 主性能指标复核：Task Duration 与 Event 的范围

已核对本地 `cannbot-skills` 的 `c60a48af8f0ff2374e1491a313d9f26b02620d1e`：
`ops-profiling/SKILL.md` 推荐用 `--compare` 做 kernel 性能验收，比较字段是
`msprof.op_summary.Task_Duration`；`msprof-op-guide.md` 将 Task Duration 的下降
列为优化回归的首项。该口径符合本轮 exp tile、sigmoid 流水的单 kernel 优化目标。
但该仓库的 compare parser 只选第一份 CSV 的最大 AI 任务，不能照搬为完整任务验收；
其 repeats 参数也没有落实为独立重复采集循环。

当前长批次 Event 是设备上两个事件间的经过时间，包含任务间隙；除以 7300 后，
得到的是批次均摊完成时间，不能把它等同于单 kernel 的任务耗时。
主机提交造成设备空闲时，Event 会记录这段空闲，并非直接累计 CPU 执行时间。
Task Duration 则包含设备任务的调度、执行和结束响应，也不是纯 Vector 指令忙碌时间。
参见 [Event 接口](https://www.hiascend.com/doc_center/source/en/CANNCommunityEdition/900/API/runtimeapi/aclcppdevg_03_0090.html)
与 [CANN 9.0 任务字段](https://www.hiascend.com/doc_center/source/zh/canncommercial/900/devaids/Profiling/atlasprofiling_16_0067.html)。

`long-enqueue-diagnostic-20261014/` 的唯一诊断保留全部 30 条 event：
均为 248.303–249.855 ms，未复现 150 ms 分支。每条 event 在第 5200–5700 次
提交附近都有约 100 ms 的检查点间隔，线程 CPU 时间也约 100 ms；
Event record 只有微秒级，cgroup 限流计数没有新增。
这定位了提交阶段的一处干扰，尚未证明具体 SDK 或队列机制。
曾讨论的“多短窗口汇总 Event”方案在实现前停止，没有生成新计时样本。

后续新协议采用以下明确范围，独立采集通过后才能发布：

- 主指标：按预登记调用范围完整匹配的 Task Duration；当前单 kernel 每个样本
  固定 100 次完整调用，全部任务耗时算术平均。每 case 六个新进程周期、
  每阶段五对，正式统计仍为 30 对，不能把 3000 个 task 当作 3000 个独立样本。
- 辅助指标：Event 区间、首末任务跨度、任务间隙和 Host wall；报告持续吞吐或
  端到端回退，不把 kernel 加速表述成端到端加速。
- 基础计时关闭 PMU，预登记 `--task-time=l1 --ai-core=off`；流水、访存等机制
  另行采集。文档支持该配置不等于已证零扰动，须做独立控制和采集完整性验证。
- 原 CV、A/A 偏差、漂移、收益下界、逐 case 回退和正确性要求保持数值不变。
  这是指标范围的显式变更，旧 Event 样本不能改标签后用于新口径准入。
- 多 kernel 必须登记每次完整调用的全部任务；有重叠时另外报告完成跨度，
  不能把任务时长之和称为完整算子延迟。缺失或歧义任务禁止准入。

### 关闭 PMU 的同次任务诊断结果

`task-duration-diagnostic-20261014/` 对 exp case 10 的原失败二进制完成唯一一次
Task-only 时间线诊断，保持 R=7300。完整 220222 个任务、30 条 Event 和两侧
原正确性 oracle 均通过独立回放；总墙钟 269.533 秒，其中采集及自动导出 245.462 秒。

| 同一次采集中的指标 | 结果 |
| --- | ---: |
| 7300-task 平均 Task Duration | 6.274787–6.278972 μs |
| 上述 30 个聚合均值的 CV | 0.01697% |
| 7300-task 时长之和中位数 | 45.824752 ms |
| Event 区间 | 150.132767–250.631317 ms |
| 任务间隙总和 | 104.312224–204.813672 ms |

这次 profile 确实同时出现约 150/250 ms 两档：十条 Event 各含一个约 100 ms
任务间隙，另二十条各含两个，而 kernel 总时长保持约 45.825 ms。
这些同次证据支持把本次 Event 差异定位到任务之间的等待，不能解释为 kernel
执行时间相应变慢。全部任务和长间隙保留；没有剔除异常点或追加采集。

它仍只有一个独立 profile 生命周期，不能替代固定 repeat=100 的全量资格验证，
也不能单独证明旧未插桩记录中全部差异的具体运行时根因。
旧 Event 失败继续保持失败，新 Task 协议须重新采集两侧数据。
完整分析为工作区同目录的 `analysis-report.json`，SHA256
`39e1aa739cf1a0239f78b2e881dd55280d8f1c7630fd66ef1835f0912ff1ac8c`。
预登记见 `scaffolding/curation/graph-base-0.5.1-task-duration-diagnostic-anchor.json`；
接口及待验收范围见 `scaffolding/curation/graph-base-0.5.1-task-protocol-design.md`。

### 首次 Task 生产确认：成本预估中止

`production-task-confirmation-v1/` 按固定 repeat=100、两算子各 20 case、
每 case 六个独立进程周期启动；主计时关闭 PMU，每周期完整匹配 4222 个任务。
候选 208 个文件已冻结，独立副本的实际 pip 安装、runtime 0.2.2 及 registry
检查通过。执行前修复了外层超时无法清理独立 session 后代的问题，六项真实进程
测试覆盖超时、SIGTERM、双重 fork、忽略 TERM 和正常回执兼容。

原定单算子预算为 3600 秒。exp 已完成的周期耗时约 58–69 秒，
其中 profiler 约 26–29 秒。第一个周期的原生测量序列仅约 0.275 秒，
日志显示大量墙钟时间发生在工具初始化、收尾、解析导出以及后续证据处理。
处理各阶段的具体占比需要另行离线计时，不能直接归因于某个存储操作。

据此预估 120 个周期约需两小时，root 在实际墙钟 985.100 秒时主动中止整轮，
先解决工具成本。**这不是实际预算超限，也不是统计控制失败。**

- exp case 1、2 各六个周期及 case 3 的前两个周期，共 14 个完整周期，
  采集时的控制检查均通过；这不代表完整算子准入。
- 第 15 个周期（case 3、cycle 2）的实际目录和部分证据保留；sigmoid 未启动。
- 外层及 exp 执行回执均记录实际退出码 143。所有记录的后代进程已退出，
  设备重新检查为空闲。
- 原本未生成的 campaign 总结及 slot 终态仍保持缺失，不补造完成结果。
- 原计划、原始数据、失败历史及冻结源码不变；本版本的实验不续跑、不重采。

取消请求为该目录的 `root-cost-projection-cancellation.json`，SHA256
`4ae046beab87420e0bafa9c73fe61b46ba94811544141bbc6adaa41f08dd2dc9`；
清理回执为 `post-cancellation-cleanup.json`，SHA256
`dcc8d289e1c375a22160618aa6bccef9b72475dc6dc869a7ca9aa6788cef6ca5`。
修改前源码归档为同级 `measurement-task-v1-source-archive-20261014/index.json`，
SHA256 `dac4a22c3624f1942c50b72917206f583c9bc2d2158c810f1f65ac5cacb389b0`。
这些部分结果均不可用于发布；下一轮须先明确降低成本的实现，再独立预登记完整确认。

### 证据入库成本修复

在同一份 exp case 1、cycle 0 的既有 profile 上，以独立 SQLite/CAS 做离线对照：
78 个文件共 9,817,788 字节。首次全文件入库由 22.712 秒降至 7.042 秒；
无 export 时第二次重复入库由 4.782 秒改为复用已保存的快照。整个离线 probe
由 32.768 秒降至 11.991 秒。原 profile manifest 和 4222-task partition 的哈希
均与旧记录一致，CSV 在解析前后也经过哈希检查。

实现保留每个不可变对象的持久化和内容校验，仅合并索引事务；发生错误时回滚
索引。批量入库、损坏对象和回滚的八项定向测试通过。旧单文件 API 测试通过；
另一个旧 episode 测试在进入 store 检查前因缺少现有 gate 要求的 CAS reader 失败，
没有将其记为通过。

修复后的 probe 结果位于工作区
`validation-graph-base-0.5.1-20261014/measurement-task-v1-cost-probe-fixed-20261014/result.json`，
SHA256 `6800d756ed05c36f5db69a5f0af08f4b87e04292616dae01fa5781f4f8fb5c7e`。
这次检查没有执行 NPU，不能据此宣称完整硬件确认已满足 3600 秒预算。

### 原生 Task Profiling API 设施检查

在执行前固定 exp case 1、sigmoid case 4 各一个独立进程周期。适配器在原
RunShared 前后调用 `aclprofStart/Stop`，只启用 `ACL_PROF_TASK_TIME`；
原 kernel、共享计时循环和 oracle 的字节保持一致。显式结束采集后，再调用一次
`msprof --export=on --type=text`。原生 API 失败、任务缺失、正确性或控制失败
均停止本轮，没有重试。

两槽均通过，随后独立只读回放通过：每槽 4222 个完整任务、30 个 Event 辅助
读数、两侧输出验证。外层总墙钟 90.276 秒。

| 项目 | exp case 1 | sigmoid case 4 |
| --- | ---: | ---: |
| 原生采集 | 8.412 秒 | 9.235 秒 |
| 导出 | 17.434 秒 | 15.449 秒 |
| 两侧冷启动 CLI oracle | 11.406 / 7.514 秒 | 8.967 / 9.016 秒 |
| 最大 phase CV | 1.492% | 0.0395% |
| 最大角色偏差 | 0.535% | 0.0362% |
| 最大前后漂移 | 1.439% | 0.0437% |

冷启动 CLI 成本不能作为持久 oracle worker 的周期成本。该检查只支持这两次
API 生命周期的完整性与局部控制；全量 20 case × 六周期的预算和方法准入仍未
验证。特别是每周期导出仍占 15–17 秒，不能仅凭 API 入口替换宣称成本已解决。

证据为工作区
`validation-graph-base-0.5.1-20261014/native-task-api-facility-probe-20261014/facility-summary.json`，
SHA256 `db04c67293ad3220c561b52e5cf0108d1b7c77886f9c5effec0352fced1f288d`；
只读回放为同目录 `independent-replay.json`，SHA256
`ca26fd194e840515229b13e5b091aedd56f9962dfe7e2c25cfad1ce447b81957`。

### 导出成本定位与本地工作目录

先在已有 exp case 1 的六份原始 PROF 副本上执行一次批量导出，耗时 101.512 秒，
约 16.919 秒/份。六份完整 Task 分组均与原记录相同，但没有明显摊销收益，故不
采用按 case 批量导出的方案。

随后对同一份原始 PROF 预登记两槽导出：JuiceFS → 本地 `/tmp` overlay，每槽
各一次，失败即停。JuiceFS 耗时 18.408 秒，本地耗时 2.297 秒；两份导出 CSV
SHA256 均为 `6a2f44df4af87c3023ad37b049447963e3f7e3469ee5cb8249e95313a1c0f577`，
4222 条 Task 的完整分组与原记录一致。本地结果的 81 个文件共 9,788,853 字节，
用 3.893 秒复制回持久目录，两端完整哈希清单一致。

这支持将该次离线 export 的主要成本定位到存储条件；尚不能外推完整 NPU 采集
和全部 case 的预算。正式 v2 采用原 msprof CLI、原 host/binary 与逐周期检查，
仅将 profiling 工作目录迁至预登记本地路径，完整证据校验后保存在持久存储。
原生 API 设施检查继续留在历史中，不作为生产入口。

批量实验结果为工作区
`validation-graph-base-0.5.1-20261014/measurement-task-batch-export-cost-20261014/result.json`，
SHA256 `be96278ddc1599cb29d9f589a063621d94debe26dfb160e23c92809c3985d1d5`。
存储对照为同级 `measurement-task-local-export-cost-20261014/result.json`，
SHA256 `bbdfdccc12c5046b6a5690dd5ffd105f8c25863a982b5f85f300e28332081a7b`。
两项均没有运行 NPU，也不提供发布准入。
