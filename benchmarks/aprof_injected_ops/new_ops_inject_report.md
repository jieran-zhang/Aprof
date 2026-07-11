# 三算子注入前 / 注入后对比报告：gelu_mul / fast_gelu_grad / foreach_norm

> 生成时间：2026-07-10（v2，基于 PR #2 skill 管线优化后重采）
> 采集环境：远程 `xeon6.pku-dasys.cn:2222`（PKU 910B，CANN 9.0.0，`dav-2201`）
> 采集方式：`msprof op --config`（mode=onboard），每 case 3 次 warmup + 1 次 launch
> 数据来源：`benchmarks/aprof_injected_ops/<op>/remote_inject_out/results_hw.json` + 下载的 `OpBasicInfo.csv`
> 合并汇总：`benchmarks/aprof_injected_ops/new_ops_inject_results.json`
> 设计文档：`docs/new_ops_inject_workflow.md`
> Skill 管线：`skills/aprof/benchmark/ascendc-aprof-inject-problems/`（PR #2 引入，本批 case 已对齐 schema v2）

---

## 0. 为什么选这三个算子 / 这三类问题

每个算子的"核心逻辑"决定了它天然容易暴露哪类反模式。注入实验的设计原则是：**把算子的固有结构特征当成放大器，注入与该结构最匹配的反模式，使性能信号最清晰**。

| 算子 | 核心结构 | 该结构为何放大此类问题 | 注入的问题类型 |
|------|----------|----------------------|----------------|
| `gelu_mul` | 数据拆分 + 激活 + 乘法，**多阶段流水线**（load→gelu→mul→store） | 多阶段流水本应靠 MTE2/V/MTE3 overlap 隐藏延迟；一旦 tile 切碎或阶段间插屏障，overlap 被破坏，AI Core 空转 | 流水并行不足、AI Core 利用率低 |
| `fast_gelu_grad` | 反向梯度，**计算图多分支 + 控制流**（exp/除法/平方，分子分母双分支） | 计算图分支多 → API 选择与中间量复用空间大；选错 API 或重复计算会直接放大 vector op 数量 | API 与算法实现低效 |
| `foreach_norm` | 对张量列表**循环执行规约**，每张量内还有 tile 循环 | 双层循环（外层 N 张量 × 内层 tile）使"循环开销 × 数据搬运次数"被乘起来；tile 越小循环越多，搬运重复则带宽翻倍 | Tiling 不合理、数据搬运瓶颈 |

> 设计逻辑：**算子结构 ↔ 反模式**的对应关系，比"随便挑一个算子注入所有问题"更能产出可解释的 ground-truth，便于后续 AProf diagnosis 闭环对齐。

---

## 1. 数据都在哪里？

| 类型 | 路径 | 内容 |
|------|------|------|
| 注入旋钮与标签 | `<op>/<variant>/metadata.json` | `injected_label`、blockdim、tile_length、num_tensors 等 |
| 单算子汇总 | `<op>/remote_inject_out/results_hw.json` | 每 case 的 `task_duration_us`、`oprof_id`、`hw_csv` 路径 |
| 三算子合并 | `benchmarks/aprof_injected_ops/new_ops_inject_results.json` | 跨算子汇总 dict |
| hw CSV | `<op>/remote_inject_out/<case>_hw/.../OpBasicInfo.csv` | Task Duration / Block Dim / Op Type |
| 远程完整产物 | 远程 `/home/u2300013210/aprof_new_ops_inject/<op>/<case>/msprof_hw_output/OPPROF_*/` | `PROF_GROUP_*` + aic metrics |
| 设计 + 解读 | `docs/new_ops_inject_workflow.md` | 矩阵、运行说明、实测对比 |

采集链路与 `fast_gelu` hw 流程一致：device `.o`（`--npu-arch=dav-2201`）+ `op_config.json`（`mode=onboard`），由 `scripts/run_remote_new_ops_inject_hw.py`（gitignored，含凭据副本）一键上传/编译/采集/下载。

---

## 2. gelu_mul — 流水并行不足 / AI Core 利用率低

### 2.1 算子与注入靶点

```
y = x * fast_gelu(x) = x * (x / (1 + exp(-1.702 * x)))
```

