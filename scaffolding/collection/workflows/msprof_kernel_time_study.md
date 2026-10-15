# 用原生 msprof 验证算子时间性能

这是独立的方法验证入口。它复用已有 prepared 输入和 A/B 动态库，用原生
`msprof` 的逐 task 记录观察时间；实验结果不写入历史 episode、优化账本或旧
`shared_context_paired_v1` gate。当前支持经过 launch 顺序核验的纯向量核算子。

## 时间口径

| 字段 | 用途及边界 |
|---|---|
| `sum(Task Duration(us)) / repeat` | 主指标：一次完整算子所有串行 kernel task 的耗时之和，包含设备 task 调度、执行和结束响应，排除 task 之间的等待；不称为纯流水线 busy time |
| `sum(aiv_time(us)) / repeat` | 辅助指标：PMU 导出的各向量核平均 task 执行时间之和，不是最慢核完成时间；缺失保留 null，不能填 0 |
| `ACL event elapsed / repeat` | 同一批调用的设备 event 区间，含设备可见的 host 提交间隙；用于对照，不等于 CPU 启动函数用时之和 |
| `task_span_us`、`inter_task_gap_us` | 首 kernel 起点至末 kernel 终点，以及该窗口内 task 间空隙；与 task 耗时分别报告 |

`foreach_norm` 的一次调用包括每个列表成员的 partial 和 finalize。必须按实际
调用序列计入全部 kernel。主指标不覆盖被排除的 host 调度、H2D/D2H 和分配成本，
也不覆盖 kernel 间的等待。多 stream 或发生重叠的 target task 会拒绝聚合。

字段依据为本机 CANN 9.0 的 `msprof --help`、安装目录
`tools/profiler/profiler_tool/analysis/msconfig/filename_introduction_config.py`
及[官方 op_summary 字段说明](https://www.hiascend.com/document/detail/zh/mindstudio/830/T%26ITools/Profiling/atlasprofiling_16_0151.html)。
原始流程参考仓库 `third_party/cannbot-skills/ops/ops-profiling/references/msprof-guide.md`。
工具支持 `profiler_mode=task_time_l1_ai_core_off` 只采 task time，以及
`task_time_l1_pipe_utilization` 同时采一组 PMU。后者是未声明 mode 时的兼容默认值；
不运行指南中用于深度诊断的全部七组 PMU。两种条件分别校准、分别汇总。

## 执行入口

从仓库根目录、已加载 CANN 环境的 shell 执行：
采集/校验使用现有 CANN、NumPy、PyTorch 环境，统计汇总还需要 SciPy。

```sh
python scaffolding/collection/scripts/cannbench_msprof_timing.py build \
  --output /absolute/new-study/runner --repeat 10

OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
python scaffolding/collection/scripts/cannbench_msprof_timing.py collect \
  --request /absolute/request.json --output /absolute/new-study/session-01

python scaffolding/collection/scripts/cannbench_msprof_timing.py summarize \
  /absolute/new-study/session-01 /absolute/new-study/session-02 \
  --output /absolute/new-study/summary.json
```

请求文件例子（路径替换为真实、已构建产物）：

```json
{
  "version": "msprof_kernel_time_study_v1",
  "role_build": "/absolute/aa-build/build_manifest.json",
  "runner_build": "/absolute/new-study/runner/build.json",
  "profiler_mode": "task_time_l1_ai_core_off",
  "device": 0,
  "cpu": 8,
  "load_order": "AB",
  "first_order": "AB",
  "buffer_configs": "normal,swapped",
  "cases": [
    {
      "case_id": 1,
      "metadata": "/absolute/prepared/case_01/metadata.json",
      "verifier": "/absolute/baseline/scripts/verify_result.py"
    }
  ]
}
```

采集命令实质为：

```sh
taskset -c 8 msprof --output=/absolute/raw \
  --task-time=l1 --ai-core=off \
  --ascendcl=off --runtime-api=off /absolute/runner ...
```

`msprof op` / `msopprof` 不参与此入口。既有深度诊断工具仍可独立收集机制数据。
需要对照 PMU 平均核时间时，显式选择 `task_time_l1_pipe_utilization`，对应
`--ai-core=on --aic-metrics=PipeUtilization`。只采 task time 时辅助 `core_us` 为 null。

`run_msprof_timing_study.py --plan PLAN --output NEW_DIR` 可以串行执行预先冻结的
有限计划。`schedule` 每项含 `name`、`cohort`、`request`；输出目录拒绝覆盖，失败
不会自动重试。一个 cohort 的汇总以独立 native process 为重复单位，先在每个
进程内计算 30 对 log(A/B) 的平均，再给进程间 t 区间。normal/swapped 分别汇总。
没有异常值删除，也不把数千次 kernel launch 当作数千个独立进程。
汇总拒绝重复进程目录，以及不同 build、case 集合、设备/CPU、PMU 或 host delay
条件的混合输入；不能把开/关 PMU 的样本拼成一个置信区间。

## runner 与证据

构建工具从既有共享 context runner 生成独立副本，只改变 repeat 及相应数值换算、
加入受控 host delay、保持动态库映射至进程退出，并给 journal 加入独立协议标识。
原 runner 和 kernel 源码不变；原文、生成文件、精确 patch、ABI、二进制 hash 与
构建命令保存在新 build 目录。模板不匹配时拒绝生成，要求先审查适配。

host delay 默认 0；请求中的 `host_delay_a_us` / `host_delay_b_us` 只用于方法干预，
在 event 之后、每次完整算子提交之前调用 `usleep`。它不是优化候选；实际睡眠可
超过请求值，真实 event 与 task 时间均保留，不能假定它对设备状态完全没有影响。

每个 case/config 固定预热 10 次、30 对交替 AB/BA；repeat 默认 10。预热在同一
进程/context/stream 中执行，并由 journal 和完整 CSV 顺序确定剔除窗口。解析核对
目标 kernel 名、顺序、数量、设备/stream、重复记录、非正时间及 native 正常退出。
CSV 时间戳以 Decimal 排序，避免大绝对时间戳损失微秒小数精度。

采集持有主机锁及兼容的全部设备锁，记录前后 NPU 占用状态。输出在 native 退出后
交给原始、可安全导入的 oracle 完整校验，避免校验过程影响计时；覆盖每个
case/config/role 最后一个正式样本的最后一次输出，不宣称验证了所有中间调用。

主要产物为 `request.json`、`bindings.json`、`cases.json`、`native/journal.jsonl`、
原始 profiler 目录、每份输出的 oracle 日志、`samples.json` 和 `completion.json`。
`samples.json` 的每个样本保留对应原 CSV 行号。原始失败也保留；修复解析器后的
重分析另存，不覆写原失败状态。

## 使用结论的边界

低 CV 只能说明在该采样配置下波动较小，不能代替 A/A 无偏性、加载顺序和资源
角色检查，也不能证明 profiler 没有扰动 kernel。应分别报告 A/A 偏差、进程级
区间、进程内 CV，以及不同加载/缓冲区配置的结果。六进程、小 case 集的方法
试验不是全算子、全 workload 或亚百分比收益的正式准入。

如果训练优化轨迹以此时间为目标，必须保存独立 metric/protocol 标识及原始
单位；旧 event 时间与新 task 时间不能混作同一标签。端到端吞吐和延迟需要另行
评价。当前研究入口不会自动改写原 workflow、schema 或生产 gate。
