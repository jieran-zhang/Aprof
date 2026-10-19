# 采集与归一化接口

从当前包的 profiling skill 目录执行脚本，或使用解析后的绝对路径与随包 runtime 环境。所有命令使用任务私有输出目录，保留实际墙钟和失败日志，不写回安装包。

## 统一性能计时

当前入口为 `scripts/single_role_task.py`，具体配置见 [统一协议](unified-timing.md)和该脚本 `--help`。它调用已有 native adapter，记录完整正确性、设备状态、采集、导出及输出校验；真实完整调用和清 L2 callback 必须由算子工程提供。

BF16 或自定义精度使用 [original_python_v1](original-oracle.md) 绑定并回放原程序。`--preflight-only` 在任何 native 执行前检查全部 case 的 adapter/环境；能力通过后仍需 correctness-only 和真实计时。缺 adapter、缺环境、oracle 执行异常和数值失败分别报告，不把能力缺项误写成原始精度失败。

代表 case 反馈与全 case 收尾共用这条路径。后者用 `tools/aprofctl timing finalize --request <comparison.json> --output <result.json>` 一次核验；没有旧 Task v5 再采集阶段。早期 fast manifest 不能改协议名充当完整证据。

## 冻结已安装工具链

```bash
<package>/tools/aprofctl task toolchain
<package>/tools/aprofctl task toolchain --check <toolchain-binding.json>
```

发现命令支持显式 `--sdk-root`、`--python`、`--cmake`、`--cxx`、`--npu-smi`，不安装或升级 SDK。结果中的 `result.toolchain` 是绑定对象；--check 读取该对象，不读取整个 CLI envelope，也不能同时提供替换工具参数。缺失或变化的工具应报错，不偷偷切换 SDK。工具 hash 不是硬件性能验证。

## 独立机制采集

下面接口用于 PMU/诊断，不能把其中 duration 当成统一性能计时：

```bash
python3 scripts/profile_capture.py select --backend auto --architecture Ascend910C
python3 scripts/profile_capture.py capture --config <capture.json> --output <new-task-local-capture-directory>
```

省略 output 时创建私有临时目录。select 只按声明架构路由，返回 hardware_verified=false；capture 还用 npu-smi 探测实际设备并绑定证据。A3 使用 msprof，兼容 950/dav-3510 使用 npu-compute。A3 显式请求 npu-compute 会在运行目标前失败。

机制配置示例：

```json
{
  "backend": "auto",
  "architecture": "Ascend910C",
  "device": 0,
  "case_id": 1,
  "kernel": "exp_kernel",
  "role": "baseline",
  "source_dir": "/absolute/operator-project",
  "binary": "/absolute/operator-project/build/exp",
  "workload": {"shape": [1024, 1024], "dtype": "float16"},
  "command": ["/absolute/operator-project/build/exp", "--input", "/absolute/input.bin", "--output", "/absolute/output.bin"],
  "cwd": "/absolute/operator-project",
  "warmups": 10,
  "repeats": 5,
  "timeout_seconds": 120
}
```

command 直接执行声明 binary；构建、输入生成和完整正确性在此前完成。生成输入不放源码快照内。有可见设备映射时显式声明 physical_device 和 chip，同时保留逻辑 device。可选 soc 来自实测；tool_path 只能选择已安装兼容工具。

仅 npu-compute 接受 sections 或 set；JSON 先展开 Set 再按首次出现去重 Sections，需要其他顺序时用原生 CLI。msprof 拒绝这些选项。

采集器先运行声明的 host 预热命令，再以独立进程/目录采每次 capture；msprof 使用 --warm-up=0 --launch-count=1。这些不是同 context 预热或内部 replay。多个 collection 必须显式选定，不合并不明来源。

输出包括 logs/receipts、原始文件、capture-manifest.json 和 local-index.json，返回 manifest、manifest_hash、local_index。拒绝已存在输出目录，失败保留日志。performance_gate=false 表示采集成功不等于性能通过。

## 机制指标归一化

```bash
python3 scripts/normalize_profile.py --manifest <capture-manifest.json> --metrics <metrics.json> --local-index <capture-local-index.json> --output <new-normalized-profile.json>
```

manifest 也可为索引内 sha256 引用，原文件必须仍在。选择器对每个独立 capture 展开，文件名精确匹配实际 collection；不要用猜测文件名替换带时间戳 CSV。

```json
{
  "vector_ratio": {
    "unit": "ratio",
    "file": "PipeUtilization.csv",
    "format": "csv",
    "field": "aiv_vec_ratio",
    "where": {},
    "row_aggregation": "median",
    "aggregation": "median"
  }
}
```

msprof 使用真实 CSV/字段；npu-compute JSONL 可按 category=OpInfoSummary 选择。需要每 capture 不同文件名时使用 schema 中 sources 形式，不自造字段。

正式可用机制指标需要 10 次已记录预热、5 次独立 capture 和 CV≤0.05，低于要求保留探索观察。归一化器回放原始来源，输出 1.1 profile、profile_hash、statuses 和新 local_index；后续使用返回的新索引，不覆盖输入。

npu-compute CSV 有 sub_block_id 时，aiv_* 聚合所有 vector* 行，aic_* 聚合所有 cube* 行；其他字段保留所有匹配行。适用行任一 NA/null 都使该 capture 指标不可用，不择优删行。CSV where 仅支持精确 Op Name/OP Name；JSONL where 仅支持 category。

归一化不是候选 gate。采集结果按 [profiling contract](../../../workflows/contracts/profiling.md)交接，机器来源按 [runtime 契约](../../../workflows/references/runtime-contracts.md)核验，正确性、计时和机制证据保持各自含义。永久复制与 CAS 由明确要求的后续 collector 负责，归档不能补写已结束任务的缺失采集。
