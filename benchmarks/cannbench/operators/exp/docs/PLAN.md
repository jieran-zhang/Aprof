# exp 算子开发计划

## 1. 需求概述

| 项目 | 内容 |
|---|---|
| 算子名称 | `exp` / `Exp` |
| 数学公式 | `base<=0: y=exp(scale*x+shift)`；`base>0: y=exp((scale*x+shift)*ln(base))` |
| 输入 | `x`，连续 ND，dtype=`float16/float32/bfloat16` |
| 输出 | `y`，shape/dtype 与 x 相同 |
| 算子类别 | Elementwise |
| 需求类型 | 通用 + `cases.yaml/cases.csv` 20 cases 强制验收 |
| 目标平台 | 真实 DAV_2201 NPU，CANN 9.0.0，`--npu-arch=dav-2201` |
| 精度口径 | FP16 `2^-10`，BF16 `2^-7`，FP32 `2^-13`；MERE/MARE + Inf/NaN 一致性 |
| 性能口径 | msprof `kernel_details.csv` Task Duration + cann-bench HAP Eq.3/Eq.4 |

需求追溯统一指向 DESIGN.md §0.2 第 1～6 条。

## 2. 文件清单

| 文件 | 用途 | 状态 |
|---|---|---|
| `kernel/exp_tiling.h` | Host/Kernel 共享 TilingData、branch key、dtype code | ⬜ |
| `kernel/exp_kernel.asc` | SIMD/MemBase Kernel、CopyIn/Compute/CopyOut | ⬜ |
| `host/exp.asc` | ACL 直调 main、动态核数/UB 查询、tiling、launch、I/O | ⬜ |
| `torch_library/exp_torch.cpp` | PyTorch NPU Host；验证参数并直接 launch Kernel | ⬜ |
| `torch_library/ops.h` + `torch_library/register.cpp` | `TORCH_LIBRARY` schema/registration | ⬜ |
| `CMakeLists.txt` | `LANGUAGES ASC CXX`；直调可执行与 `libexp_ops.so` 双 target | ⬜ |
| `run.sh` | 单 case/全 20 cases 调度，设备锁，结果归档 | ⬜ |
| `scripts/golden.py` | 复用权威 golden 语义 | ⬜ |
| `scripts/gen_data.py` | 按 case manifest 和固定 seed 生成输入/golden | ⬜ |
| `scripts/verify_result.py` | MERE/MARE、Inf/NaN mask/符号验证 | ⬜ |
| `scripts/test_torch.py` | PyTorch 接入与 direct runner 1:1 对应测试 | ⬜ |
| `scripts/profile_cases.sh` | warmup + msprof 采集，保存原始 profiler 产物 | ⬜ |
| `scripts/parse_perf.py` | 从 `kernel_details.csv` 解析 Task Duration | ⬜ |
| `scripts/score_cases.py` | 读取 910b2 metadata，按 HAP 公式生成 case/算子分数 | ⬜ |
| `cases/cases.yaml` + `cases/cases.csv` | 权威 20 cases 的可追溯副本/链接 | ⬜ |
| `docs/precision/summary.txt` | 20 cases 精度验收汇总 | ⬜ |
| `docs/perf/round_NNN/` | msprof 原始 CSV、命令、环境、解析 JSON | ⬜ |
| `results.json` | exp 算子级 build/precision/perf/HAP 汇总 | ⬜ |
| `README.md` | 环境、编译、运行、精度、profile 复现命令 | ⬜ |
| `docs/WALKTHROUGH.md` / `docs/REVIEW.md` | 官方 plugin 设计串讲/审查记录 | ⬜ |
| `../../benchmark_results.json` | 更新 exp 项目级状态与产物路径 | ⬜ |

## 3. 测试计划

### 3.1 测试通路和通用断言

- Direct executable 和 PyTorch `.so` 两条通路使用同一 Kernel/Tiling 逻辑，20 cases 1:1 对应。
- `gen_data.py` 和 `test_torch.py` 共享 `scripts/golden.py`，语义与任务 `golden.py` 一致。
- 每 case 断言 shape、dtype、特殊值 mask，然后对普通有限值计算 MERE/MARE。
- 每 case 在正确性通过后才进入性能计分；性能阶段再次抽样检查输出，防止性能分支破坏精度。
- 必须另加不计分 smoke：最小 1 元素、32B 边界前后、base=1 且 x=Inf/NaN，证明通用路径不错用 finite-only 快路。