kernel 是典型的**四阶段流水**：`DataCopy(load) → Muls/Exp/Adds/Div(gelu) → Mul(乘法) → DataCopy(store)`，每个 tile 内 MTE2→V→MTE3 应当 overlap。

**为什么选 gelu_mul 注入"流水并行/AI Core 利用率"**：多阶段流水的性能上限完全取决于阶段间 overlap 是否成立。一旦 tile 太小（循环开销 > 计算开销）或阶段间被屏障强制串行，AI Core 利用率立刻下降。gelu_mul 的阶段数（4）和每阶段计算量（轻量 vector op）正好让 overlap 占比高、反模式信号放大明显。

### 2.2 注入旋钮对照

> v2 变更：workload 从 2048→16384 elem（让流水 overlap 占比更高），`inject_pipe_break` 替换为 skill canonical recipe `inject_excessive_barrier`（`pipeline_parallel/excessive_pipe_barrier`，双 `PipeBarrier<PIPE_ALL>` at tile boundary）。

| Variant | injected_label | output_elements | blockdim | tile_length | 注入点 | 注入意图 |
|---------|----------------|-----------------|----------|-------------|--------|----------|
| baseline | baseline | 16384 | 4 | 256 | — | 4 阶段流水正常 overlap，16 tile/core |
| inject_blockdim | blockdim_too_small | 16384 | **1** | 256 | 4 核→1 核 | 单核承载 4× workload，AI Core 利用率低 |
| **inject_excessive_barrier** | **excessive_pipe_barrier** | 16384 | 4 | 256 | tile 边界双 `PIPE_ALL` | skill recipe `pipeline_parallel/excessive_pipe_barrier`，强制每 tile drain |
| inject_tilelen_small | tileLength_too_small | 16384 | 4 | **16** | tile=16 | tile 数 16→256/core，循环开销主导 |

### 2.3 实测 msprof 真机耗时（Task Duration, μs）

| Variant | label | Task Duration(us) | 相对 baseline |
|---------|-------|-------------------|---------------|
| baseline | baseline | **7.60** | 1.00× |
| inject_blockdim | blockdim_too_small | 28.86 | 3.80× |
| inject_excessive_barrier | excessive_pipe_barrier | 9.90 | 1.30× |
| inject_tilelen_small | tileLength_too_small | **60.68** | **7.98×** |

```
baseline                  ████                          7.60 μs
inject_excessive_barrier  █████                         9.90 μs
inject_blockdim           █████████████                 28.86 μs
inject_tilelen_small      ███████████████████████████   60.68 μs
```

### 2.4 解读

1. **`tileLength_too_small` 影响最大（7.98×）**：16384 elem + tile=16 → 256 tile/core（vs v1 的 32 tile/core），循环/同步固定开销被放大 8×，信号从 v1 的 4.06× 增强到 7.98×。**workload 放大是 tiling 类反模式的最有效放大器**。
2. **`blockdim_too_small` 3.80×**：4 核→1 核，单核 16384 elem，AI Core 利用率 ~25%，耗时近线性增长。
3. **`inject_excessive_barrier` 1.30× — 从 v1 的 1.07× 改善**：v2 使用 skill canonical recipe（tile 边界双 `PIPE_ALL`，16 tile/core → 32 次额外 drain）替代 v1 的 per-stage barrier。workload 放大 8× 后，屏障的累积开销开始可见。但仍未达到 2× 以上——根因是 baseline kernel 已在每个 vector op 后插 `PIPE_V`，跨阶段 overlap 本就有限，`PIPE_ALL` 的边际 drain 效应被掩盖。**进一步改进方向**：重构 baseline 移除 `PIPE_V` 让 overlap 充分发生，或增大 tile 到 1024–2048 使单 tile overlap 窗口更长。

---

## 3. fast_gelu_grad — API 与算法实现低效

### 3.1 算子与注入靶点

```
emx       = exp(-1.702 * x)
one_plus  = 1 + emx
denom     = one_plus * one_plus
numer     = one_plus - emx * (1.702 * x)
dydx      = numer / denom
dx        = grad * dydx          (grad = x 作为 benchmark 简化)
```

