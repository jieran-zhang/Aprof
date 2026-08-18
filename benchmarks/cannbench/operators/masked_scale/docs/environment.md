# 环境检查报告

**算子**: masked_scale   **状态**: ✅ 通过   **时间**: 2026-08-11T00:00:00+00:00

## 硬件

| 项 | 值 |
|----|----|
| 芯片型号 | Ascend 910 |
| SocVersion | ASCEND910 |
| 设备数 | 16 |

> NPU Arch / `--npu-arch` 编译参数由 Architect 在 Step 2 通过 `/npu-arch` skill 查得后写入 DESIGN.md；运行时探测结果为 `dav-2201`。

## CANN

- ASCEND_HOME_PATH: `/usr/local/Ascend/cann-9.0.0`
- 版本: `9.0.0`
- CPU 架构目录: `aarch64-linux`

## 编译器与库

- ✅ bisheng: `/usr/local/Ascend/cann-9.0.0/bin/bisheng`
- ✅ kernel_operator.h: `/usr/local/Ascend/cann-9.0.0/aarch64-linux/asc/include/kernel_operator.h`
- ✅ libregister.so: `/usr/local/Ascend/cann-9.0.0/aarch64-linux/lib64/libregister.so`
- ✅ libascendcl.so: `/usr/local/Ascend/cann-9.0.0/aarch64-linux/lib64/libascendcl.so`

## asc-devkit

- ✅ 路径: `/workspace/tmp/Aprof/benchmarks/cannbench/asc-devkit`
- API 文档: 1167 个
- 示例: 242 个
- CMake 配置: ✅

## 检查汇总

- 错误: 0
- 警告: 4

### 警告明细

- ⚠ 两个已安装自定义算子包的 `op_api/lib` 未加入 `LD_LIBRARY_PATH`；本直调工程不依赖这些包。
- ⚠ Kirin9030 simulator 缺少 `libruntime_camodel.so`；目标是真实 Ascend 910，不影响上板。
- ⚠ KirinX90 simulator 缺少 `libruntime_camodel.so`；目标是真实 Ascend 910，不影响上板。
- ⚠ `ASCEND_SLOG_PRINT_TO_STDOUT` 未开启；仅影响日志打屏。

## 采集证据

- `ascendc-env-check/scripts/check_env.sh`：CANN Toolkit、Ops、msprof、cannsim 均通过，无错误。
- `npu-smi info`：真实 Ascend 910 设备健康状态为 OK。
- `ascendc-env-check/scripts/get_npu_arch.py`：输出 `dav-2201`。
