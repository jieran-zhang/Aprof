# FastGelu 注入前 / 注入后对比报告

> 生成时间：2026-06-29  
> 算子：`fast_gelu`  
> 远程主机：`xeon6.pku-dasys.cn`（CANN 9.0.0，simulator `dav-3510`）

---

## 1. 数据都在哪里？

**不是**全部放在一个 `json/` 目录里，而是按用途分散存放：

| 类型 | 路径 | 内容 |
|------|------|------|
| 注入旋钮与标签 | `fast_gelu/<variant>/metadata.json` | `injected_label`、blockdim、tile_length、tile_num 等 |
| 汇总结果 | `fast_gelu/remote_inject_out/results.json` | 远程 sim 是否成功、core duration |
| 单次重跑记录 | `fast_gelu/remote_inject_out/*_sim_rerun.json` | 某 variant 的 trace 文件路径列表 |
| msprof 时间线 | `fast_gelu/remote_inject_out/<variant>/msprof_sim_output/OPPROF_*/simulator/trace.json` | Chrome Tracing 格式，simulator 主报告 |
| 逐核时间线 | `.../simulator/core0.veccore0/trace.json` | 单核细分 |
| 真机直调（另一套工程） | `reference_ops/fast_gelu/remote_out/` | `op_summary_*.csv`、`PROF_GROUP_*`（Ascend910B，`dav-2201`） |

注入 benchmark 走 **`msprof op simulator --config`**（device `.o` + `op_config.json`）；  
reference 直调走 **真机 `msprof` + host 可执行文件**，两者采集模式不同，下文分开对比。

---

## 2. 注入前（baseline）配置

来源：`fast_gelu/baseline/metadata.json`

| 字段 | 值 |
|------|-----|
| variant | `baseline` |
| injected_label | `baseline` |
| output_elements | 2048 |
| blockdim | 1 |
| tile_length | 256 |
| tile_num | 8 |
| tail_length | 0 |
| variant_flags | 0 |

**sim 采集状态**：首次批量远程 sim 因 `ulimit` 未产出可用 `trace.json`；后续重跑仅覆盖了三个 inject variant。**baseline 的 simulator duration 本次报告中暂无**，仅作配置对照。

---

## 3. 注入后三个代表 case

### 3.1 旋钮对比（metadata）

| Variant | injected_label | output_elements | blockdim | tile_length | tile_num | tail_length | flags |
|---------|----------------|-----------------|----------|-------------|----------|-------------|-------|
| **baseline** | baseline | 2048 | 1 | 256 | 8 | 0 | 0 |
| inject_blockdim | blockdim_too_small | 512 | 1 | 256 | 2 | 0 | 0 |
| inject_tail | tail_inefficient | 2305 | 1 | 256 | 10 | 1 | 1 |
| inject_tilelen_small | tileLength_too_small | 2048 | 1 | **16** | **128** | 0 | 0 |

相对 baseline 的变化：

- **inject_blockdim**：`blockdim=1` 且 workload 缩小为 512 元素（单核过载侧实验）
- **inject_tail**：`output_elements=2305` 故意不整除 `tile_length`，`tail_length=1`，`APROF_INJECT_TAIL=1` 开启尾块重复搬运
- **inject_tilelen_small**：与 baseline **同规模 2048 元素**，但 `tile_length` 从 256 降到 16，`tile_num` 从 8 升到 128

### 3.2 msprof simulator 耗时（core0.veccore0）

来源：`remote_inject_out/results.json`（远程 `msprof op simulator --config`，`dav-3510`）

| Variant | injected_label | core duration (μs) | 相对 inject_blockdim | OPPROF 目录 |
|---------|----------------|-------------------|----------------------|-------------|
| inject_blockdim | blockdim_too_small | **1.89** | 1.00× | `OPPROF_20260629120814_IRTCXDPNGQZYLEKL` |
| inject_tail | tail_inefficient | **5.37** | 2.84× | `OPPROF_20260629120927_UJKGFOYGJRGGNSXD` |
| inject_tilelen_small | tileLength_too_small | **48.64** | **25.7×** | `OPPROF_20260629121018_ROAGYWBHATXGTBWK` |

```
inject_blockdim        ████                          1.89 μs
inject_tail            ████████████                  5.37 μs
inject_tilelen_small   ████████████████████████████  48.64 μs
```

**解读（与注入意图一致）：**