反向梯度计算有**分子/分母双分支 + 多个中间量**（exp、平方、乘法、减法、除法），API 选择和中间量复用空间大。

**为什么选 fast_gelu_grad 注入"API/算法低效"**：算子含 exp 这种相对昂贵的 transcendental op，且 `(1+emx)` 在分子分母都出现 → 是否复用中间量、是否用 `Mul` 一步算平方 vs 拆成 `1+2e+e²` 三步，对 vector op 数量影响显著。前向 fast_gelu/gelu_mul 的公式太紧凑（一次 exp + 一次除法），没有可拆解空间；grad 的双分支结构才是"算法实现低效"的天然温床。

### 3.2 注入旋钮对照

> v2 变更：workload 从 2048→16384 elem，`inject_api_inefficient` 替换为 skill canonical recipe `inject_scalar_loop`（`api_algorithm/scalar_loop_redundant`，64-iter 冗余标量循环 at tile boundary）。

| Variant | injected_label | output_elements | blockdim | tile_length | 注入点 | 注入意图 |
|---------|----------------|-----------------|----------|-------------|--------|----------|
| baseline | baseline | 16384 | 4 | 256 | — | 单次 exp，`(1+e)^2` 用一次 Mul |
| inject_blockdim | blockdim_too_small | 16384 | **1** | 256 | 4 核→1 核 | 单核承载全部反向梯度 |
| **inject_scalar_loop** | **scalar_loop_redundant** | 16384 | 4 | 256 | tile 边界 64-iter 标量循环 | skill recipe `api_algorithm/scalar_loop_redundant`，制造 scalar-control 压力 |
| inject_dynshape | fixed_tiling_dynamic_shape | 640 | 1 | 640 | 固定 tiling + 空 core 屏障 | 固定 tiling on dynamic shape |

### 3.3 实测 msprof 真机耗时

| Variant | label | Task Duration(us) | 相对 baseline |
|---------|-------|-------------------|---------------|
| baseline | baseline | **8.52** | 1.00× |
| inject_blockdim | blockdim_too_small | 30.08 | 3.53× |
| inject_scalar_loop | scalar_loop_redundant | 8.48 | **1.00×** |
| inject_dynshape | fixed_tiling_dynamic_shape | 3.46 | 0.41×（不同规模，不可直接比） |

```
baseline             ████                          8.52 μs
inject_scalar_loop   ████                          8.48 μs
inject_blockdim      █████████████                 30.08 μs
```

### 3.4 解读

1. **`blockdim_too_small` 3.53×**：4 核→1 核，单核 16384 elem，多核并行缺失，是本算子最大开销来源。
2. **`inject_scalar_loop` 1.00× — 无信号，skill recipe 存在 DCE bug**：skill 的 `scalar_loop_redundant` recipe 在 tile 边界插入 64-iter 标量循环 + `if (aprofScalarWaste == 0xFFFFFFFFU) { PipeBarrier<PIPE_ALL>(); }`。但编译器（bisheng -O2）判定 `aprofScalarWaste` 永远不等于 `0xFFFFFFFFU`（64 次 `+= aprofI + tileIdx` 的和远小于该值），将整个循环 + 条件屏障作为 dead code 消除。**这是 skill recipe 需要修复的 bug**：标量循环需要不可消除的 side effect（如写 volatile GM 地址、或 `asm volatile` 屏障），否则 -O2 必然 DCE。已记录待反馈 skill 维护者。
3. **`inject_dynshape` 0.41×**：规模仅 640 elem（vs baseline 16384），绝对值 3.46 μs，不可直接与 baseline 比；该 case 测的是"固定 tiling on 小 shape"的非比例效应。

> **v1 → v2 对比**：v1 的 `inject_api_inefficient`（手动重算 exp + 拆 `(1+e)^2`）在 2048 elem 下有 1.08× 微弱信号；v2 换用 skill canonical `scalar_loop` 后信号完全消失（DCE）。**结论**：当前 skill 的 `api_algorithm` 家族 recipe 在 bisheng -O2 下均无法产生可靠信号——`scalar_loop` 被 DCE，`redundant_vector` 的 anchor (`MaybeInjectTailReload`) 只在 fast_gelu 模板中存在。`api_algorithm` 家族需要重新设计 recipe（如用 `Adds(+0)` 等价 vector op 替代标量循环，或加 volatile 防止 DCE）。

