# 统一性能计时协议

新任务必须按 [soft_targets_local_v1](../../../workflows/references/execution-policy.md) 执行：耗时仅为软目标，baseline 默认 assumed，新候选完整验证一次，按全输出内容复用；所有运行产物留在 /dev/shm。

采集协议 ID：`single_role_l2_clean_task_v1`。1.3.0当前优化探索使用显式预声明的[中位数稳定性v2](median-stability-v2.md)，采样与完整调用口径不变。1.2.0及旧记录按各自声明回放。旧 v5/Event 和早期 screen manifest 保持历史含义，不自动升级或作为回退。

## 测量定义

每个 case、每个实现启动一个新 native 子进程：

1. 准备输入和单次设备分配，完成设备稳态准备与必要身份检查。
2. 执行 5 次完整调用预热；预热不计入样本。
3. 启动 `ACL_PROF_TASK_TIME`，PMU 不混入计时。
4. 重复 20 轮：同一 ACL stream 上先执行真实 `CannBenchCacheClean`，再执行完整目标调用，最后同步。清理缓冲区大于实际 L2 容量。
5. 停止并 flush profiler，在计时外保存输出、验证输入未变。
6. 仅导出一次原始 Task 表，执行原 oracle 和输出核验，保留 raw profile、日志、退出码、时间与所有来源。

目标 callback 包含全部组成 kernel、scratch 初始化和必要依赖。驱逐时间不计入目标时间。输入不可修改，输出必须完整写入；有状态、原地修改或并行重叠任务需要相应 adapter/计时定义，不假定当前串行 Task 求和适用。

`assets/device_single_role_task.h` 提供时序；算子提供完整调用、真实清 L2 和输出 snapshot callbacks。控制器不生成这些算子代码。设备稳态准备由受审阅 adapter 实现，不能把仅执行 5 次算子预热当成已证明频率稳定。

## 完整调用解析

优先 kernel_details.csv，仅在它不存在时使用 op_summary。原始表不做 task-name、时长或迭代过滤。每个清 L2 marker 后必须是该实现预注册的完整有序 kernel 序列，重复名字仍作为独立 Task 保留。

恰好重建 20 次完整调用，各次求目标 Task Duration 之和，然后按预声明统计策略取中位数。禁止先对各 kernel 取中位数再相加、取最长 kernel 或改写原始样本。Stream ID 必须存在且整次采集一致，缺项、额外 Task、乱序或流变化拒绝。Task 总和不是重叠多流 workload 的整体延迟。

20 次是同一个进程内重复，不是 20 个独立进程，也不是 20 对 A/B。轮内 CV 仅反映轮内波动。

## 统计策略按版本选择

当前1.3.0探索任务在declaration v3中选择`median_stability_exploration_v2`／`bounded_outlier_v2`：一次对称检测、最多4/20、处理后CV≤10%，另报告双方原始中位数的跨窗口漂移及剔除敏感性。完整定义、需复核与收益的区别见[中位数稳定性v2](median-stability-v2.md)，不把轮内CV当作中位数跨窗口误差。

### 历史 bounded_outlier_v1

旧任务在 declaration.json 中预声明 `stability_policy: "bounded_outlier_v1"`。从全部 20 个完整调用时长计算中位数 m 和 MAD；仅当 |x−m| > max(3×1.482602218505602×MAD, 0.10×m) 时标记异常。最多剔除 2/20，保留至少 18 个样本；对保留样本计算中位数与样本 CV，CV 仍须 ≤5%。两侧用相同规则，快慢异常对称处理且只计算一轮，不能反复剔除直到通过。超过 2 个异常则不剔除并判 inconclusive。原始 CSV、全部 20 个值、阈值、异常/剔除索引和原始 CV 都保留。未声明此字段的旧记录继续按原始 20 值判定，不追改历史结论。

这是确定性的工程稳定性规则，不是异常原因鉴定或统计置信区间。新设备/采集方式应先用包含短 case 的独立进程复验检查中位数可重复性；剔除异常不能修复跨进程漂移。

## 先声明，再执行

会话开始冻结 declaration.json：

```json
{
  "schema_version": 3,
  "operator": "exp",
  "stability_protocol": "median_stability_exploration_v2",
  "stability_policy": "bounded_outlier_v2",
  "replication_policy": {"max_retests": 1, "estimator": "last_executed_window"},
  "created_at": "2026-10-16T00:00:00+00:00",
  "case_ids": [1],
  "correctness_case_ids": [1],
  "reuse_policy": {
    "max_age_seconds": 600,
    "max_ab_gap_seconds": 600
  }
}
```

示例时间和 600 秒只演示格式，必须替换为实际采集前时间与本会话预声明策略；它们不是已经实测校准的通用有效期。正确性集合可以大于计时集合，但必须覆盖计时集合。完整计时集合在反馈开始前固定，不能看到坏 case 后缩小。

