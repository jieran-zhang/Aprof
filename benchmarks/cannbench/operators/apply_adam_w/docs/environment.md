# 环境检查报告

**算子**: apply_adam_w   **状态**: ✅ 通过   **时间**: 2026-08-11T00:00:00+00:00

## 硬件

| 项 | 值 |
|----|----|
| `npu-smi` NPU Name | 9362 |
| `npu-smi` Chip Name | Ascend910（驱动通用标签） |
| 运行时 NPU Arch | dav-2201（对应 910B/910_93 架构族） |
| 物理 NPU ID | 0～7，每卡 2 chips |

> `npu-smi` 的 `Ascend910` 是通用 Chip Name，不能据此套用 DAV_1001 静态映射。权威运行时探测 `get_npu_arch.py` 输出 `dav-2201`，且 `--npu-arch=dav-2201` 二进制已在该设备运行。未把不准确的字面 `SocVersion=ASCEND910` 作为环境证据。

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

- ⚠ 两个已安装自定义算子包的 `op_api/lib` 未加入 `LD_LIBRARY_PATH`；本直调工程使用 CANN ACL/ASC 库，不依赖这些包。
- ⚠ Kirin9030 simulator 缺少 `libruntime_camodel.so`；目标是真实 Ascend 910，不影响上板。
- ⚠ KirinX90 simulator 缺少 `libruntime_camodel.so`；目标是真实 Ascend 910，不影响上板。
- ⚠ `ASCEND_SLOG_PRINT_TO_STDOUT` 未开启；仅影响日志打屏。

## 采集证据

- `ascendc-env-check/scripts/check_env.sh`：CANN Toolkit、Ops、msprof、cannsim 均通过，无错误。
- `npu-smi info`：真实 Ascend 910 设备健康状态为 OK。
- `ascendc-env-check/scripts/get_npu_arch.py`：输出 `dav-2201`。