### 3.2 20 个强制 case

`Txx/Pxx` 分别为 direct/PyTorch 通路，全部追溯 DESIGN.md §0.2 #2/#3/#4。baseline 和 T_HW 来自 `tasks/metadata/910b2.json`，单位为 us。

| ID | shape / dtype | attrs `(base,scale,shift)` | 特殊覆盖 | baseline / T_HW |
|---:|---|---|---|---:|
| T01/P01 | `[1024,1024]` FP16 | `(-1,1,0)` | 对齐、Exp-only | 10.9 / 1.09 |
| T02/P02 | `[2048,2048]` FP32 | `(-1,1.5,0)` | FP32、Muls | 29.06 / 8.74 |
| T03/P03 | `[4096,4096]` BF16 | `(-1,2,0)` | BF16 Cast、大 shape | 58.922 / 17.48 |
| T04/P04 | `[8192,8192]` FP16 | `(-1,0.5,0)` | 67M 元素 | 143.202 / 69.91 |
| T05/P05 | `[8192,8192]` FP32 | `(-1,1,1)` | 大范围溢出 | 354.187 / 139.81 |
| T06/P06 | `[1023,1023]` BF16 | `(2,1,0)` | 非对齐、自定义 base | 10.9 / 1.09 |
| T07/P07 | `[1009,1021]` FP16 | `(2,1.5,0)` | 质数 tail、标量舍入 | 10.7 / 1.07 |
| T08/P08 | `[1537,769]` FP32 | `(10,1,0)` | 非对齐、base=10 | 16.5 / 2.46 |
| T09/P09 | `[363,367,373]` BF16 | `(-1,2,0.5)` | 3D、大范围 | 228.864 / 51.76 |
| T10/P10 | `[2049,513]` FP16 | `(-1,1,2)` | FP16 边界、Inf/0 | 10.9 / 1.09 |
| T11/P11 | `[3,7,13,4003]` FP32 | `(1,2,0)` | finite-only base=1 快路 | 22.46 / 2.28 |
| T12/P12 | `[1000007]` BF16 | `(-1,0.5,0.5)` | Inf 符号一致 | 10.4 / 1.04 |
| T13/P13 | `[11,13,17,67,67]` FP32 | `(2,1,1)` | NaN mask 一致 | 92.263 / 22.73 |
| T14/P14 | `[3,7,11,13,1013]` FP16 | `(-1,2,1)` | 零输入、5D | 26.34 / 3.17 |
| T15/P15 | `[512,2049]` FP32 | `(-1,1,0.5)` | 微小对称范围 | 21.361 / 2.19 |
| T16/P16 | `[255,8193]` BF16 | `(-1,1.2,0)` | BF16 标量精度 | 20.12 / 2.18 |
| T17/P17 | `[4097,511]` FP16 | `(1,0.5,0)` | finite-only base=1、大输入 | 21.8 / 2.18 |
| T18/P18 | `[2,511,2049]` FP32 | `(2,0.5,0)` | 3D、微小值 | 37.121 / 4.36 |
| T19/P19 | `[4,255,2049]` BF16 | `(10,0.5,0.5)` | 3D、base=10 | 24.4 / 2.44 |
| T20/P20 | `[2,3,17,1024,101]` FP16 | `(1,1.5,1)` | finite-only base=1、5D | 51.582 / 12.31 |

### 3.3 性能采集与评分产物

每个 case 在 `docs/perf/round_NNN/case_XX/` 保存：

- `command.txt`、`environment.json`、`npu_smi.txt`、`arch_probe.txt`；
- msprof 原始目录和权威 `kernel_details.csv`；
- `parsed.json`，包含 kernel name、block dim、Task Duration 样本、聚合值；
- `score.json`，包含 `baseline_perf_us`、`t_hw_us`、`t_cand_us`、`score_i`、公式版本；
- 性能阶段的输出复检结果。

`results.json` 必须至少包含 schema version、git revision、CANN/NPU/arch、20 case 状态、MERE/MARE/特殊值结果、Task Duration、HAP、产物相对路径和完整性校验。更新项目 `benchmark_results.json` 时不覆盖其他算子条目。

## 4. 开发进度