declaration 的文件 hash 绑定后续采集、正确性和比较请求，不能事后放宽时限再当作原计划。

## 正确性与采集命令

从 profiling skill 目录执行，或使用脚本绝对路径：

```bash
python3 scripts/single_role_task.py --config <implementation-config.json> --output <new-correctness-dir> --correctness-only --timeout-seconds <remaining-seconds>
python3 scripts/single_role_task.py --config <implementation-config-with-correctness.json> --output <new-capture-dir> --timeout-seconds <remaining-seconds>
```

候选对完整 correctness 集执行第一条命令，产生真实 correctness.json；计时配置用 `correctness: {path, sha256}` 引用，核对全部身份和实际输出内容。默认 baseline 设置 `baseline_status="assumed"` 并在 declaration v3（旧协议为v2）声明 baseline_trust，不执行第一条命令，也不伪造 correctness.json。用户明确要求验证 baseline 时才执行一次。

采集配置核心字段：

```json
{
  "schema_version": 1,
  "protocol": "single_role_l2_clean_task_v1",
  "operator": "exp",
  "implementation": "exp_complete",
  "source_files": ["/absolute/op/kernel.cpp", "/absolute/op/host.cpp"],
  "binary": "/absolute/op/build/exp",
  "adapter_files": ["/absolute/shared-adapter.cpp"],
  "toolchain_files": ["/absolute/compiler"],
  "device": 0,
  "hardware_probe_command": ["/absolute/python3", "/absolute/device_probe.py"],
  "export_python": "/absolute/sdk/python3",
  "export_script": "/absolute/sdk/msprof.py",
  "declaration": {"path": "/absolute/declaration.json", "sha256": "sha256:<实际文件摘要>"},
  "cache_policy": {
    "eviction_kernel": "CannBenchCacheClean",
    "eviction_bytes": 268959744,
    "l2_bytes": 201326592,
    "address_policy": "reuse-one-allocation"
  },
  "cases": [{
    "case_id": 1,
    "workload": {"shape": [2], "dtype": "float32", "oracle_limits": {"atol": 0, "rtol": 0, "equal_nan": false}},
    "input_files": ["/absolute/input.bin"],
    "kernel_names": ["exp_kernel"],
    "command": ["/absolute/op/build/exp", "--profile", "--input", "/absolute/input.bin", "--output", "outputs/output.bin"],
    "correctness_command": ["/absolute/op/build/exp", "--input", "/absolute/input.bin", "--output", "outputs/output.bin"],
    "oracle_command": ["/absolute/python3", "/absolute/oracle.py", "--actual", "outputs/output.bin", "--expected", "/absolute/expected.bin"],
    "oracle_source": "/absolute/oracle.py",
    "checks": [{"actual": "outputs/output.bin", "expected": "/absolute/expected.bin", "dtype": "float32", "atol": 0, "rtol": 0, "equal_nan": false}]
  }]
}
```

所有路径、kernel、容量、参数和容差必须替换为实际契约，不能直接运行占位示例。native 命令必须直接执行绑定 binary，cwd 是该 case 的私有目录；argv 是字面参数，没有 shell 或隐式占位替换。输出使用 outputs/ 下的新文件。正常计时配置必须增加上述 correctness 引用；反馈时 cases 可选预声明代表子集，正确性模式必须覆盖全部 correctness_case_ids。

source_files、adapter_files 和 toolchain_files 必须列全影响行为的依赖；工具不能发现遗漏的 include/import 或证明二进制确由该源码构建，构建回执与 adapter 审查仍由准备阶段保留。

硬件 probe 输出 JSON，至少含 device、physical_device、soc_version。physical_device 应绑定主机和物理卡；需要控制的频率/状态也由实际 probe 提供。前后 probe 必须一致。不能把手填静态 JSON 当作已观测设备。

控制器设置 APROF_TASK_PROFILE_DIR、APROF_TASK_CAPTURE_ID、APROF_TASK_CASE_ID，检查 native stdout 唯一采集记录的协议、实现、case、PID、5/20、容量与输入完整性。export 使用冻结 SDK Python 的 `msprof.py export summary -dir <PROF> --format csv`，要求唯一 PROF 树并核验原始文件完整性。

每 case 输出 capture.json 与完整证据。collection.json 汇总引用，collection_costs.json 记录总耗时与快照成本。失败输出 failure.json 和已产生的日志。单次 collect 内私有共享快照减少重复复制，不链接可变用户源码。

### 当前 oracle adapter 范围

runtime 0.2.5 增加 [原始 Python oracle 回放](original-oracle.md)：live 与离线回放执行同一份冻结程序，绑定依赖、输入/golden/native 参考、参数、完整原始输出与环境。BF16、mean/max-relative、区域错误计数和特殊值规则由原程序决定，不额外叠加逐元素判据。