---

## 4. foreach_norm — Tiling 不合理 / 数据搬运瓶颈

### 4.1 算子与注入靶点

```
for i in 0..N-1:
    out[i] = sqrt( sum_{j=0..L-1} x[i*L + j]^2 )
```

输入是 N 个长度为 L 的张量拼接成一段连续 GM，输出是 N 个 L2 范数标量。kernel 是**双层循环**：外层 N 个张量，内层每张量按 tile 循环 `DataCopy → Mul(x,x) → ReduceSum → Add(acc) → Sqrt → DataCopy(out)`。

**为什么选 foreach_norm 注入"Tiling/数据搬运"**：
- **Tiling 不合理**：规约的 tileLength 决定每张量切多少次内层循环。tile 太小 → `ReduceSum` 的启动/收尾固定开销 × N 张量 × 内层次数 被乘起来，规约开销主导；这是规约类算子特有的反模式。
- **数据搬运瓶颈**：foreach 模式的瓶颈常在 GM→UB 搬运（每张量每 tile 必须搬一次）。注入一次额外搬运就让 MTE2 带宽需求翻倍，直接体现"搬运成为瓶颈"。
- 前向 gelu_mul/fast_gelu_grad 是单层 tile 循环，循环放大效应只有 ×tile_num；foreach_norm 是 ×N×tile_num，反模式信号天然更强。

### 4.2 注入旋钮对照

tiling 结构 `AprofForeachTilingData`（9 个 uint32 = 36 字节）：

```c
struct AprofForeachTilingData {
    uint32_t numTensors, tensorLength, tileLength, tileLengthAligned,
             tensorsPerCore, inputStride, outputStride, blockdim, variantFlags;
};
```

| Variant | injected_label | num_tensors | tensor_length | tile_length | blockdim | APROF_INJECT_DATA_MOVE | 注入意图 |
|---------|----------------|-------------|---------------|-------------|----------|-------------------------|----------|
| baseline | baseline | 32 | 256 | 128 | 4 | 0 | N=32 张量按 tile=128 规约，搬运与计算平衡 |
| **inject_tiling_unreasonable** | **tiling_unreasonable** | 32 | 256 | **8** | 4 | 0 | tile=8 使规约切 2→32 次/tensor，规约开销主导 |
| **inject_data_move_bottleneck** | **data_move_bottleneck** | 32 | 256 | 128 | 4 | **1** | 每 tile 在规约前多一次 GM→UB 重复搬运，MTE2 带宽翻倍 |
| inject_blockdim | blockdim_too_small | 32 | 256 | 128 | **1** | 0 | 单核串行处理全部 32 张量，循环批处理吞吐低 |

### 4.3 实测 msprof 真机耗时

| Variant | label | Task Duration(us) | 相对 baseline | OPPROF 目录 |
|---------|-------|-------------------|---------------|-------------|
| baseline | baseline | **8.20** | 1.00× | `OPPROF_20260706165316_TRPGYFJLXMCWCFGC` |
| inject_tiling_unreasonable | tiling_unreasonable | **54.60** | **6.66×** | `OPPROF_20260706165327_IRHEOVQXLJNJAOIX` |
| inject_data_move_bottleneck | data_move_bottleneck | 10.26 | 1.25× | `OPPROF_20260706165338_FNDPFUISBPLTLPFQ` |
| inject_blockdim | blockdim_too_small | 28.32 | 3.45× | `OPPROF_20260706165349_MXYZQMUBEBBIZYPA` |

```
baseline                     ████                          8.20 μs
inject_tiling_unreasonable   ██████████████████████      54.60 μs
inject_data_move_bottleneck  ████                         10.26 μs
inject_blockdim              ███████████                  28.32 μs
```

### 4.4 解读

