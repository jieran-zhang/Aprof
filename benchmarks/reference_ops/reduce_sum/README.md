# ReduceSum Skeleton

## 概述

本工程是一个最小 Ascend C `ReduceSum` skeleton。它对 FP32 输入张量 `[M, N]` 沿 `axis=1` 求和，输出 `[M]`。

kernel 的核心 UB 内归约实现来自 `op_kernel/reduce_common.h`，外层 skeleton 只负责 GM/UB 搬运、tiling、launch 和结果写回。

### 功能特性

- **数据类型**：当前仅支持 FP32
- **核心实现**：使用 `reduce_common.h` 中的 `ReduceSumHalfInterval`
- **多核切分**：单次 launch，多 block 按 M 维切分
- **UB Tiling**：按 N 维分 chunk，每个 chunk 在 UB 内归约后累加 partial sum
- **边界处理**：支持尾行和尾列

## 文件结构

```
ReduceSum_template/
├── op_kernel/
│   ├── reduce_common.h            # UB 内 ReduceSum helper
│   ├── reduce_sum_tiling.h       # Tiling 结构体（host/kernel 共用）
│   └── reduce_sum_kernel.asc     # Device 侧 Kernel 实现
├── op_host/
│   ├── reduce_sum.cpp            # Host 侧直调入口
│   └── data_utils.h              # 二进制文件读写工具
├── scripts/
│   ├── gen_data.py               # 生成输入数据 + golden
│   └── verify_result.py          # 精度验证
├── CMakeLists.txt                # 编译配置
├── run.sh                        # 一键编译运行验证
└── README.md                     # 本文件
```

## 快速开始

### 前提

```bash
source ${ASCEND_HOME_PATH}/set_env.sh
```

### 一键运行

```bash
# 默认：M=8, N=2048, FP32, 单核
bash run.sh

# 自定义参数
bash run.sh 16 4096 fp32 4      # M=16, N=4096, FP32, 4核

# 跳过编译（调试阶段）
bash run.sh --skip-build 8 2048 fp32 1
```

### 手动分步执行

```bash
# 1. 编译
mkdir -p build && cd build && cmake .. && make -j
cd ..

# 2. 生成数据
python3 scripts/gen_data.py 8 2048 fp32

# 3. 运行
cd build && ./reduce_sum 8 2048 fp32 1 && cd ..

# 4. 验证
python3 scripts/verify_result.py fp32
```

## Tiling 设计

### 多核切分

```
输入 [M, N]
  │
  ├── Core 0: rows [0, perCoreM)
  ├── Core 1: rows [perCoreM, 2*perCoreM)
  └── Core k: rows [k*perCoreM, min((k+1)*perCoreM, M))
```

### UB Tiling（单核内）

对于每一行，按列方向分 chunk 归约：

```
Row i (N elements)
  │
  ├── Chunk 0: columns [0, perLoopN)          → ReduceSumHalfInterval → partial_0
  ├── Chunk 1: columns [perLoopN, 2*perLoopN) → ReduceSumHalfInterval → partial_1
  └── Chunk k: columns [k*perLoopN, N)        → ReduceSum → partial_k
                                                           ↓
                                              accum = Σ partial_j
                                                           ↓
                                              output[i] = accum
```

### Buffer 规划

| Buffer | 大小 | 用途 |
|--------|------|------|
| `inputBuf` | `perLoopNAligned × 4` | 输入 chunk，作为 `ReduceSumHalfInterval` 的原地归约 buffer |

## TODO / 已知限制

- [ ] 仅支持 FP32、2D 输入沿 axis=1 归约。
- [ ] FP16 需要在 UB 内显式 Cast 到 FP32 后再复用 `reduce_common.h`。
- [ ] PyTorch 对接层（`op_extension/`）未实现，见 CMakeLists.txt 注释区块。
- [ ] L2 缓存优化和 double buffer 未启用。

## 修改指南（搜索 `[MODIFY]`）

- `reduce_sum_tiling.h`：新增 axis 维度、新增 dtype 时扩展字段。
- `reduce_sum_kernel.asc`：新增归约轴、新增 dtype 特化。
- `reduce_sum.cpp`（host）：新增 dtype 分支、新增 kernel 入口映射。
- `CMakeLists.txt`：切换架构 `-DNPU_ARCH=DAV_2201`，新增 PyTorch 扩展 target。
- `run.sh`：无需修改，参数透传。