上方旧配置示例仍适用于原契约就是逐元素 atol/rtol/equal_nan 的 float16/32/64、整数和 bool。非逐元素原 oracle 使用新模式；不能为了适配而删 case、换容差或改判据。先用 `--preflight-only` 检查完整配置，随后仍须构建、全量真实正确性和采集。依赖/适配缺失与原 oracle 的 numerical_mismatch 分开记录。

## 比较与正式收尾

全量 A/B 比较前先完成两侧构建、输入、baseline 信任声明、候选完整正确性和存储准备，再连续采集两侧；不要把修复、归档搬迁或额外模型调查插在有效 A 与 B 之间。若已有 A 的剩余有效窗口不足以完成 B，按预声明规则更新 A 并记录目标/实际成本，保留旧记录；不能通过放宽复用窗口续用过期 A。

采集 artifact 不保存 baseline/candidate 角色；以下v2请求指定比较关系；replications登记实际追加窗口，不预先伪造引用：

```json
{
  "schema_version": 2,
  "protocol": "single_role_l2_clean_task_v1",
  "stability_protocol": "median_stability_exploration_v2",
  "replications": {"baseline": [], "candidate": []},
  "operator": "exp",
  "candidate_id": "candidate-1",
  "baseline_source_sha256": "sha256:<A源码清单摘要>",
  "candidate_source_sha256": "sha256:<B源码清单摘要>",
  "declaration": {"path": "declaration.json", "sha256": "sha256:<摘要>"},
  "baseline_captures": [{"path": "a/case_1/capture.json", "sha256": "sha256:<摘要>"}],
  "candidate_captures": [{"path": "b/case_1/capture.json", "sha256": "sha256:<摘要>"}],
  "baseline_correctness": {"path": "a-correctness/correctness.json", "sha256": "sha256:<摘要>"},
  "candidate_correctness": {"path": "b-correctness/correctness.json", "sha256": "sha256:<摘要>"}
}
```

比较请求中的引用相对于 comparison.json 所在目录，不能逃逸该证据根。源码身份取自采集器生成的 source 清单摘要，不随意替换为 git commit 或单个 kernel hash。多个 case 时每侧引用必须恰好覆盖声明集合。

```bash
tools/aprofctl timing finalize --request <comparison.json> --output <new-result.json>
# 需要独立审计时才执行；默认收尾不重复回放。
tools/aprofctl timing verify --result <result.json>
```

runtime 从原始证据计算：

- 每 case：A/B 各自重建全部 20 次调用，按冻结策略得到中位数，speedup = median(A) / median(B)，回归 = median(B) / median(A) - 1。
- 全集合：每 case 加速比的等权几何平均，收益目标 ≥1.03。
- 任一case回归不得超过3%；轮内质量、跨窗口漂移和剔除敏感性按测前选定版本独立报告。当前v2为4/20、CV≤10%的试用规则；旧v1保持2/20、CV≤5%。超限是波动需复核，不直接当性能失败。
- 复用时间、A→B 间隔按预声明策略检查；超限或波动过大保持不确定，不能按有利时段挑样本。

结果是 `performance_engineering_only`，输出 accepted/rejected/inconclusive 及原因，不输出 paired count、95% LCB、生产 best 或策略 reward。正式收尾只有这一次入口，不再调用旧 gate/finalize。verify 回放既有证据，不启动 NPU。

代表集反馈可使用 `fast_task_screen.py --baseline <A-capture.json> --candidate <B-capture.json> --output <new-screen.json>`；它支持新采集的完整来源回放，仍只是单 case 反馈，不替代全 case finalize。旧 screen manifest 与新 capture 不能混用。

## 复用、复验与发布

A/B 必须具有相同 case/workload、输入、实际设备、工具链、采集器及缓存/地址策略。实现源码和 kernel 序列可以不同，分别绑定真实来源。有效 B 可直接作为下一轮 A，无需改写 artifact；变更实现或环境时重新采相应记录。

临界结果、环境变化或异常按预声明规则用同一方法独立复验。不要择优选进程，不重复直到通过；多次尝试全部留存；v2请求保留首测与全部已执行复验，固定使用最后窗口作点估计，并按首测检查每个复验的原始中位数。复验次数服从声明与外部预算，不增加反复采到通过的路径。点估计目标与统计置信下界是不同承诺，轮内 CV 不能证明跨时段稳定。

本版仍未封版。此前三个 case 的 clean 实验支持计时设计；后续维护记录单独提供原 oracle 全量接入和有界异常统计的硬件验证，不能据此宣称所有算子、设备或跨时段条件均已验证。66 秒只来自旧实验条件下 B 计时的估算，新增回放/快照等开销需单独实测；不能宣布 10 分钟正式验收已达成。
