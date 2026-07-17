# 三算子问题注入与 msprof 采集流程

> **2026-07 布局更新**：`benchmarks/aprof_injected_ops` 已对齐 `aprof_benchmark/fast_gelu`：
> `direct_invoke_baseline` + `operators/op_XXXX` + `.ground_truth/`。
> Agent 可见面说明见 `benchmarks/aprof_injected_ops/README.md`。
> 下文仍保留早期 `inject_*` / bisheng 直跑设计记录，新开发请以新布局与 `common/run_direct_invoke.sh` 为准。

本文记录在 `fast_gelu` 注入流程（见 `docs/fast_gelu_inject_workflow.md`）之上，对以下三个算子复用同一注入模板（`benchmarks/aprof_injected_ops/common/`）落地的设计、变体矩阵与远程真机采集入口。

| 算子 | 核心逻辑 | 注入"靶点" | 适合注入的问题类型 |
|------|----------|-----------|--------------------|
| `gelu_mul` | 数据拆分 + 激活 + 乘法（多阶段流水线） | vector 阶段间流水 overlap | 流水并行不足、AI Core 利用率低 |
| `fast_gelu_grad` | 复杂反向梯度计算（计算图 + 控制流） | exp 重复计算、`(1+e)^2` 拆解 | API 与算法实现低效 |
| `foreach_norm` | 张量列表循环执行 L2 范数 | tile 切分 + GM→UB 搬运 | Tiling 不合理、数据搬运瓶颈 |

## 1. 目录结构

每个算子沿用 `fast_gelu` 的 `baseline + 多 inject variant` 布局，共享 `common/inject_run.sh` 与 `common/inject_gen_data.py`。

```
benchmarks/aprof_injected_ops/
├── common/                                   # 共享脚本（已扩展 3 个 golden + foreach 生成器）
│   ├── inject_run.sh
│   ├── inject_gen_data.py                    # +gelu_mul_golden / +fast_gelu_grad_golden / +foreach_norm_golden / +main_foreach_norm
│   └── parse_hw_op_summary.py
├── gelu_mul/
│   ├── baseline/                             # 多阶段流水正常 overlap
│   ├── inject_blockdim/      → blockdim_too_small
│   ├── inject_pipe_break/    → pipeline_parallel_insufficient   ← 靶点①
│   └── inject_tilelen_small/ → tileLength_too_small
├── fast_gelu_grad/
│   ├── baseline/                             # 反向梯度单次 exp
│   ├── inject_blockdim/      → blockdim_too_small
│   ├── inject_api_inefficient/ → api_algorithm_inefficient      ← 靶点②
│   └── inject_dynshape/      → fixed_tiling_dynamic_shape
└── foreach_norm/
    ├── baseline/                             # N 个张量按 tile=128 规约
    ├── inject_tiling_unreasonable/    → tiling_unreasonable          ← 靶点③a
    ├── inject_data_move_bottleneck/   → data_move_bottleneck         ← 靶点③b
    └── inject_blockdim/               → blockdim_too_small
```

每个 variant 通过 `scripts/gen_data.py` 旋钮（blockdim / tile_length / num_tensors / variant_flags）+ `op_kernel/aprof_variant_config.h` 编译期开关注入**单一问题**，ground-truth 写在 `metadata.json.injected_label`。

## 2. 注入旋钮对照

### 2.1 gelu_mul（流水并行 / AI Core 利用率）

| Variant | injected_label | output_elements | blockdim | tile_length | APROF_INJECT_PIPE_BREAK | 注入意图 |
|---------|----------------|-----------------|----------|-------------|-------------------------|----------|
| baseline | baseline | 2048 | 4 | 256 | 0 | load→gelu→mul→store 正常流水 |
| inject_blockdim | blockdim_too_small | 2048 | 1 | 256 | 0 | 单核承载全部 workload，AI Core 利用率低 |
| inject_pipe_break | pipeline_parallel_insufficient | 2048 | 4 | 256 | **1** | 每个 vector 阶段间插 `PipeBarrier<PIPE_ALL>`，破坏 MTE2→V→MTE3 overlap |
| inject_tilelen_small | tileLength_too_small | 2048 | 4 | **16** | 0 | tile 数 8→128，循环开销主导，流水并行不足 |

