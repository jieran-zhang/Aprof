# soft_targets_local_v1（graph-base/1.2.0，未封版）

## 执行与证据是两个判据

C0=600、总任务=3120、recorder=600、finalize=600 秒及 build=180、完整正确性=300、单 case=60 秒均是软目标。1200 秒采集/R1 预留和 180 秒 recorder 收尾预留只提示预计超支。所有阶段继续到目标完成、真实不可继续原因、既定候选/重试次数耗尽或用户取消。不得将目标换成巨大 timeout。execution status、budget warnings、correctness status、performance verdict 分列。

使用 task_budget_v2/launch_v2/terminal_v2；旧 v1 仅按历史规则回放。单调时钟从接收 seed 到终态连续计算，等待和续跑间隙均计入。外部宿主期限若不可控制，记录具体限制和恢复点；不当作 numerical_mismatch。

超出目标触发 checkpoint 和 /proc 的进程、CPU、I/O 诊断，不凭 stdout 静默杀进程。只有明确诊断证据确认局部挂起，才终止对应进程组；其余独立步骤与报告继续。取消会清理本任务进程组。

A/B 间隔、测量有效期、完整 Task 数、20 cases、5 预热/20 正式、真实逐轮清 L2 和 bounded_outlier_v1 均不放宽。过期保留数据并判 inconclusive；按预声明最多一次复验，不挑有利结果。

## 正确性身份

默认原始 baseline 是用户前提下 assumed，未在本任务验证。C0 仅冻结源码/输入、必要构建、工具链/设备/容量、入口/输出接口和 oracle 契约；不执行完整正确性或隐藏数值预检。用户明确要求才执行 baseline 的一次完整检查。declaration v2 的 baseline_trust 绑定 source/binary；修改计算语义后是新候选，不继承假定。最终 comparison 的 baseline_correctness=null，结果注明 assumed。

每个新候选先实际验证全部声明 case。后续对实际输出全部重新哈希，绑定源码、binary、case、input、workload、oracle 依赖/规则/环境和全输出映射。相同内容使用任务 validation-cache 的真实执行引用；不同输出重新交给原 oracle，不能仅因不同就判错。多输出/原位/TensorList 的完整覆盖继续校验。缓存由实际通过的 oracle 写入并用任务私有密钥认证；任意 passed JSON 不授予通过。信任边界是任务所有者和已冻结 runtime，不防范能读取密钥并替换 runtime 的恶意同用户进程。

正常采集、报告、finalize、recorder 共享任务根中的 cache；独立审计明确设置 APROF_ORACLE_AUDIT=1，一次执行且单列成本。旧证据没有可信缓存时真实重放，不能由旧 passed 标签补造缓存。

## 本地运行与采集

workspace-create 生成唯一 /dev/shm/aprof-<task-id>/。源码副本、输入、构建、TMPDIR、缓存、输出、profile/SQLite/CSV、日志、checkpoint、报告和 memory 均在任务根。系统 CANN/驱动从安装位置读。准备时检查可用 bytes/inode/内存；不足具体报缺项，不回退共享盘。不得自动复制/归档回 JuiceFS。仅交付框架源码可按仓库约定保存。

先源码诊断；若确需早期采样，只采预声明代表集。两侧构建、输入、候选完整正确性和容量齐备后调用 single_role_task.collect_pair：顺序完成 A/B native，再集中顺序导出。pending.json 允许在原目录仍存在时 finish_case 恢复后处理，保留原始采样顺序与全部 trace。已完成 capture 必须回放验证后才能复用。

device_probe_session=True 使用维护的 device_probe_session.py：一个 ACL 会话、case 前后轻量动态查询；native 仍核对 context/device。Vector 频率不可用记 unknown，不宣称频率稳定。设备窗口不并发重型导出。

## 成本和恢复

operations.jsonl 使用单调起止，workflow_stage 与 operation_type 分开，含 case、implementation、pid、parent_operation、目标/超支、执行结果。阶段父耗时不能与子操作再次相加。记录 oracle hit/miss/真实执行次数；模型等待/生成无法取得时 unknown，未归属时间不称模型时间。

/dev/shm 为易失存储；只有目录、原始身份、缓存密钥仍存在时可以恢复。目录丢失明确 missing，不能声称跨重启持久。保留被报告引用的原始测量数据，不自动 cleanup。

## 兼容边界

历史 Task-window/paired/shared 协议及 v1 预算回放保留原始硬截止判据，只解释旧证据；新任务不得调用其执行脚本，统一走本页列出的 single_role/task_budget_v2 入口。新流程不借助旧脚手架的 controller/process_guard。取消/真实错误后的清理等待不是耗时预算。系统 CANN/驱动和可选 simulator 的内部 watchdog/期限不受此 runtime 控制；若它们结束任务，保留实际退出、日志和 pending 恢复点，不称为数值失败。
