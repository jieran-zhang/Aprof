# graph-base 0.4.2 验收记录

0.4.2 基于 0.4.1 发布；runtime 为 0.2.1，默认图仍为 v0002。
Vector / Ascend 910C（A3）是当前优化重点。0.4.1 与 v0001/v0002 的历史字节保留。

## 工具支持与版本边界

| 环境 | 采集选择 | 本轮验证 |
| --- | --- | --- |
| 本机 910C/A3（9392），CANN 9.0.0，aarch64 | msprof op | 完整正确性、两组独立采集、CSV 解析、CAS 来源回放 |
| 950 / dav-3510 | 优先 npu-compute | 上游真实样例离线解析、模拟 CLI 成功/失败边界；未进行 950 真机采集 |
| 910C 上显式要求 npu-compute | 明确拒绝 | 选择器回归通过；没有升级系统 CANN 或驱动 |

npu-compute 的硬件限制来自 [固定版本的官方说明](https://gitcode.com/cann/asc-tools/blob/8b15e97b18375f12e90884eee052d09ca36dcac7/docs/zh/06_npu_compute.md)。
蒸馏来源为 cannbot-skills `1fd7ec9770ecde574be5888c992997ffff910e71`；许可证和修改说明随版本保留。

新增 capture manifest 和 normalized-profile 1.1，正式 gate、finalize 和 store
验证共享原始来源回放。旧 1.0 profile 可以读取；历史 0.2.0 episode 保持只读
验证。旧 exploration outcome 没有 runtime 身份字段，继续用冻结的
0.4.1/runtime 0.2.0 验证；新正式记录必须提供 1.1 来源，不能改绑旧 producer。

## 910C 实测

在隔离目录复制现有 CANNBench exp 工程，逻辑设备 0 对应板卡 0 / 芯片 0。
构建和完整 20-case 正确性全部通过，耗时 400.17 秒。
随后分别为 case 1 和 case 7 执行 10 次独立目标进程预热、5 次独立
`msprof op --warm-up=0 --launch-count=1 --aic-metrics=Default` 采集。
目标命令仅运行已构建程序；构建、数据生成和结果验证均在采集命令外。
这不是同一 context 的连续预热，也不是 30 对 production timing。

| case | workload | Task Duration 中位数 | CV | Vector / Scalar / MTE2 比例中位数 |
| --- | --- | --- | --- | --- |
| 1 | 1024×1024，FP16 | 7.660153 µs | 1.01% | 27.01% / 45.06% / 37.80% |
| 7 | 1009×1021，FP16，尾块 | 7.720154 µs | 2.44% | 26.71% / 44.94% / 37.09% |

比例先在每次 capture 的全部适用核中取 median，再在五次 capture 间取 median。
所有六项收录 metric 的 CV 均低于 5%，两组采集后的输出再次通过正确性检查。
每次调用前后核对源码、二进制和工具的身份，避免把变化后的程序绑定到旧 hash。

**诊断判断：** 两组 workload 都只有约 8 µs，48 个 Vector 核每核约处理 6 个
4096-element tile；Scalar 与 MTE2 活跃比例高于 Vector，值得进一步观察每 tile
控制开销及搬运/计算衔接。各 pipeline 可以重叠，比例不能相加后作为总耗时。
这些指标不足以证明单一的算力或带宽瓶颈。两组的属性也不同，不能把耗时差单独归因于尾块。
下一步可用 timeline 与有独立配对计时的候选，区分控制开销、数据搬运及分核成本。
本轮没有据此强行修改算子，没有候选收益比较或正式最优结论。

[精简实测证据](../../evidence/deliveries/graph-base-0.4.2-validation/index.json)
包含原始 CSV、manifest、过程 receipt、配置、完整正确性结果和归一化指标。
完整 SQLite/CAS、程序和首轮调试产物仍位于索引声明的外部验证目录，首轮记录未改写。
113 个新增精简文件共 736706 字节；不代表完整证据闭包已进入 Git。

另将完整数据库/CAS复制到独立临时目录，所有 12 项指标仅从复制后的 CAS 回放，
检查了 175 个不同对象；修改复制件中的 raw CSV 后，回放被拒绝。
原始证据未修改。详见 [portable replay receipt](../../evidence/deliveries/graph-base-0.4.2-validation/portable-replay.json)。

## 复现入口

从仓库根目录使用稳定包提供的工具（真实采集要求配置中的工程和输入仍可访问）：

```bash
release="$PWD/skill-libs/graph-base/0.4.2"
evidence="$PWD/scaffolding/evidence/deliveries/graph-base-0.4.2-validation"
python3 "$release/skills/ascendc-aprof-profiling/scripts/profile_capture.py" select \
  --backend auto --architecture Ascend910C --soc 9392
python3 "$release/skills/ascendc-aprof-profiling/scripts/profile_capture.py" capture \
  --config "$evidence/case-01/config.json" \
  --output /tmp/aprof-new-case01 --store /tmp/aprof-new-case01.sqlite
python3 "$release/skills/ascendc-aprof-profiling/scripts/normalize_profile.py" \
  --manifest /tmp/aprof-new-case01/capture-manifest.json \
  --metrics "$evidence/metrics.json" --store /tmp/aprof-new-case01.sqlite \
  --output /tmp/aprof-new-case01-normalized.json
```

输出目录必须为新目录。换机器或工程时更新 config 中的真实环境、源路径、binary、
workload、argv 和设备映射；不能只复制旧硬件标签。
完整案例驱动脚本是原验证目录的记录，需要同级 `exp-baseline` 和正确性 receipt。
稳定包自身的使用说明不依赖这些实验目录。

## 软件验收

| 检查 | 结果 |
| --- | --- |
| 0.4.1 历史完整 CPU 回归 | 2711 passed / 11 skipped；未运行两个仅适用新 profiler 的测试模块 |
| 0.4.2 完整 CPU 回归 | 2776 passed / 11 skipped；4 处旧 profile 准入断言需要更新，见下文 |
| 更新后的两个 Level1 测试模块 | 0.4.2 和 0.4.1 分别 52 passed；覆盖上述全部 4 处失败 |
| 独立复制、安装和工具 | runtime 0.2.1 安装、196 文件发布校验、图校验、路由、collector/normalizer/Pipeline smoke 通过 |
| 合成正式证据链路 | 清空仓库环境变量后，contract → gate → finalize → store 重开验证通过；gate/finalize 决策 hash 一致 |
| 原始证据检查 | JSONL/CSV 来源回放、身份/单位/聚合/样本数篡改拒绝、NA/不稳定证据拒绝均纳入回归 |
| 历史与图 | 0.4.1 校验通过；v0001/v0002 与旧版本逐文件字节一致；v0002 编译检查通过 |

四处旧断言来自冻结 Level1 producer 的 normalized-profile 1.0。新 runtime
按设计保留这些证据，但不据此交付正式最优；测试现明确验证 baseline 保留与
`attribution_uncertain`，旧 runtime 继续验证原有成功路径。仅调整两个测试文件，
未改 producer 或 runtime。完整运行后复跑这两个模块，最终覆盖 2780 项通过、
11 项跳过；未再重复整套运行。测试日志保存在外部验证目录的 `software/`。

独立 CPU 测试副本与最终发布包的执行代码完全相同。最后仅修正了一段混合核
适用性说明，随后重新复制、封存、安装并通过发布、图和工具检查。
合成 gate/episode 只验证软件链路，不构成硬件收益证据。

精简证据入口验证通过：496 个文件、19181950 字节。原有 383 条文件索引及
历史状态保持不变；新增 113 个实测文件的 hash、size 与原文件一致。

历史 Level1 仍为 37 条 memory / 26 条 lesson；Level2 仍为 26/48、暂停、
证据不完整、无新增训练资格。未恢复实验，未迁移大型 raw，未处理 push 认证。