kernel：`gelu_mul_kernel.asc`，注入点 `MaybePipeBreak()` 由 `APROF_INJECT_PIPE_BREAK` 控制。

### 2.2 fast_gelu_grad（API / 算法低效）

| Variant | injected_label | output_elements | blockdim | tile_length | APROF_INJECT_API_RECOMPUTE | APROF_INJECT_DYNSHAPE |
|---------|----------------|-----------------|----------|-------------|----------------------------|-----------------------|
| baseline | baseline | 2048 | 4 | 256 | 0 | 0 |
| inject_blockdim | blockdim_too_small | 2048 | 1 | 256 | 0 | 0 |
| inject_api_inefficient | api_algorithm_inefficient | 2048 | 4 | 256 | **1** | 0 |
| inject_dynshape | fixed_tiling_dynamic_shape | 640 | 1 | 640 | 0 | **1** |

`inject_api_inefficient` 的两处低效：
1. **重复计算 exp**：`exp(-1.702*x)` 在分母分支算一次后，分子分支再算一次（`emx2Local`），浪费一次 Exp + 一次 Muls。
2. **`(1+emx)^2` 拆解**：用 `1 + 2*emx + emx*emx`（Adds+Mul+Adds+Adds 共 4 op）替代 baseline 的一次 `Mul`。

数学公式（`grad = x` 作为 benchmark 简化）：

```
emx      = exp(-1.702 * x)
one_plus = 1 + emx
denom    = one_plus * one_plus
numer    = one_plus - emx * (1.702 * x)
dydx     = numer / denom
dx       = x * dydx
```

### 2.3 foreach_norm（Tiling / 数据搬运）

tiling 结构 `AprofForeachTilingData`（9 个 uint32 = 36 字节，与 `main_foreach_norm` 对齐）：

```c
struct AprofForeachTilingData {
    uint32_t numTensors, tensorLength, tileLength, tileLengthAligned,
             tensorsPerCore, inputStride, outputStride, blockdim, variantFlags;
};
```

| Variant | injected_label | num_tensors | tensor_length | tile_length | blockdim | APROF_INJECT_DATA_MOVE | 注入意图 |
|---------|----------------|-------------|---------------|-------------|----------|-------------------------|----------|
| baseline | baseline | 32 | 256 | 128 | 4 | 0 | N 个张量按 tile=128 规约，搬运与计算平衡 |
| inject_tiling_unreasonable | tiling_unreasonable | 32 | 256 | **8** | 4 | 0 | tile=8 使规约切 32 次/tensor，规约开销主导 |
| inject_data_move_bottleneck | data_move_bottleneck | 32 | 256 | 128 | 4 | **1** | 每个 tile 在规约前多一次 GM→UB 重复搬运，MTE2 带宽翻倍 |
| inject_blockdim | blockdim_too_small | 32 | 256 | 128 | **1** | 0 | 单核串行处理全部 N 个张量，循环批处理吞吐低 |

kernel：`foreach_norm_kernel.asc`，每 core 处理 `tensorsPerCore` 个张量，每个张量按 tile 循环：`DataCopy → Mul(x,x) → ReduceSum → Add(acc) → Sqrt → DataCopy(out)`。

## 3. 本地构建（需 CANN + NPU/simulator）

复用 `fast_gelu` 的 `inject_run.sh`，每个 case 仓库根目录的 `run.sh` 已设置 `OP_NAME`：

```bash
cd benchmarks/aprof_injected_ops/gelu_mul/inject_pipe_break
export ASCEND_HOME_PATH=...
export ASC_ARCH=dav-3510          # simulator
# 或 export ASC_ARCH_HW=dav-2201  # 真机
bash run.sh all                   # gen + build_sim + msprof op simulator --config
bash run.sh all_hw                # gen + build(dav-2201) + msprof op --config
```

> 注意：`foreach_norm` 的 `op_config.json` 的 `tiling_data_size=36`（与 vector case 的 40 不同），由 `main_foreach_norm` 自动生成。

## 4. 远程一键采集（910B 真机）

新增统一 runner，覆盖三个算子全部变体：

```powershell
# 1) 复制 example 为本地 gitignore 副本
Copy-Item scripts\run_remote_new_ops_inject_hw.example.py `
            scripts\run_remote_new_ops_inject_hw.py