1. **tileLength_too_small** 影响最大：在 **与 baseline 相同的 2048 元素** 下，tile 从 8 次循环暴增到 128 次，simulator 耗时约为 blockdim case 的 **26 倍**，符合「循环/同步开销主导」的预期。
2. **tail_inefficient**：2305 元素 + 尾块注入，耗时约为 blockdim case 的 **2.8 倍**；绝对值仍低于 tilelen_small，因 tile 次数仍为 10 次量级。
3. **blockdim_too_small**：workload 仅 512 元素，绝对耗时最短；与 baseline 不能直接比 μs，需看 **每元素耗时** 或补采同规模 baseline。

### 3.3 同规模粗算（μs / 元素）

| Variant | output_elements | μs / element |
|---------|-----------------|--------------|
| inject_blockdim | 512 | 0.0037 |
| inject_tail | 2305 | 0.0023 |
| inject_tilelen_small | 2048 | **0.0237** |

`inject_tilelen_small` 的每元素成本明显高于另两者，再次印证 tile 过小的反模式。

---

## 4. 与 reference 直调真机数据的对照（非注入矩阵）

来源：`reference_ops/fast_gelu/`（host 直调，`dav-2201`，Ascend910B 真机）

| 项 | 值 |
|----|-----|
| shape | `[8, 2048]` → 16384 元素 |
| Task Duration（msprof 真机） | **10.8 μs** |
| AIV vec 占比 | 14.7% |
| AIV MTE2 占比 | 42.1% |
| 采集目录 | `reference_ops/fast_gelu/remote_out/msprof_hw_output/PROF_GROUP_20260629_093334/` |

说明：

- 这是 **另一套工程**（`reference_ops` 直调 skeleton），不是 `aprof_injected_ops` 的 inject kernel 模板。
- **规模更大**（16384 vs 2048/512），**真机 vs simulator**，**dav-2201 vs dav-3510**，数值不可直接等同，仅作「同一 FastGelu 公式在不同链路下可达的性能量级」参考。

---

## 5. 采集链路对比

| 维度 | 注入前/后（injected_ops） | reference 直调 |
|------|---------------------------|----------------|
| 工程路径 | `aprof_injected_ops/fast_gelu/` | `reference_ops/fast_gelu/` |
| Kernel 模板 | AProf vector inject 模板 | 手写 CopyIn/Compute/CopyOut |
| 编译架构 | `dav-3510`（sim） | `dav-2201`（真机） |
| 运行方式 | `msprof op simulator --config` | `./fast_gelu` host + `<<<>>>` |
| 主要产物 | `trace.json` | `op_summary_*.csv`、`PROF_GROUP_*` |
| 精度验证 | inject 矩阵未在本轮跑 golden | 真机 verify PASS（max abs err ≈ 4.8e-7） |

---

## 6. 本地 trace 文件位置（已下载）

```
benchmarks/aprof_injected_ops/fast_gelu/remote_inject_out/
├── results.json
├── inject_blockdim_sim_rerun.json
├── inject_tail_sim_rerun.json
├── inject_tilelen_small_sim_rerun.json
├── inject_blockdim/msprof_sim_output/OPPROF_.../simulator/trace.json
├── inject_tail/msprof_sim_output/OPPROF_.../simulator/trace.json
└── inject_tilelen_small/msprof_sim_output/OPPROF_.../simulator/trace.json
```

可用 Chrome `chrome://tracing` 或 MindStudio Insight 打开 `trace.json` 做逐指令分析。

---

## 7. 结论与后续

| 结论 | 说明 |
|------|------|
| 注入有效 | `tileLength_too_small` 在同等 2048 元素下 sim 耗时显著上升（48.64 μs） |
| 标签可对齐 | 三个 case 的 `metadata.json.injected_label` 与 skill 配方一致，可供 AProf diagnosis 闭环 |
| baseline sim 待补 | 建议对 `fast_gelu/baseline` 用同一 `dav-3510` + `ulimit` 重跑 sim，得到与 `inject_tilelen_small` 同规模直接对比 |
| 真机 inject 未做 | inject 矩阵当前仅 device `.o`；真机上板需另建 host 直调或保持 sim 归因 |

**补采 baseline sim（远程）：**

```powershell
$env:INJECT_CASE="baseline"
python d:\Code\Aprof\scripts\run_remote_fast_gelu_inject_sim.py
```

**诊断闭环（本地，需 msprof 产物在 case 目录下）：**

```bash
python -c "from aprof.benchmarks.closed_loop import run_fast_gelu_alignment; print(run_fast_gelu_alignment())"
```

---

## 8. 相关文档

- 注入 skill：`skills/aprof/benchmark/ascendc-aprof-inject-problems/`
- 注入操作说明：`docs/fast_gelu_inject_workflow.md`
- 直调 + 真机 profiling：`docs/fast_gelu_direct_invoke_workflow.md`
