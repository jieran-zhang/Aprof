# FastGelu Benchmark 参数速查

## 默认运行参数

| 参数 | 值 | 说明 |
|------|-----|------|
| M | 8 | 行数 |
| N | 2048 | 列数 |
| totalLength | 16384 | M×N |
| dtype | fp32 | 当前 skeleton 仅支持 FP32 |
| blockdim | 1 | launch 核数 |
| TILE_LENGTH | 4096 | UB 单次处理元素数 |
| FAST_GELU_ATTR | -1.702 | 与 ops-nn 一致 |
| npu-arch | dav-3510 | Ascend950 simulator / 编译 |

## 命令速查

```bash
# 精度闭环
bash run.sh 8 2048 fp32 1

# simulator profiling
bash scripts/profile_sim.sh 8 2048 1 10

# 真机 profiling（需 NPU）
bash scripts/profile_hw.sh 8 2048 1 3
```

## Tiling 二进制布局（simulator）

`tiling.bin` = `struct.pack("4I", totalLength, numPerCore, tailNumLastCore, blockNum)`

与 `op_kernel/fast_gelu_tiling.h` 字段顺序一致。

## 文件产物

| 路径 | 用途 |
|------|------|
| `data/input.bin` | 输入 |
| `data/golden.bin` | NumPy golden |
| `build/output/output.bin` | kernel 输出 |
| `build_sim/fast_gelu_kernel.o` | simulator device ELF |
| `msprof_sim_output/OPPROF_*` | simulator 性能报告 |
| `msprof_hw_output/PROF_GROUP_*` | 真机 msprof 报告 |