# 2) 设置远程凭据（与 fast_gelu hw 流程同套环境变量）
$env:APROF_REMOTE_HOST="xeon6.pku-dasys.cn"
$env:APROF_REMOTE_USER="u2300013210"
$env:APROF_REMOTE_PASS="<你的密码>"
$env:APROF_REMOTE_ROOT="/home/u2300013210/aprof_new_ops_inject"   # 可选
$env:ASC_ARCH_HW="dav-2201"

# 3) 跑全部三算子
python scripts\run_remote_new_ops_inject_hw.py

# 或只跑某算子
$env:INJECT_OPS="gelu_mul,foreach_norm"
python scripts\run_remote_new_ops_inject_hw.py

# 或单算子只跑某 case
$env:INJECT_OPS="gelu_mul"
$env:INJECT_CASES_gelu_mul="baseline,inject_pipe_break"
python scripts\run_remote_new_ops_inject_hw.py
```

产物落点：

| 路径 | 内容 |
|------|------|
| `benchmarks/aprof_injected_ops/<op>/remote_inject_out/results_hw.json` | 单算子结果（每个 case 的 `task_duration_us`、`oprof_id`、`hw_csv`） |
| `benchmarks/aprof_injected_ops/<op>/remote_inject_out/<case>_hw/.../op_summary_*.csv` | 已下载的 hw CSV（Task Duration / aic metrics） |
| `benchmarks/aprof_injected_ops/new_ops_inject_results.json` | 三算子合并汇总 |
| 远程：`/home/<user>/aprof_new_ops_inject/<op>/<case>/msprof_hw_output/` | 完整 msprof 产物（`PROF_GROUP_*` / `OPPROF_*`） |

## 5. 实测性能对比（910B 真机，dav-2201，msprof op --config mode=onboard）

来源：`benchmarks/aprof_injected_ops/<op>/remote_inject_out/results_hw.json`（每 case 3 次 warmup + 1 次 launch）。

### 5.1 gelu_mul

| Variant | label | Task Duration(us) | 相对 baseline |
|---------|-------|-------------------|---------------|
| baseline | baseline | **2.22** | 1.00× |
| inject_blockdim | blockdim_too_small | 5.34 | 2.40× |
| inject_pipe_break | pipeline_parallel_insufficient | 2.38 | 1.07× |
| inject_tilelen_small | tileLength_too_small | **9.02** | **4.06×** |

```
baseline               ████                          2.22 μs
inject_blockdim        █████████                     5.34 μs
inject_pipe_break      ████                          2.38 μs
inject_tilelen_small   ████████████████              9.02 μs
```

**解读**：
1. `tileLength_too_small` 影响最大（4.06×）：tile 从 256→16 使单核循环 8→128 次，循环/同步开销主导，符合预期。
2. `blockdim_too_small` 2.40×：4 核 → 1 核，单核承载 4 倍 workload，AI Core 利用率下降。
3. **`inject_pipe_break` 仅 1.07× — 实测小于预期**：因 baseline kernel 已在每个 vector op 后插 `PipeBarrier<PIPE_V>()`，MTE2→V→MTE3 的跨阶段 overlap 本就有限；再加 `PIPE_ALL` 屏障边际影响小。若要放大流水打断效果，应改为**移除** baseline 的 V 屏障 + 在 inject 版只加 `PIPE_ALL`，或增大 tile 让 overlap 占比更高。

### 5.2 fast_gelu_grad

| Variant | label | Task Duration(us) | 相对 baseline |
|---------|-------|-------------------|---------------|
| baseline | baseline | **2.36** | 1.00× |
| inject_blockdim | blockdim_too_small | 6.02 | 2.55× |
| inject_api_inefficient | api_algorithm_inefficient | 2.54 | 1.08× |
| inject_dynshape | fixed_tiling_dynamic_shape | 3.42 | 1.45× |

```
baseline                ████                          2.36 μs
inject_blockdim         ██████████                    6.02 μs
inject_api_inefficient  ████                          2.54 μs
inject_dynshape         ██████                        3.42 μs
```

**解读**：
1. `blockdim_too_small` 2.55×：单核承载全部反向梯度，多核并行缺失，最大开销来源。
2. **`api_algorithm_inefficient` 仅 1.08× — 实测小于预期**：重算 exp + `(1+e)^2` 拆 4 op 仅多 ~0.18 μs。原因：vector op 在该 tile 规模（256 elem）下绝对耗时本就很小，且 V 流水线下两条 `Muls/Exp` 可被指令级并行吸收。要放大该反模式，需把 tile 加大到接近 UB 上限，使 V 计算成为瓶颈。
3. `inject_dynshape` 1.45×：规模缩到 640 elem + 空 core 路径插 `PIPE_ALL`，绝对值低但相对 baseline 有可见开销。

### 5.3 foreach_norm

| Variant | label | Task Duration(us) | 相对 baseline |
|---------|-------|-------------------|---------------|
| baseline | baseline | **8.20** | 1.00× |
| inject_tiling_unreasonable | tiling_unreasonable | **54.60** | **6.66×** |
| inject_data_move_bottleneck | data_move_bottleneck | 10.26 | 1.25× |
| inject_blockdim | blockdim_too_small | 28.32 | 3.45× |

```
baseline                     ████                          8.20 μs
inject_tiling_unreasonable   ██████████████████████      54.60 μs
inject_data_move_bottleneck  ████                         10.26 μs
inject_blockdim               ███████████                 28.32 μs
```

**解读**：
1. **`tiling_unreasonable` 6.66× — 最显著**：tile 从 128→8 使每个张量规约切 2→32 次，`ReduceSum` 启动/收尾开销 ×16 张量被放大，符合"Tiling 不合理"靶点预期。
2. `blockdim_too_small` 3.45×：4 核 → 1 核串行处理 32 张量，循环批处理吞吐下降。
3. `data_move_bottleneck` 1.25×：每 tile 多一次 GM→UB 重复搬运，MTE2 带宽翻倍但被多核 + 流水掩盖部分影响，绝对开销 ~2 μs。

### 5.4 三算子靶点命中率汇总

| 算子 | 主靶点 inject variant | 倍率 | 是否最显著 case |
|------|----------------------|------|-----------------|
| gelu_mul | inject_tilelen_small（流水并行不足） | 4.06× | ✅ 该算子内最大 |
| gelu_mul | inject_pipe_break（流水并行不足） | 1.07× | ❌ 实测不显著，见 5.1 解读 |
| fast_gelu_grad | inject_api_inefficient（API/算法低效） | 1.08× | ❌ 实测不显著，见 5.2 解读 |
| foreach_norm | inject_tiling_unreasonable（Tiling 不合理） | **6.66×** | ✅ 该算子内最大 |
| foreach_norm | inject_data_move_bottleneck（数据搬运瓶颈） | 1.25× | ⚠️ 可见但不主导 |

**总评**：tiling 类反模式（tile 过小）在三个算子中都表现为最显著的开销源；blockdim=1 普遍带来 2-3.5× 退化；流水/API 类反模式在当前小 tile 规模下被 V 流水掩盖，需放大 tile 或重构 inject 才能突显——这与 fast_gelu sim 报告中 `tileLength_too_small` 25.7× 的结论一致：**循环/同步开销主导是小算子注入中最稳定的反模式信号**。

## 6. 注意事项

1. **架构一致**：远程 910B 真机用 `dav-2201` 编译 + `msprof op --config`（`mode=onboard`）；如走 simulator 用 `dav-3510`。
2. **`ReduceSum` 签名**：`foreach_norm_kernel.asc` 使用 `ReduceSum<float>(dst, src, work, calCount)`，CANN 9.0 已验证；如远程版本签名不同，需在 kernel 内调整该一行调用。
3. **tiling_data_size**：vector case 40 字节、foreach case 36 字节，已在各自 `gen_data.py` 与 `op_config.json` 中对齐。
4. **ground-truth**：每个 case 的 `metadata.json.injected_label` 与 `injected_problem` 写明注入意图，可供 `/ascendc-aprof-diagnosis` 闭环对齐。
5. **gitignore**：`scripts/run_remote_new_ops_inject_hw.py`（无 `.example` 后缀）已加入 `.gitignore`，存放本地凭据副本。

## 7. 相关文档

- `docs/fast_gelu_inject_workflow.md`：原始注入流程与 sim 产物说明。
- `benchmarks/aprof_injected_ops/fast_gelu_inject_report.md`：fast_gelu 注入前/后对比与 msprof 耗时解读。
- `skills/aprof/benchmark/ascendc-aprof-inject-problems/`：注入 skill。
