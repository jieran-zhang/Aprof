# 0.5.1 原始确认耗时与持久 oracle 设计

本报告只分析已失败的 `production-confirmation-json-fix`。全部 76 个已执行周期均纳入；不改变历史结论，不构成新方法准入。原始时间戳、逐周期拆分、已核实的来源哈希及计算口径见同目录 `graph-base-0.5.1-oracle-cost-audit.json`。当前硬件 quiet window 中仅做小型 JSON 读取和报告写入，没有运行 torch、测试、构建或 NPU。

## 可直接证明的成本

exp 执行 35 周期，sigmoid 执行 41 周期，分别在首个控制失败后停止。外层执行回执记录总耗时 **2010.45 秒（33.51 分钟）**。

| 不重叠阶段 | 秒 | 占外层总耗时 |
| --- | ---: | ---: |
| native 执行回执区间 | 248.95 | 12.4% |
| 152 次 baseline/candidate oracle CLI | 1305.56 | 64.9% |
| 周期内其余区间 | 329.70 | 16.4% |
| 周期间、raw 区间内 | 12.38 | 0.6% |
| 外层执行减两个 raw 区间 | 113.87 | 5.7% |

每周期平均 24.792 秒，其中两次 oracle 平均合计 17.178 秒；每次 oracle 平均 **8.589 秒**。现有 collector 在每周期结束后，分别通过 `subprocess.Popen()` 启动两个 Python 验证进程。exp/sigmoid 脚本都会导入 NumPy 与 PyTorch。

这里的 oracle 成本包含进程启动、导入、数学计算、输入输出及退出。**没有导入专用计时，不能把 1305.56 秒都归因于 torch 导入。** native 回执也包含进程启动及 close/log 收尾，不是纯设备时间。其余区间包含输出 CAS 登记、身份检查等操作，但旧回执没有这些操作各自的时间戳，不能进一步准确归因。周期阶段来自记录的 wall-clock 时间戳，外层来自执行器的 duration 字段；本报告没有把它们称为 CPU 时间。

## 对单任务 60 分钟的含义

20 case × 6 周期需要 120 周期、240 次 oracle 请求。直接用这 76 周期的均值外推，确认周期本身需要 **49.58 分钟**。50 ms 目标下，120 周期 × 3 phase × 5 pairs × 2 role 的名义 event 区间总计约 3 分钟；该数既不是实测总开销，也不是上界。

这些估计尚未包含模型 proposer/reviewer、pilot、构建、额外的前置全量正确性、profile、硬件探测和证据回放。现有 `validation_host_evaluator.py` 确实还单独执行前置全量正确性。因此，目前不能宣称该流程能在 60 分钟内完成。

这也不是全部 40 case 或五个 validation 算子的耗时预测：现有数据只覆盖 exp/sigmoid 的早期 case，且受首败停止影响。GQA、weight_quant_batch_matmul 的 CPU golden 数学可能明显更贵；dynamic_quant 则仅使用 NumPy。需要实际测量，不能直接转用 exp/sigmoid 的启动节省比例。

一个有用的预算换算：240 次请求中，每次真正节省 1 秒，整任务节省 4 分钟。例如 warm 请求若实测为 4 秒，按当前均值的预算情景可节省约 18.36 分钟；**4 秒尚未实测**。即使 oracle 成本为零，当前其余周期成本的线性外推仍约 15.23 分钟。

## 收敛后的最小实现

v2 固定使用一个受信任的 Python oracle worker，每个 collect/trial 启动一个，生命周期及启动成本计入相同 60 分钟预算，不跨 trial 复用。v1 只保留历史证据回放，不增加用户可选执行模式或 shell fallback。

worker 逐次调用冻结的原始脚本：`runpy.run_path(script, run_name="__main__")`。每次使用新的脚本 globals，保留原始 CLI 参数、数学、阈值及输入读取。NumPy/PyTorch 模块缓存可复用；不缓存 golden、输出或通过判定。两个 role 在每个周期都重新验证，baseline 完成后才验证 candidate，两者均完成后才启动下一 native 周期。pilot 的两个输出也独立验证。

GQA 和 weight_quant_batch_matmul 的 oracle 在模块顶层执行，没有 `main()`；因此不能统一实现为“导入一次、反复调用 main”。runpy 能保留这类原始入口。

### 真实脚本的状态边界

已读取 exp、sigmoid 和五个 validation oracle。它们的实际操作包括导入、argparse、局部/顶层数据、输入读取、CPU 张量数学、结果文件写入、打印及 `SystemExit`；未发现显式修改 torch/NumPy 全局配置、随机状态、信号或线程设置的代码。

最小恢复范围为 `sys.argv`、`sys.path`、cwd、环境和标准输出/错误。`sys.path[0]` 在请求期间对应脚本目录，匹配原 CLI 导入路径。脚本返回的 globals 和异常 traceback 不跨请求保留，避免持有大张量/memmap。第三方库的模块全局状态并不被 runpy 隔离，因此只允许冻结并审查过的脚本；不把它作为执行任意 Python 的沙箱。

