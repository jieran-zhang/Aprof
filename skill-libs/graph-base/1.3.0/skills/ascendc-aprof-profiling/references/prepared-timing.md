# 输入与 oracle 准备复用

本页说明仍可复用的准备工具。新性能计时统一使用 [L2 清理 Task 协议](unified-timing.md)；旧双进程 Event 示例不再用于新会话。

## 一次准备，按身份复用

```bash
python3 scripts/prepare_workload.py --config <preparation.json> --cache-dir <task-prepared-cache> --receipt <new-preparation-receipt.json>
```

配置示例：

```json
{
  "schema_version": "1.0.0",
  "workload": {"shape": [1024, 1024], "dtype": "float16"},
  "dependencies": {
    "python": "/absolute/python3",
    "generator": "/absolute/scripts/generate.py",
    "oracle": "/absolute/scripts/oracle.py"
  },
  "commands": [["{dep:python}", "{dep:generator}", "--output", "{output_dir}"]],
  "outputs": ["input.bin", "expected.bin", "metadata.json"],
  "timeout_seconds": 300,
  "environment": {}
}
```

每条命令以显式 `{dep:name}` 可执行文件开头。声明所有影响生成/oracle 语义的依赖，包括 import 文件和相关环境变量。工具无法发现未声明依赖。子进程只继承工具默认的 PATH、LANG、LC_ALL 以及显式 environment；所需 CANN、PYTHONPATH 和库路径必须声明。

缓存键绑定 workload、依赖内容、命令模板、输出清单、环境和 producer 身份。依赖位置不入键，字节相同的工程副本可复用。命中前复核依赖与输出完整性，产生新命中回执并引用原始不可变证据。缓存的是数据准备，绝不缓存候选正确性。

输出从一开始使用稳定路径，确保含绝对路径的 metadata 可用。只有成功并验证的尝试才成为 ready；失败保留但不能命中。拒绝输出/缓存符号链接；锁忙则报错，不擅自删除不明归属锁。缓存移至另一绝对位置时重新准备，避免内嵌旧路径。

候选输出保存在准备缓存外。每个修改后的候选执行完整正确性；每个计时实现仍核验其实际执行路径输出。

## 完整调用适配

使用 `assets/device_single_role_task.h` 的 `RunSingleRoleTask`，在输入、分配和 H2D 准备好之后调用。目标 callback 包含一次完整算子调用的所有 kernel、scratch 初始化和流内依赖；清 L2 callback 独立提供；输出快照与 oracle 在计时外执行。

A/B 使用同一时序与地址策略，记录各自真实 kernel 顺序；算法变化可以改变 kernel 数量，不能遗漏其中一段。保留普通正确性路径。源、二进制、输入、输出和 adapter 审查记录随采集证据绑定。

历史 `device_timer.h` / `aprof::Run` 是 Event 工具，不能作为当前 Task Duration 的替代。其历史结果按原协议解释，不用当前验收重新标注。
