# 原始 Python oracle 回放

runtime 0.2.5 提供 `original_python_v1`。需要 BF16、MERE/MARE、小值区域错误计数、native 参考、TensorList 或算子自定义判据时，使用此入口执行原程序；不把原规则翻译为逐元素 allclose。原有逐元素 adapter 仅用于原契约本来就是逐元素容差的任务。

## 配置与冻结

在 case 中设置 `oracle_source` 和 `oracle_replay`，此模式不使用旧的 `oracle_command`/`checks`。以下例子执行已有的 exp verifier，所有绝对路径和版本均需换为实际值：

```json
{
  "oracle_source": "/task/exp/scripts/verify_result.py",
  "oracle_replay": {
    "mode": "original_python_v1",
    "entrypoint": "verify_result.py",
    "argv": ["--metadata", "metadata.json"],
    "files": {
      "verify_result.py": "/task/exp/scripts/verify_result.py",
      "metadata.json": "/task/case-3/oracle-metadata.json",
      "input.bin": "/task/case-3/input.bin"
    },
    "outputs": {
      "output.bin": {"actual": "outputs/output.bin", "dtype": "bfloat16"}
    },
    "result": {"path": "result.json", "passed_field": "passed"},
    "environment": {
      "python": "/absolute/python3",
      "sha256": "sha256:<Python实际文件摘要>",
      "packages": {"numpy": "<实际版本>", "torch": "<实际版本>"}
    },
    "timeout_seconds": 60
  }
}
```

`files` 的键是回放目录内的相对路径，值是待冻结文件的绝对路径。保留原有目录结构，登记完整本地 import 闭包，以及输入、golden、native 参考、属性和阈值文件。metadata 只能做路径重定位，例如把 input/output 改为 `input.bin`/`output.bin`；shape、dtype、属性、阈值和数值内容保持原样，并保存重定位前后文件。不得把 actual 放进 golden 的位置，或让 oracle 读取未冻结的外部路径。

`outputs` 逐项对应 native 的实际输出；`actual` 必须位于采集目录的 `outputs/` 下，键为原 oracle 读取的相对位置。回放执行前复制原始输出，不转换 BF16、不生成 sentinel，不从 passed 标签推断精度。多输出必须全部列出。原程序使用 `precision_pass` 等结果字段时只配置 `passed_field`，不改判据。

准备阶段使用本包 runtime 的 `aprof_runtime.original_oracle.config_contract(spec)` 计算实际 `oracle_replay` 的契约摘要，然后冻结：

```python
case["workload"]["oracle_limits"] = {
    "mode": "original_python_v1",
    "contract_sha256": config_contract(case["oracle_replay"]),
}
```

该摘要绑定程序/依赖/输入/golden 字节、参数、输出映射、结果字段、环境和超时。采集时再次核对，不能在看到结果后重签 workload。timing 和 correctness 必须使用相同契约；不同源码的 A/B 也不能换 oracle 或 golden。

## 执行与失败分类

先执行 `single_role_task.py --config <config> --output <new-preflight.json> --preflight-only --timeout-seconds <remaining>`。它检查全部 case 和 Python 包版本，任何缺项在启动第一个 native 进程前返回。此结果只是能力检查，不是构建、NPU 正确性或计时通过。随后按统一协议执行 correctness-only，再采性能。

live 与离线回放都在独立临时目录运行同一份冻结程序。回放需要可用且摘要匹配的 Python、声明版本的第三方包；依赖缺失应补齐执行环境，不能改判据。程序、依赖、metadata 和实际输出在 oracle 前后均检查未变；超时终止自己的子进程组。live 原始 stdout/stderr、退出码和结果 JSON 保存于 `logs/oracle.*`。

同一次 collect/finalize 内，契约与实际输出摘要完全相同的已执行结果可复用，文件仍重新校验 hash。缓存只由真实执行成功填充，不写进回执，不跨进程保存；新一次离线审计仍重新执行原程序。这样避免收尾对相同字节重复启动 Python，而不把 passed 标签当作证明。

这是对受信任务代码的执行，不是运行未知代码的安全沙箱。准备阶段仍需审查原 oracle 的输出覆盖、依赖闭包和参数接线。包版本核对不等于冻结整个系统环境。

| reason | 含义与后续 |
| --- | --- |
| oracle_adapter_unsupported | 当前选定 adapter 表达不了原契约；修适配或新开发包，不计数值失败 |
| oracle_environment_unavailable | Python/包缺失或变化；修环境后在剩余预算内继续 |
| oracle_execution_failed | 程序异常或未输出有效原结果；保留日志排查 |
| numerical_mismatch | 原程序对真实输出返回 false；进入正确性诊断，不能放宽 oracle |
| oracle_timeout | 达到原始阶段/任务剩余预算；保留失败与成本，不重置计时 |

迁移旧原始数据可用于独立回归测试，但不能补造旧轮次执行。新正式任务须重新冻结包、输入锁、workload 与声明。批次级启动顺序由上层 batch skill 管理。
