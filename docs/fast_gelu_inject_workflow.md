# FastGelu 问题注入与 msprof 采集流程

本文记录 `ascendc-aprof-inject-problems` skill 在 **fast_gelu** 上的落地方式，以及在 PKU 远程机上的编译 + msprof simulator 采集结果。

## 注入 case 位置

```
benchmarks/aprof_injected_ops/fast_gelu/
├── baseline/
├── inject_blockdim/      → blockdim_too_small
├── inject_tail/          → tail_inefficient
├── inject_tilelen_small/ → tileLength_too_small
├── inject_tilelen_large/ → tileLength_too_large
├── inject_tilenum/       → tileNum_unreasonable
└── inject_dynshape/      → fixed_tiling_dynamic_shape
```

每个 variant 通过 `scripts/gen_data.py` 旋钮 + `op_kernel/aprof_variant_config.h` 编译期开关注入单一问题，ground-truth 写在 `metadata.json.injected_label`。

## 本地运行（需 CANN + simulator）

```bash
cd benchmarks/aprof_injected_ops/fast_gelu/inject_blockdim
export ASCEND_HOME_PATH=...
export ASC_ARCH=dav-3510   # simulator 与 kernel 架构需一致
bash run.sh all            # gen + build_sim + msprof op simulator --config
```

共享脚本：`benchmarks/aprof_injected_ops/common/inject_run.sh`

## 远程一键采集（PKU xeon6）

```powershell
# 编译 + sim 四个代表 case
python scripts/run_remote_fast_gelu_inject.py

# 单 case 重跑 sim（调 ulimit / 架构后）
$env:INJECT_CASE="inject_blockdim"
python scripts/run_remote_fast_gelu_inject_sim.py
```

远程路径：`/home/u2300013210/aprof_fast_gelu_inject/<variant>/`

本地产物：`benchmarks/aprof_injected_ops/fast_gelu/remote_inject_out/`

## 关键参数（inject_blockdim 示例）

| 字段 | 值 |
|------|-----|
| injected_label | `blockdim_too_small` |
| output_elements | 512 |
| blockdim | 1 |
| tile_length | 256 |
| tile_num | 2 |
| npu-arch (sim) | `dav-3510` |

## msprof simulator 产物

成功采集后目录结构：

```
msprof_sim_output/OPPROF_<ts>_<id>/
└── simulator/
    ├── trace.json
    └── core0.veccore0/
        ├── trace.json
        └── *_instr_exe_*.csv   # 若 bisheng -g
```

`inject_blockdim` 已在远程验证：`OPPROF_20260629120814_IRTCXDPNGQZYLEKL`，core0.veccore0 duration ≈ 1.89 μs。

## 注意事项

1. **架构一致**：远程 CANN 9.0 simulator 使用 `dav_3510`；kernel 必须用 `--npu-arch=dav-3510` 编译，不能用真机 `dav-2201` 编完再 sim。
2. **ulimit**：sim 会打开大量 dump 文件，需 `ulimit -n 65536`（已写入 `inject_run.sh`）。
3. **无 numpy**：`inject_gen_data.py` 已改为标准库，远程无需 pip。
4. **真机上板**：inject case 仅提供 device `.o` + `op_config.json`（`--config` 模式）；真机 msprof 需另建 host 直调工程（见 `reference_ops/fast_gelu`）。

## 诊断闭环（后续）

```bash
python scripts/run_closed_loop.py   # 当前覆盖 swi_glu 三 case
# fast_gelu 对齐函数：src/aprof/benchmarks/closed_loop.py::run_fast_gelu_alignment
```

需将 `msprof_sim_output` 产物放回各 inject 目录后，可用 `/ascendc-aprof-diagnosis` 验证 `injected_label` 对齐。
