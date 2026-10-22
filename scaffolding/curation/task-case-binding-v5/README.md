# Task v5：按 case 绑定完整 callback 任务序列（未应用）

状态：源码补丁与 CPU 检查草案。基于已封存 `graph-base/0.5.1`，没有修改该包、`1.0.0` runtime 或默认入口，没有启动硬件测量。

新协议名：`shared_buffer_msprof_task_window_v5`。它与现有 v4 的配置合同不同；不能将旧回执改名后用于新协议准入。`measurement_entry.py` 已从 Task 回放模块导入协议常量，不需要增加旁路入口。

## 唯一合同变化

以下两个原本全局的字段改为 **role → case ID → 值**。JSON case ID 使用 `expected_case_ids` 的十进制字符串；两个角色的 key 集合必须完整、完全一致，不允许默认值或缺项回退。

```json
{
  "roles": {
    "baseline": {"source_dir": "/baseline", "symbol": "baseline_callback",
      "launches_per_operator": {"1": 5, "2": 7}},
    "candidate": {"source_dir": "/candidate", "symbol": "candidate_callback",
      "launches_per_operator": {"1": 5, "2": 7}}
  },
  "task_profile": {
    "profiler": "/usr/local/Ascend/cann-9.0.0/tools/profiler/bin/msprof",
    "scratch_root": "/task-local/scratch",
    "role_kernel_names": {
      "baseline": {
        "1": ["reorder_b", "qk_fp16_b", "softmax_b", "pv_fp16_b", "scatter_b"],
        "2": ["reorder_b", "qk_bf16_b", "qk_bf16_b", "softmax_b", "pv_bf16_b", "pv_bf16_b", "scatter_b"]
      },
      "candidate": {
        "1": ["reorder_c", "qk_fp16_c", "softmax_c", "pv_fp16_c", "scatter_c"],
        "2": ["reorder_c", "qk_bf16_c", "qk_bf16_c", "softmax_c", "pv_bf16_c", "pv_bf16_c", "scatter_c"]
      }
    }
  }
}
```

这是字段片段；其余 source/build、case command、workload、输入和 oracle 字段保持原合同。数组是一次完整 callback 的有序任务序列，重复的 kernel 名称必须保留，长度必须等于该 case/role 的 launch 数。两个角色允许不同的完整 launch 数，A/A 阶段依然执行 baseline 实现。

GQA/WQMM 配置生成方可以直接转换现有 `shared-multikernel-adapter-design-v1/shared_multikernel_adapter.py::case_binding(operator, metadata)`：逐 case 将 `launches_per_call[role]` 写到 `roles[role].launches_per_operator[str(case_id)]`，将 `role_kernel_names[role]` 写到对应序列 map。必须使用原全量 metadata 和受审核组合 binary，保留完整 GQA QK/PV 循环以及 WQMM dequant/matmul/post。本文示例名称是合成测试名称，不是可提交的硬件绑定。

## 四个最小修改点

| 文件 / 函数 | 变化 |
| --- | --- |
| `task_window_timing.py::case_task_config` | 校验全部 case/role map；为指定 case 生成临时 scalar view。原 `partition_window_tasks`、`choose_task_repeat` 函数字节不变。 |
| `device_task_window_timing.py::config_value / run_session` | 通过 scalar view 复用原完整路径/source/build/workload 校验，随后恢复完整 map；采集解析按实际 `case.case_id` 选取。 |
| `measurement_admission.py::_config_identity` | 增加默认关闭的 `case_launch_counts` 参数。只有新 Task 回放启用 map；旧 Event 和其它回放调用的 scalar 合同不变。 |
| `task_window_measurement_admission.py::replay_task_window_measurement_admission / _session` | 明确 v5；冻结和校验完整 map，并按 `session.case_id` 使用与采集器同一 helper。 |

config hash、registration、source/build/binary/hardware、case command/workload/input 和完整尝试身份仍绑定原完整配置。临时 scalar view 只用于既有配置检查与 native/CSV 解析，不写成新的证据。native READY 及每次 sample 的实际 launch 数仍与所选 case 核对，全部 CSV 行仍进入原有严格的串行分组回放；不按名字挑选局部任务。

native `RunShared` 已接受当次两个角色的 launch 数，现有组合 host 按数学 argv 计算 GQA 数量，header 无需修改。本补丁没有更改 callback、计时边界、v0002、schemas、gate 数学、预热、六周期、每阶段五对或 repeat 选择。

## CPU 验证

运行：`python scaffolding/curation/task-case-binding-v5/run_cpu_checks.py`。

测试脚本只向 `/tmp` 复制所需 Python 源码和 header，零 fuzz 应用补丁；退出后移除测试副本。没有创建新 skill-lib 副本、NPU 进程或真实 profile 归档。

本次结果：**25 passed / 5.15 s**，见 `cpu-checks.log`。

- 两个 case 的 fp16/bf16 序列、5/7 个 launch，以及合法重复 kernel 名称：完整 pilot、首末确认周期均通过。
- 独立角色的不同 launch 数可表达；逐 case 完整 Task Duration 求和保持原算法。
- 缺任务、额外任务、重复 CSV 记录、错误 kernel 顺序/dtype/native 数量、未登记 case、map 缺项/多项/计数不符均拒绝。
- 真实 collector 配置校验保留完整 map，并继续拒绝缺失的原始 verifier 文件。
- 单 case 的完整合成 registration → calibration → 六周期 → 原始回放链通过；旧 v4 回执和篡改后的角色绑定拒绝。两 case 的检查覆盖配置与完整 Task 解析，不宣称完成两 case 硬件或全 controller 验收。

## 仍需单独决定的边界

**冻结现有 runtime 字节与支持这个新合同不能同时成立。** 本补丁必须进入后续明确版本的 runtime/collector 并重新绑定 producer 身份，才可用于五算子评估；0.5.1 继续只接收已发布 v4。尚未应用或发布此补丁，不宣称新方法已通过硬件资格验收。

`R >= 100`、baseline-only pilot、30 对正式样本和全部控制/快照均保持原样。GQA 每次完整调用的多次 launch 会相应放大 profile 行数与时间成本；本补丁只解决可表达性，不能证明整轮可在预算内完成，也没有实测超时结论。采样成本与是否需要另一个预登记协议必须单独判断，不能删 kernel、缩小 case 或暗改 R。

完整正确性、boundary、六对独立探索、五次机制、实际 exit、全尝试 roster 与任务总预算仍由既有外层合同负责。本补丁不替代这些检查。
