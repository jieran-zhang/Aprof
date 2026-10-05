# 本机串行性能续采

本文记录已封存的 2026-09-08 serial run；下文“当前”均指该历史协议。
新的实验组织见[实验手册](optimization_experiment_playbook.md)，新的性能
比较规范见[共享 context 配对协议](shared_context_paired_protocol.md)。
此处 `single-live-context` 是每个角色样本新启进程、一次仅一个存活，
并非新规范中的 A/B 共用原生进程/context。旧绝对漂移硬阈值和命令
保留用于解释历史结果，不能作为新协议已实现的依据。

当前正式续采 run 为 `.aprof/runs/level1-serial-final-20260908T011500Z`，
使用 `single-live-context` 和 `reuse-verifier`，补测旧 run 已冻结的 24 个
源码候选。父 run 为 `.aprof/runs/level1-20260907T152600Z`；源码、候选
身份和父归档保持不变，不根据本轮计时结果追加候选。

在启动正式续采时，单上下文方法仅在独立 probe 的 **exp case 8** 上
通过了正常、反向两个 A/A 会话的比较。该 probe 不证明其他 case、算子
或优化候选已经通过，也不构成性能收益证据。正式结果以各算子的控制
决策及导出器准入结果为准；`serial_progress.json` 单独记录已关闭与
待完成的算子，不把进度报告作为最终交付。

## 当前采样协议

协调器只在本机运行，物理设备为 0，计时进程固定在 CPU 8。它持有
`/tmp/aprof-device-locks/host-serial.lock` 和全部 16 个 `device-N.lock`，
排除仍只识别单设备锁的旧 worker。每个算子批次前后保存 `npu-smi info`，
要求设备进程表为空。健康记录和进程时间区间同时保留；协议锁无法约束
不遵守锁协议的外部程序。

`single-live-context` 保证一次只存活一个 ACL 计时进程。每个角色的
采样都新建进程；采样结束并确认该进程完全退出后，才启动下一个角色。
每个新进程执行以下固定步骤：

1. 准备输入、分配设备内存、完成 H2D，并预热完整算子 10 次。
2. 执行一个预处理样本，其中包含完整算子的 100 次调用。
3. 执行一个正式样本，同样包含完整算子的 100 次调用；ACL event
   时长除以 100，得到每次完整算子的设备事件时长。
4. 完成进程退出，再进入下一个角色。

每个 case 采集 **30 对**正式样本，正常会话交替 AB/BA；反向会话从
BA 开始交替。预处理样本全部保留，但不纳入收益估计；每个新进程的
原生 `sample_index` 重新开始计数，生命周期证据与每轮日志分别保留。

当前 manifest 为 `capture_replay=false`，使用直接提交的 prepared-input
ACL event harness。初始化、分配、H2D 和输出校验都在计时区间之外。
TensorList 的一次完整算子调用覆盖全部列表项，`foreach_norm` 包括
每项的 partial/finalize。每个 case 结束后，分别验证 baseline 和
candidate **最后一个进程的输出**；此前各轮输出没有逐个独立校验。
`reuse-verifier` 预加载未修改的校验模块，对这些最终输出完整调用
`main()`，省去重复解释器与依赖初始化。

## 每个算子的控制与准入

当前 manifest 的 `calibration_scope=per_operator_before_and_after`。
`collect` 直接执行以下流程；历史四条件 `pilot` 不是当前正式续采的
必要步骤，也不能替代每个算子的控制：

1. 用该算子的原 baseline 做 `before` 正常 A/A 和
   `startup-reversed` 反向 A/A。两个会话都覆盖四个 sentinel：
   **1、8、14、20**。
2. 只有两个控制会话逐 case CV ≤ 5%、A/A 角色偏差 ≤ 2%、两会话
   各角色及合并中位数漂移 ≤ 2% 时，才测该算子的全部冻结候选。
   每个候选均测完整 **20 个 case**，每 case 30 对。
3. 候选批次完成后再做四个 sentinel 的 `after` A/A，并与 `before`
   比较。后置控制失败时，该批数据保留，性能准入失败。

控制决策通过仅表示测量控制合格。每个候选还须具备成功的执行记录、
完整配对样本和当前正确性证据；收益要求保持为 95% speedup LCB ≥ 1.03、
最坏 case 回退 ≤ 3%、每 case CV ≤ 5%。未完成、失败或未准入的数据
不得报告为已验证收益。

## 建立与继续当前流程

以下变量对应实际父归档、单上下文 probe 和正式续采 run：

```bash
REPO=/mnt/tidalfs-hwwh01/dataset/dots_infra/workspace/jieran/APROF/aprof-feat-aprofgraph
PY=/usr/local/python3.11.15/bin/python3
PARENT="$REPO/.aprof/runs/level1-20260907T152600Z"
SINGLE_PROBE="$REPO/.aprof/runs/level1-single-context-probe-20260908T011000Z"
RUN="$REPO/.aprof/runs/level1-serial-final-20260908T011500Z"
```

新建时必须把方法选项写入 manifest，再封存输入。下列命令记录当前 run
的建立方式；当前 run 已存在，`init` 会拒绝重复初始化。复现为另一个
新 run 时，将 `RUN` 改为尚不存在的目录。

