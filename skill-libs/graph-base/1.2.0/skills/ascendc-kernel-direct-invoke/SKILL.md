---
name: ascendc-kernel-direct-invoke
description: 将单个 Ascend C kernel 文件或目录转换成可构建的 Host 直调工程，生成 CMake、运行、数据与可选 simulator 配套文件，并核验启动 ABI。
---

# Ascend C Kernel 直调工程

本技能只补齐启动工程，不改写用户算法。硬件或 simulator profiling 是可选验证；性能优化与当前计时入口见 [主工作流](../ascendc-aprof-coordinator/SKILL.md)。

## 边界

- 原 kernel 是算法依据，保留 `CopyIn` / `Compute` / `CopyOut`、tiling 数学、API 次序和 kernel 类逻辑。
- 只添加目录、CMake、Host runner、数据生成、可选 tiling 二进制与 simulator 配置；相对依赖头文件复制到 `op_kernel/`。
- Host/Device ABI 一致：`GM_ADDR` / `__gm__ uint8_t*` 参数须使用兼容设备指针传递。
- shape、dtype、输入/输出/workspace 大小、blockDim、kernel 名和 tiling 未知时，不能宣称可运行。
- 优先使用用户 `io-spec-json`。自动推断仅适用于明显采用 `inputGM/outputGM/tilingGM` 等签名的常见 AProf Vector kernel。

## 生成与验证

检查 `extern "C" __global__ ... void <kernel>(...)` 的参数顺序，把参数分类为 `input`、`output`、`workspace`、`tiling`，再从包根运行：

```bash
python skills/ascendc-kernel-direct-invoke/tools/scaffold_direct_invoke.py \
  --kernel-file <path/to/op_kernel.asc> \
  --out-dir <output/project> \
  --op-name <op_name> \
  --kernel-name <kernel_entry> \
  --io-spec-json <io_spec.json> \
  --soc dav-2201
```

输出为：

```text
<project>/
  CMakeLists.txt
  run.sh
  scaffold_report.json
  op_kernel/<op_name>_kernel.asc
  op_host/main.cpp
  op_host/data_utils.h
  scripts/gen_data.py
  scripts/verify_result.py
  build_sim/op_config.json
```

`build_sim/op_config.json` 由 `scripts/gen_data.py` 生成。若报告为 `needs_io_spec`，补齐缺失字段后用 `--io-spec-json` 重生成。`status == "runnable"` 只说明工程信息齐全，实际可运行还需在 CANN 主机验证：

```bash
cd <project>
bash run.sh build
bash run.sh gen
bash run.sh run
bash run.sh verify
```

构建应得到 `build/<op_name>`，生成应得到 `data/*.bin` 和 `build_sim/op_config.json`，运行与完整 checker 均需成功。技能目录内的 `python tools/scaffold_direct_invoke.py --help` 可检查工具接口。

## IO 说明

自动推断不足时使用以下结构，字段保持工具定义：

```json
{
  "blockdim": 1,
  "dtype": "float32",
  "params": [
    {"name": "inputGM", "kind": "input", "dtype": "float32", "shape": [2048], "file": "input.bin"},
    {"name": "outputGM", "kind": "output", "dtype": "float32", "shape": [2048], "file": "output.bin"},
    {"name": "tilingGM", "kind": "tiling", "size": 40, "file": "tiling.bin"}
  ],
  "tiling_values_u32": [2048, 2048, 2048, 2048, 2048, 256, 256, 8, 0, 0],
  "verification": {"mode": "exists"}
}
```

`kind` 支持 `input`、`output`、`workspace`、`tiling`。`verification.mode=exists` 只检查输出字节存在，不等于数学正确性；可验证数学结果时为每个 output 参数提供 `golden_file`。

## 可选机制采集与模拟

真实 NPU 上可运行 `bash run.sh profile` 获取硬件机制报告。默认输出在仓库根的 `tmp/aprof/...`，可用 `APROF_TMP_ROOT` 或 `APROF_MSPROF_OUTPUT` 改到任务临时目录。该兼容入口默认 `APROF_WARMUP=10`、`APROF_REPEAT=5`；旧 `msprof --application` 在独立 `legacy_run_N` 目录重复采集，受支持时 `APROF_PROFILE_MODE=hw-op` 使用 `msprof op --warm-up --launch-count`。这些机制采集参数**不是当前性能计时协议**；不能由普通 profile 结果宣称候选已接纳。

```bash
bash run.sh sim-build
bash run.sh sim
```

模拟路径使用 `bisheng -fPIC --aicore-only --asc-aicore-lang` 编译、`ld.lld -m aicorelinux -Ttext=0` 链接，再执行 `msprof op simulator --config=./op_config.json`。`ASC_ARCH` 匹配目标，默认 `dav-2201`，兼容 950 环境可设 `dav-3510`。

`sim-build` 应产生 `build_sim/<op_name>_kernel.o`；`sim` 应产生 `tmp/aprof/**/msprof_sim_output/OPPROF_*` 的 `trace.json` 或 `*_instr_exe_*.csv`。硬件 profile 应产生 `tmp/aprof/**/msprof_hw_output/**` 的重复报告目录。模拟性能保持代理标识。手工调试模板为 `references/build_kernel_o.sh`、`references/gen_input_tiling.py`、`references/op_config.template.json`。

## workload tiling-key 接线

多区域实现先有 `ascendc-aprof-parallel-planning` 的有效计划和分发。Host 根据真实 shape/dtype/layout/属性算 uint64 key，启动对应编译实现，或显式传给匹配 kernel 参数。注册算子的 `SetTilingKey`/`TILING_KEY_IS` 示例不能直接假定适用于裸直调。保持参数声明、Host 启动、Kernel 定义一致和通用 fallback；在正确性/计时输出记录真实 group/key/entry，测试完整 case 集、条件等值边界及相邻未见 shape。