原脚本的 `SystemExit(None/0)` 是成功、整数非零是失败，其他值按 CLI 失败记录；异常不能被转换为通过。直接退出、崩溃、IPC 断开或超时均终止当前 trial，不重启 worker、不重做该请求。超时由父进程控制并终止进程组，避免依赖正在执行 oracle 的 Python 线程自行中断。

使用独立 IPC 文件描述符传输协议；stdout/stderr 在 OS 文件描述符层面捕获，避免原脚本打印或第三方库警告破坏协议。实际 stderr 可能因库内的一次性警告状态而不同，应原样保存，不能伪造为独立 CLI 的日志。结果 JSON 和 stdout 中的判定必须按原规则一致。

worker 在 native 采样期间不执行新的验证请求。已加载库的常驻线程/内存仍可能影响采样；独立硬件资格验证必须使用真实 worker 生命周期，不能以“没有请求”证明完全没有干扰。

## 建议接口及证据合同

新增包内 `skills/ascendc-aprof-profiling/scripts/persistent_oracle.py`，只拥有 worker/client 和请求协议。启动前冻结完整 request plan，所有请求的脚本、argv、cwd、prepared refs、输出/结果/日志路径均由可信 controller 生成。IPC 请求只选择下一个 `request_index`；不接受任意命令或脚本。

建议 Python 接口：`PersistentOracle(plan, receipt_dir, *, deadline)`，`verify_next(request_index) -> receipt`，`close() -> worker_receipt`。parent deadline 使用 monotonic 时间，所有等待使用剩余预算。失败时也必须写出实际终态及已消耗成本。

`raw.verifier_worker_ref` 指向 CAS worker 回执，最小字段为：

```text
schema_version, protocol="persistent_python_oracle_v1",
run_id, session_id, worker_id, pid,
interpreter_ref, worker_source_ref, request_plan_ref,
started_at, ready_at, finished_at, exit_status, transcript_ref
```

request plan 每项包含 `case_id`、`stage`（calibration/confirmation）、`cycle`、`role`、argv/cwd、脚本 ref、prepared refs、output paths、result path 和 log path。顺序在执行前冻结；失败后只允许后续项未执行，不允许补跑、交换或跳过。

每个 `session.verifications[role]` 保留现有 argv/cwd、起止时间、exit_status、log_ref/log_hash、output_refs，增加 protocol、worker_id、request_index、request_ref、result_ref。request_ref 绑定真实请求/响应、PID、源码、输出/结果、stdout/stderr、状态恢复结果；parent transcript 保留超时和异常。各 receipt 不冒充独立 Python 子进程。

runtime 回放须检查：

- worker 身份、源码、解释器和 request plan 均与运行前冻结记录一致；整个 collect 只一个 worker。
- 原始 transcript 与请求回执一致，序号连续、无重复；每个已完成周期两个 role 的完整正确性均存在。
- 请求与原 oracle、metadata/input/output/result 的 CAS 引用相符；输出验证前后不可修改。
- 同一 PID 的请求串行，native 结束后验证，下一次 native 开始前验证完成；启动/退出均在 trial 预算内。
- 原 stdout 判定、结果 JSON、退出状态一致；错误、超时或缺少证据拒绝准入。

oracle transcript 证明本 worker 的请求顺序，不能单独证明不存在未登记 pilot。首次 pilot、失败停止和禁止重采样仍由外层 preregistration、独占 started 标记及完整 attempt roster 保证。

## 可独立分工的文件边界

| 责任 | 文件范围 |
| --- | --- |
| worker/client、CPU 协议与等价测试 | 新 `persistent_oracle.py` 及独立 tests；eval_runner |
| pilot/confirmation 调用、worker 生命周期、CAS 登记、producer 清单 | 0.5.1 `device_shared_timing.py` 和新 v2 qualifier；hardware_validation |
| v2 worker/request 回放、v1 历史分支 | 0.5.1 `runtime/src/aprof_runtime/measurement_admission.py`；training_repo |
| 完整资格、生产协议冻结、独立安装及发布 | 外层 qualifier/publication 检查与 root 集成；所有新 producer 字节在硬件前冻结 |
| 1.0.0 预算接入 | 稳定 0.5.1 后迁移 `validation_host_evaluator.py`；不得提前声称五算子已满足 60 分钟 |

## 后续必须验证的事项

CPU window 后，用已保存的真实输出及受控错误输出，对新 worker 和原 fresh CLI 比较原结果 JSON、正确性结论及失败语义；覆盖 dtype、NaN/Inf、尾部、错误大小和同进程重复请求。协议负测覆盖乱序、重复请求、变更脚本/输入、结果与 stdout 不一致、异常、SystemExit、崩溃和超时；验证无新 PID 偷换、失败无重试。

实测 cold startup 与逐请求 warm 成本，保留 CPU/RSS/线程信息。之后将固定 50 ms 方法和真实 persistent worker 一起做新的独立 full40case 硬件确认。任何历史失败继续保留；本报告及旧样本不能替代该确认。