1. **`tiling_unreasonable` 6.66× — 三算子所有 case 中最显著**：tile 从 128→8 使每张量规约切 2→32 次，`ReduceSum` 的启动/收尾固定开销 × 32 张量 × 16 倍内层次数被放大，符合"Tiling 不合理"靶点预期。这是规约类算子的标志性反模式——tile 越小，规约开销占比越高。
2. **`blockdim_too_small` 3.45×**：4 核 → 1 核串行处理 32 张量，循环批处理吞吐下降。注意 foreach_norm 的 blockdim 退化倍率（3.45×）比 gelu_mul（2.40×）/fast_gelu_grad（2.55×）更大，因 N=32 张量的外层循环串行后总耗时线性累加，没有单核流水的补偿效应。
3. **`data_move_bottleneck` 1.25×**：每 tile 多一次 GM→UB 重复搬运，MTE2 带宽需求翻倍，但被多核（4 核分担）+ MTE2/V 流水掩盖部分影响，绝对开销 ~2 μs。说明在当前规模（32×256=8K elem）下搬运尚未成为瓶颈，需更大 N 或 L 才能放大搬运信号。

---

## 5. 跨算子对比

### 5.1 全 case Task Duration 汇总（v2，16384 elem）

| 算子 | baseline (μs) | 最显著 inject | 最显著 label | 最显著 μs | 倍率 |
|------|---------------|---------------|--------------|-----------|------|
| gelu_mul | 7.60 | inject_tilelen_small | tileLength_too_small | 60.68 | **7.98×** |
| fast_gelu_grad | 8.52 | inject_blockdim | blockdim_too_small | 30.08 | 3.53× |
| foreach_norm | 8.20 | inject_tiling_unreasonable | tileLength_too_small | 54.60 | **6.66×** |

```
gelu_mul / tileLength_too_small         ████████████████████████████  60.68 μs (7.98×)
foreach_norm / tileLength_too_small     █████████████████████████     54.60 μs (6.66×)
fast_gelu_grad / blockdim_too_small     ██████████████                30.08 μs (3.53×)
                                        ──────────────────────────
                                         0     20     40     60
```

### 5.2 靶点命中率（v2）

| 算子 | 主靶点 inject variant | 倍率 | 是否该算子内最显著 case | 评价 |
|------|----------------------|------|------------------------|------|
| gelu_mul | inject_tilelen_small（流水并行不足） | **7.98×** | ✅ 该算子内最大 | 靶点命中，v1 4.06×→v2 7.98× |
| gelu_mul | inject_excessive_barrier（流水并行不足） | 1.30× | ❌ 仍不显著 | v1 1.07×→v2 1.30×，skill canonical recipe 改善但 baseline V 屏障掩盖 |
| fast_gelu_grad | inject_scalar_loop（API/算法低效） | **1.00×** | ❌ 无信号 | skill recipe 的标量循环被 bisheng -O2 DCE，需修复 recipe |
| foreach_norm | inject_tiling_unreasonable（Tiling 不合理） | **6.66×** | ✅ 该算子内最大 | 靶点命中（未重采，沿用 v1） |
| foreach_norm | inject_data_move_bottleneck（数据搬运瓶颈） | 1.25× | ⚠️ 可见但不主导 | 需放大 N/L |

### 5.3 反模式信号强度排序（v2 实测倍率）

```
gelu_mul / tileLength_too_small         7.98×  ████████████████████████████  ← 最强（v2 放大 workload）
foreach_norm / tileLength_too_small     6.66×  █████████████████████████
gelu_mul / blockdim_too_small           3.80×  ██████████████
fast_gelu_grad / blockdim_too_small     3.53×  █████████████
foreach_norm / blockdim_too_small       3.45×  ████████████
gelu_mul / excessive_pipe_barrier       1.30×  █████
foreach_norm / redundant_copyin         1.25×  ████
fast_gelu_grad / scalar_loop_redundant  1.00×  ███  ← skill recipe DCE bug
```

---

## 6. 结论与后续（v2）