```bash
"$PY" "$REPO/scripts/run_level1_serial.py" init \
  --run "$RUN" --parent "$PARENT" \
  --single-live-context --reuse-verifier --method-parent "$SINGLE_PROBE"
"$PY" "$REPO/scripts/run_level1_serial.py" seal-inputs --run "$RUN"
```

`seal-inputs` 对齐父 run 的冻结名单并绑定 prepared metadata、输入和
oracle 文件摘要。正式采集由一个协调器执行，协议选项从 manifest 读取：

```bash
"$PY" "$REPO/scripts/run_level1_serial.py" collect --run "$RUN"
```

本次已有协调器在采集。恢复时，在原协调器退出后使用同一条 `collect`
命令；完整且验证一致的执行归档可以复用。未完成的本地 scratch 或共享
`.partial` 目录须保留并审查恢复，不能覆盖。数据先写本地磁盘，再原子
发布到共享归档；每个 case 完成或发生异常时保留检查点。

## 后续按已关闭算子导出

算子完成控制决策并具备终态证据后，可在 CPU 40 上逐步导出：

```bash
taskset -c 40 "$PY" "$REPO/scripts/finalize_level1_serial.py" \
  --run "$RUN" --ready-only
taskset -c 40 "$PY" "$REPO/scripts/finalize_level1_serial.py" \
  --run "$RUN" --ready-only --verify-only
```

`--ready-only` 只导出已关闭算子的完整冻结批次，其他算子继续记为 pending。
它更新 `serial_progress.json`、`serial_checkpoint.json` 和已关闭算子的
报告、JSONL、CAS；进度导出不表示整轮交付完成。导出器重新核对测量、
控制、源码和日志绑定，拒绝将未准入观测提升为收益。

全部算子关闭后，才执行完整导出及复核：

```bash
taskset -c 40 "$PY" "$REPO/scripts/finalize_level1_serial.py" --run "$RUN"
taskset -c 40 "$PY" "$REPO/scripts/finalize_level1_serial.py" --run "$RUN" --verify-only
```

train 和 validation 分别保存证据。本轮仍是 measurement continuation，
不增加源码尝试或正式 graph-policy episode。父 run 的 msprof 仅作为
继承的机制证据，不能称为本轮重新串行采集的 profile。

长时间采集可由独立 CPU 监督程序完成上述导出步骤。将 `COLLECTOR_PID`
设为正在运行的本 run 协调器 PID 后启动一次：

```bash
"$PY" "$REPO/scripts/watch_level1_serial_export.py" \
  --run "$RUN" --controller-pid "$COLLECTOR_PID" --cpu 40 --interval 60
```

监督程序不启动硬件命令。它绑定 PID 与进程启动时钟，等待每算子的控制
决策和 `health-after.json` 终态，再执行增量导出；七个算子关闭后执行
完整导出与独立复核。当前状态位于 `export-observer/state.json`，每次
命令的 argv、源码摘要、退出状态和日志另存于该目录。协调器提前退出时，
待完成算子保持 pending，监督程序不会制造优化结果。

监督程序与 exporter 共享独立的进程锁。即使监督进程被杀死，仍在写入的
exporter 子进程也会持锁直至退出，防止重启时并发归档。源码在监督开始时
绑定，并在每次导出前后检查；更新归档代码需要等现有导出结束后重启监督
程序，已有事件和封存结果继续复用。

## 历史方法研究与当前 probe 的边界

最初的四条件研究位于 `.aprof/runs/level1-serial-20260908T003200Z`。
它使用两个常驻 ACL 上下文，按无预处理/正常、有预处理/正常、
有预处理/反向、无预处理/反向的固定顺序研究 exp baseline A/A。
虽然四个条件全部 CV < 1.64%，反向预处理条件仍有约 4.41% 的同二进制
角色偏差，因此未获准入。manifest 中保留的四条件 `pilot` 字段属于
这条历史方法路径；当前 `collect` 使用上述逐算子前后控制路径。

随后 `.aprof/runs/level1-capture-probe-20260908T005000Z` 研究了
ACL device graph capture/replay：独立测量工程只更新 timer header，
绑定 harness patch、新源码快照和重编译二进制。API、执行和精度检查
通过，但 exp case 8 的角色偏差仍超过 2%，该方法同样未准入。
它的 `complete_operator_device_graph_event_interval` 数据独立保存，
不得与当前直接提交的事件时长混池。

这两个失败研究均已单独归档为 blocked 的方法任务，优化候选和 episode
数为零；原始 A/A、构建、健康检查和控制器失败证据保留。验证器复用资格
比较的首次完整 stdout 检查受 redis/hiredis 导入警告次数影响；后续结果、
退出码和主输出比较通过。原始警告日志保留，未保存的外层命令与时间不补造；
gelu 的资格细节单独放在 validation CAS。

当前方法父节点是 `.aprof/runs/level1-single-context-probe-20260908T011000Z`。
它只证明单存活进程协议在 exp case 8 的两种顺序控制上通过比较。
`--method-parent` 连接这些方法证据，不继承优化收益，也不减少正式续采
所需的逐算子四 sentinel 控制和候选 20-case 验证。