| 阶段 | 检查项 | 状态 |
|---|---|---|
| 设计串讲 | Design Reviewer 生成 WALKTHROUGH，Architect 回应分歧 | ⬜ |
| 框架搭建 | CMake 双 target、ACL runtime、输入输出及 case loader | ⬜ |
| Tiling | 动态 AIV/UB、former/tail block、dtype UB 预算、溢出保护 | ⬜ |
| Kernel | FP16/FP32/BF16/常量快路、DataCopy/DataCopyPad | ⬜ |
| 构建验证 | 架构再探测、CMake 配置、双 target 完整编译 | ⬜ |
| Direct 精度 | T01–T20 全部通过，产出 precision summary | ⬜ |
| PyTorch 接入 | `torch.ops.npu.exp` 可调，P01–P20 全部通过 | ⬜ |
| 独立审查 | Reviewer 独立构建/运行，REVIEW=PASS/PASS WITH NOTES | ⬜ |
| 性能采集 | 真实 NPU msprof 20 cases，原始数据与解析归档 | ⬜ |
| 评分汇总 | 生成 exp `results.json`，原子更新项目汇总 JSON | ⬜ |

## 5. PyTorch 接入计划

Schema 与权威 proto 一致：

```text
exp(Tensor x, float base=-1.0, float scale=1.0, float shift=0.0) -> Tensor
```

PyTorch Host 仅做：contiguous NPU Tensor/dtype/shape/attrs 校验、输出分配、属性标量和 tiling 计算、当前 stream 上直接 launch。不得调用 `torch.exp`、`torch_npu` 同名算子、CPU fallback，也不得将 x 转置/转 dtype 作为 Host 预处理。通用 PyTorch 通路不启用 finite-only `base=1` 快路，以保持 Inf/NaN 语义。

## 6. 已知风险和决策记录

| 日期 | 问题/决策 | 处理 |
|---|---|---|
| 2026-08-11 | 环境字面 `Ascend910/ASCEND910` 与实测 DAV_2201 冲突 | 按实测 `dav-2201` 设计；构建前强制复探，不一致则停止 |
| 2026-08-11 | 基础 Exp/Muls/Adds 不支持 BF16 | 必须 BF16→FP32→BF16 |
| 2026-08-11 | FP16 golden 是 FP32 计算后回转，原生 half 可能超阈值 | 先实测 20 cases；任一失败即整体切换 FP32 中间链路 |
| 2026-08-11 | `base=1` 对 Inf/NaN 不可盲目化简为 1 | 快路仅限 manifest 已知 finite 的 case runner；通用/PyTorch 保守计算 |
| 2026-08-11 | 大 case 可能需数百 MB device/host 内存 | 按 case 串行执行并及时释放；不同 NPU 之间才可并行 |
| 2026-08-11 | HAP 锚点必须与硬件口径匹配 | 保存硬件证据；仅当设备符合 910B2/DAV_2201 口径时使用 910b2 metadata |

## 7. 测试结果（待 Developer/Reviewer 回填）

### 7.1 Direct executable

**状态**：⬜　**脚本**：`run.sh --all` + `scripts/verify_result.py`

| 范围 | 用例数 | 通过 | 失败 | 精度报告 |
|---|---:|---:|---:|---|
| T01–T20 | 20 | | | `docs/precision/summary.txt` |

### 7.2 PyTorch

**状态**：⬜　**脚本**：`scripts/test_torch.py --all`

| 范围 | 用例数 | 通过 | 失败 | 备注 |
|---|---:|---:|---:|---|
| P01–P20 | 20 | | | 与 Direct 同输入/同 golden |

### 7.3 产物和执行状态

- [ ] `build/exp` 可执行文件存在。
- [ ] `build/libexp_ops.so` 存在。
- [ ] `torch.ops.load_library` + `torch.ops.npu.exp` 可调。
- [ ] 20 cases 的 precision/perf 产物齐全。
- [ ] `results.json` 通过 schema/完整性校验。
- [ ] 项目 `benchmark_results.json` 中 exp 条目已更新。

## 8. 性能验收（待回填）

**状态**：⬜　**数据**：`docs/perf/round_NNN/`

| 指标 | 值 | 判定 |
|---|---|---|
| 20-case Task Duration | | |
| 20-case HAP score_i | | |
| Eq.4 算子总分 | | |
| Block Dim | | |
| 主导流水 | | |

**达标判定**：⬜　**理由**：

## 9. 汇总（待回填）

| 通路 | 用例数 | 通过 | 失败 | 状态 |
|---|---:|---:|---:|---|
| Direct | 20 | | | ⬜ |
| PyTorch | 20 | | | ⬜ |
| 性能/HAP | 20 | | | ⬜ |