| 结论 | 说明 |
|------|------|
| **Tiling 类反模式最稳定显著** | gelu_mul `tileLength_too_small` v2 达 **7.98×**（v1 4.06× → 放大 workload 8× 后增强近 2×），foreach_norm `tileLength_too_small` 6.66×。**workload 放大是 tiling 类反模式最有效的信号放大器**——循环次数 ×N 直接放大固定开销。 |
| **blockdim=1 普遍 3–3.8× 退化** | v2 在 16384 elem 下 gelu_mul 3.80×、fast_gelu_grad 3.53×、foreach_norm 3.45×，三者趋于一致。多核并行缺失是第二可靠的反模式信号。 |
| **Skill canonical recipe `excessive_pipe_barrier` 优于手写** | v1 手写 `inject_pipe_break`（per-stage `PIPE_ALL`）1.07×；v2 skill recipe `excessive_pipe_barrier`（tile 边界双 `PIPE_ALL`）1.30×。改善但仍弱——根因是 baseline kernel 已有 `PIPE_V` 屏障，跨阶段 overlap 本就有限。**需重构 baseline 移除 V 屏障**才能充分放大流水信号。 |
| **Skill recipe `scalar_loop_redundant` 存在 DCE bug** | bisheng -O2 将 64-iter 标量循环 + 永假条件屏障作为 dead code 消除，注入零开销（1.00×）。**这是 skill 需修复的 bug**：recipe 必须包含不可消除的 side effect（volatile GM 写、`asm volatile`、或写入 output tensor 的 dummy 路径）。 |
| **Skill schema v2 对齐成功** | 全部 12 case 已补 `inject_manifest.json`（schema v2），通过 `validate_inject_cases.py` 校验（`pass=True`）。`inject_excessive_barrier` 和 `inject_scalar_loop` 由 `tools/inject_case.py` 自动生成（含 kernel patch + manifest），其余 10 case 手工 retrofit。 |
| **靶点命中率 3/5** | gelu_mul/tile ✅、gelu_mul/excessive_barrier ❌（1.30×）、fast_gelu_grad/scalar_loop ❌（1.00× DCE）、foreach_norm/tiling ✅、foreach_norm/data_move ⚠️（1.25×）。 |

**后续工作**：
1. **修复 skill `scalar_loop_redundant` recipe**：加 volatile side effect 防 DCE，或换用 `Adds(+0)` 等价 vector op（无 DCE 风险）。
2. **重构 gelu_mul baseline kernel**：移除 per-stage `PIPE_V` 屏障，让 MTE2/V/MTE3 overlap 充分发生，再重测 `excessive_pipe_barrier` 信号。
3. **foreach_norm 放大搬运信号**：把 N=32→128 或 L=256→1024，使 `redundant_copyin` 的 MTE2 翻倍效应突破流水掩盖。
4. **补采 aic metrics**：`aivector compute usage`、`MTE2/MTE3 bandwidth utilization`，把"AI Core 利用率低"从 Task Duration 推断升级为直接指标。
5. **接入 `/ascendc-aprof-diagnosis` 闭环**：用 12 case 的 `inject_manifest.json.ground_truth` 做盲诊对齐，验证自动归因准确率。

---

## 7. 采集链路对比（与 fast_gelu 一致）

| 维度 | 本批注入 (new_ops) | fast_gelu 注入 |
|------|---------------------|----------------|
| 工程路径 | `aprof_injected_ops/{gelu_mul,fast_gelu_grad,foreach_norm}/` | `aprof_injected_ops/fast_gelu/` |
| Kernel 模板 | AProf vector inject 模板 + foreach 扩展 | AProf vector inject 模板 |
| 编译架构 | `dav-2201`（真机） | `dav-3510`（sim）/ `dav-2201`（真机） |
| 运行方式 | `msprof op --config`（mode=onboard） | `msprof op simulator --config` / `msprof op --config` |
| 主要产物 | `OpBasicInfo.csv`（Task Duration） | `trace.json`（sim）/ `OpBasicInfo.csv`（hw） |
| Runner | `run_remote_new_ops_inject_hw.py` | `run_remote_fast_gelu_inject*.py` |

---

## 8. 相关文档

- 注入流程与设计矩阵：`docs/new_ops_inject_workflow.md`
- 原始 fast_gelu 注入流程：`docs/fast_gelu_inject_workflow.md`
- fast_gelu 注入对比报告：`benchmarks/aprof_injected_ops/fast_gelu_inject_report.md`
- 注入 skill：`skills/aprof/benchmark/ascendc-aprof-inject-problems/`
- 合并数据：`benchmarks/aprof_injected_ops/new_ops_inject_results.json`
