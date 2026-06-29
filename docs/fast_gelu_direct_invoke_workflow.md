# FastGelu 直调工程搭建与性能采集流程

本文记录如何在 **AProf** 仓库中，基于 CANNBot `ops-direct-invoke` / `ops-profiling` skills，将 [ops-nn FastGelu](https://gitcode.com/cann/ops-nn/tree/master/activation/fast_gelu) 落地为可编译、可验证、可采集性能的直调 benchmark。

> 工程路径：`benchmarks/reference_ops/fast_gelu/`  
> 验证平台：Ascend950 (`dav-3510`)，CANN 需通过 `source scripts/setup_env.sh` 激活。

---

## 1. 背景与目标

| 步骤 | 目标 | 使用 skill |
|------|------|------------|
| 获取 kernel | 从 ops-nn 拿到 `fast_gelu_apt.cpp` | — |
| 搭直调框架 | `op_host` + `op_kernel` + CMake + run.sh | `ascendc-direct-invoke-template`（ops-direct-invoke 插件白名单） |
| 编译运行 | 精度对齐 golden | `run.sh` |
| 性能采集 | simulator / 真机 msprof | `ops-profiling` + `ascendc-msprof-simulator` |

**不在本文范围**（后续计划）：`ascendc-aprof-inject-problems` 注入性能问题 + msprof signing 闭环。

---

## 2. 获取上游 kernel

```bash
# 已在仓库 third_party/ops-nn（sparse clone）
git clone --depth 1 --filter=blob:none --sparse https://gitcode.com/cann/ops-nn.git third_party/ops-nn
cd third_party/ops-nn && git sparse-checkout set activation/fast_gelu
```

核心文件：

- `activation/fast_gelu/op_kernel/fast_gelu_apt.cpp` — 生产 kernel 入口
- `activation/fast_gelu/op_kernel/arch35/fast_gelu_dag.h` — 计算公式与 MicroAPI 实现
- `activation/fast_gelu/tests/assets/golden.py` — Python golden

**注意**：`fast_gelu_apt.cpp` 依赖 `atvoss/`、`ElementwiseSch`、`EleBaseTilingDataV2` 等算子仓基础设施，**不能直接**放进 AProf 的 reduce_sum 式直调模板编译。因此 benchmark 中：

- `op_kernel/upstream/` 保留原版参考；
- `op_kernel/fast_gelu_kernel.asc` 按同一公式手写 Vector 直调实现。

公式（与 `fast_gelu_dag.h` 一致）：

```
y = x / (exp(-1.702 * x) + 1)
```

---

## 3. 用 ops-direct-invoke 搭直调框架

遵循 `ascendc-direct-invoke-template` Vector 分支（`references/add_custom/`），对照 `benchmarks/reference_ops/reduce_sum/` 的 host 风格：

### 3.1 目录与改名

```
fast_gelu/
├── op_kernel/fast_gelu_tiling.h      # host/kernel 共用 tiling 结构体
├── op_kernel/fast_gelu_kernel.asc    # __vector__ 入口 fast_gelu_kernel
├── op_host/fast_gelu.asc             # ACL 初始化 + <<<>>> launch
├── op_host/data_utils.h
├── CMakeLists.txt                    # target: fast_gelu, --npu-arch=dav-3510
└── run.sh                            # build → gen_data → run → verify
```

### 3.2 Tiling 设计

`FastGeluTilingData`（16 字节，4×`uint32`）：

| 字段 | 含义 |
|------|------|
| `totalLength` | 元素总数 `M×N` |
| `numPerCore` | 每核处理元素数（除尾核） |
| `tailNumLastCore` | 尾核元素数 |
| `blockNum` | launch block 数 |

按 `TILE_LENGTH=4096` 做 UB 分块，多核按 tile 维度切分（与 add_custom 相同模式）。

### 3.3 Kernel 计算

```cpp
Muls(tmp, x, -1.702f, count);
Exp(tmp, tmp, count);
Adds(tmp, tmp, 1.0f, count);
Div(y, x, tmp, count);
```

### 3.4 Host launch

```cpp
fast_gelu_kernel<<<tiling.blockNum, nullptr, stream>>>(devInput, devOutput, devTiling);
```

---

## 4. 编译与精度验证

```bash
cd Aprof
source scripts/setup_env.sh

cd benchmarks/reference_ops/fast_gelu
bash run.sh 8 2048 fp32 1
```

`run.sh` 四步：

1. `cmake` 编译 `build/fast_gelu`
2. `scripts/gen_data.py` 生成 `data/input.bin` + `data/golden.bin`
3. `build/fast_gelu` 写 `build/output/output.bin`
4. `scripts/verify_result.py` 对比（rtol/atol=1e-4）

默认参数写入 `metadata.json`。

---

## 5. 性能采集

### 5.1 Simulator（无 NPU，推荐）

遵循 `ascendc-msprof-simulator` skill 与 `reduce_sum/docs/direct_invoke_msprof_sop.md`：

```bash
cd benchmarks/reference_ops/fast_gelu
bash scripts/profile_sim.sh 8 2048 1 10
```

内部步骤：

1. `scripts/build_kernel_o.sh` — `bisheng --aicore-only` + `ld.lld` → `build_sim/fast_gelu_kernel.o`
2. `scripts/gen_msprof_bins.py` — `input.bin` + `tiling.bin`
3. `msprof op simulator --config=build_sim/op_config.json --output=msprof_sim_output`

报告位置：

```
msprof_sim_output/OPPROF_*/device0/fast_gelu_kernel/0/simulator/
├── trace.json
├── visualize_data.bin
└── core0.veccore0/
    ├── *_instr_exe_*.csv
    └── *_code_exe_*.csv   # 需 bisheng -g
```

`build_sim/op_config.json` 中 `magic` 为 `RT_DEV_BINARY_MAGIC_ELF_AIVEC`（`__vector__` 入口）。

### 5.2 真机上板（ops-profiling skill）

需物理 NPU + `msprof`：

```bash
cd benchmarks/reference_ops/fast_gelu
bash scripts/profile_hw.sh 8 2048 1 3
```

调用 `third_party/cannbot-skills/ops/ops-profiling/scripts/msprof_profile_run.sh` 对 `build/fast_gelu` 做标准采集，再用 `msprof_perf_summary.py` 解析 `PROF_GROUP_*`。

---

## 6. 参数记录

`metadata.json` 示例：

```json
{
  "operator_name": "FastGelu",
  "shape": "float32[8, 2048]",
  "data_type": "float32",
  "soc_version": "Ascend950PR_950x",
  "upstream_kernel": "third_party/ops-nn/activation/fast_gelu/op_kernel/fast_gelu_apt.cpp"
}
```

修改 shape 时需同步更新：

- `run.sh` 命令行参数
- `scripts/gen_msprof_bins.py` 参数
- `build_sim/op_config.json` 中 `shape` / `case_name`

---

## 7. 后续：inject problem（预留）

计划使用 `skills/aprof/benchmark/ascendc-aprof-inject-problems` 在 `benchmarks/aprof_injected_ops/` 下构造带 `injected_label` 的 FastGelu 变体，并跑 msprof signing 闭环。当前 skill/脚本尚未完善，**本阶段仅完成 reference 直调 + profiling 基线**。

---

## 8. 参考链接

- [ops-nn FastGelu](https://gitcode.com/cann/ops-nn/tree/master/activation/fast_gelu)
- [AProf reduce_sum SOP](../benchmarks/reference_ops/reduce_sum/docs/direct_invoke_msprof_sop.md)
- CANNBot `ops-direct-invoke`：`third_party/cannbot-skills/plugins-official/ops-direct-invoke/`
- CANNBot `ops-profiling`：`third_party/cannbot-skills/ops/ops-profiling/`
