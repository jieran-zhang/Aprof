# FastGelu Reference Direct-Invoke

## 概述

本工程将 [ops-nn FastGelu](https://gitcode.com/cann/ops-nn/tree/master/activation/fast_gelu) 的数学定义落地为 **AProf 可复用的 Ascend C 直调 benchmark**。

- **上游 kernel**：`op_kernel/upstream/fast_gelu_apt.cpp`（ops-nn 原版，依赖 ATV OSS / ElementwiseSch）
- **直调 skeleton**：`op_kernel/fast_gelu_kernel.asc`（按 `ascendc-direct-invoke-template` 的 Vector 分支改写，可独立 bisheng/cmake 编译）
- **公式**：`y = x / (exp(-1.702 * x) + 1)`，与 `fast_gelu_dag.h` / `golden.py` 一致

### 默认参数

| 参数 | 默认值 |
|------|--------|
| shape | `[8, 2048]` |
| dtype | `fp32` |
| blockdim | `1` |
| npu-arch | `dav-3510` (Ascend950) |

## 文件结构

```
fast_gelu/
├── op_kernel/
│   ├── upstream/                  # ops-nn 原版参考（不参与直调编译）
│   ├── fast_gelu_tiling.h
│   └── fast_gelu_kernel.asc
├── op_host/
│   ├── fast_gelu.asc
│   └── data_utils.h
├── scripts/
│   ├── gen_data.py
│   ├── verify_result.py
│   ├── build_kernel_o.sh          # simulator 用 device .o
│   ├── gen_msprof_bins.py
│   ├── profile_sim.sh             # msprof op simulator --config
│   └── profile_hw.sh              # ops-profiling 真机上板采集
├── build_sim/
│   └── op_config.json
├── CMakeLists.txt
├── run.sh
├── metadata.json
└── README.md
```

## 快速开始

### 1. 环境

```bash
cd Aprof
source scripts/setup_env.sh
```

### 2. 编译 + 精度验证（真机 / 带 NPU 环境）

```bash
cd benchmarks/reference_ops/fast_gelu
bash run.sh                  # 默认 M=8 N=2048 fp32 cores=1
bash run.sh 16 4096 fp32 4   # 自定义 shape / 核数
```

### 3. Simulator 性能采集（无 NPU，推荐）

```bash
cd benchmarks/reference_ops/fast_gelu
bash scripts/profile_sim.sh 8 2048 1 10
# 报告目录: msprof_sim_output/OPPROF_*/device0/fast_gelu_kernel/0/simulator/
```

### 4. 真机性能采集（ops-profiling skill）

```bash
cd benchmarks/reference_ops/fast_gelu
bash scripts/profile_hw.sh 8 2048 1 3
# 报告目录: msprof_hw_output/PROF_GROUP_*/
```

## 与上游 ops-nn 的差异

| 项 | ops-nn `fast_gelu_apt.cpp` | 本 benchmark |
|----|---------------------------|--------------|
| 框架 | ElementwiseSch + ATV OSS DAG | 手写 CopyIn/Compute/CopyOut |
| Tiling | `EleBaseTilingDataV2` + workspace | `FastGeluTilingData`（4×uint32） |
| 入口 | `fast_gelu<<<>>>(x,y,workspace,tiling)` | `fast_gelu_kernel<<<>>>(x,y,tiling)` |
| 目的 | 算子仓生产实现 | AProf 直调 + msprof 归因基准 |

详细流程见 `docs/fast_gelu_direct_invoke_workflow.md`。
