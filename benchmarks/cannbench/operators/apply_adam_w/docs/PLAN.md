# apply_adam_w 算子开发计划

## 1. 需求概述

| 项目 | 内容 |
|---|---|
| 算子名称 | `apply_adam_w` |
| 数学公式 | AdamW 四输入逐元素融合更新，详见 `DESIGN.md §1.1` |
| 输入 | `var, grad, m, v`，shape/dtype 完全一致，连续 ND |
| 输出 | `y`，shape/dtype 与 var 相同 |
| attrs | `lr,beta1,beta2,weight_decay,epsilon=1e-8,step=1,maximize=false` |
| dtype | FP32/FP16/BF16；半精度核内升 FP32 |
| 箙江类别 | L2 FusedComposite / Elementwise fusion |
| 目标平台 | 真实 DAV_2201 NPU，CANN 9.0.0，`--npu-arch=dav-2201` |
| 强制用例 | `cases.csv` 全部 20 个，覆盖率 100% |

## 2. 文件清单

所有产物必须位于 `benchmarks/cannbench/operators/apply_adam_w/`。

| 文件 | 作用 | 状态 |
|---|---|---|
| `op_kernel/apply_adam_w_tiling.h` | Host/Kernel 共用 TilingData、dtype code 与标量参数 | ✅ |
| `op_kernel/apply_adam_w_kernel.asc` | FP32 与 FP16/BF16 升精度 Kernel | ✅ ASC 编译通过 |
| `op_host/apply_adam_w.asc` | ACL 初始化、动态核数/UB查询、Tiling、Kernel launch、输入输出文件 I/O | ✅ |
| `op_host/data_utils.h`, `apply_adam_w_common.h` | 安全 bin I/O 与共享 Host Tiling | ✅ |
| `op_extension/apply_adam_w_torch.cpp` | PyTorch NPU wrapper，只做校验、输出分配、Tiling 和自定义 Kernel launch | ✅ 构建及 20/20 真 NPU 通过 |
| `op_extension/register.cpp`, `op_extension/ops.h` | `TORCH_LIBRARY` 注册与声明；禁止调用内置同名算子 | ✅ |
| `CMakeLists.txt` | 直调 target + 可选 `libapply_adam_w_ops.so` target | ✅ 双 target 构建通过 |
| `run.sh` | 单 case/全 case 构建、执行、校验入口 | ✅ |
| `scripts/golden.py` | 与权威公式一致并遵循 Host float reciprocal 契约 | ✅ |
| `scripts/cases.py` | 严格解析 `cases.csv`，保留 attrs/default/特殊值 | ✅ |
| `scripts/gen_data.py` | 按 case_id、seed 分块生成四输入与 golden；保存 metadata | ✅ FP32/BF16 自检通过 |
| `scripts/verify_result.py` | CANN-Bench MERE/MARE、NaN/Inf 语义、逐 case JSON | ✅ 真 NPU 20/20 |
| `scripts/test_torch.py` | PyTorch 自定义算子通路 20 case 一一对应测试 | ✅ 真 NPU 20/20 |
| `scripts/profile_cases.py` | warmup=3/repeat=5、msprof 采集与目标 Kernel Task Duration 解析 | ✅ 100 份正式 profiler |
| `scripts/score_cases.py` | 读取 910B2 metadata，计算逐 case HAP 与算子综合分 | ✅；75.5839696285 为修复前 round_001，修复版待全量重采后重算 |
| `README.md` | 环境、构建、单 case、全量、profiling、复现命令 | ✅ |
| `docs/precision/cases.json`, `docs/precision/summary.txt` | 20 case 真实 NPU 正确性证据 | ✅ |
| `docs/perf/round_001/` | msprof 原始目录、逐 case Task Duration/score、summary | ✅ |
| `results.json` | 本算子逐 case汇总，供顶层 JSON 合并 | ✅ 20 条 measured_on_npu |
| `docs/WALKTHROUGH.md`, `docs/REVIEW.md` | 官方插件串讲和独立审查记录 | ⬜ |

PyTorch wrapper 只用于满足官方直调插件的双通路验收；用户要求的主交付和性能口径仍是自定义 Ascend C Kernel 的直接 launch。包装层不得做 cast、transpose、切片、代算或 CPU fallback。

## 3. 开发步骤与门禁

| 阶段 | 工作与通过条件 | 状态 |
|---|---|---|
| 架构复核 | `get_npu_arch.py` 真机复探 | ✅ dav-2201 |
| 框架搭建 | 官方 add_custom 模板建立双 target；配置 CANN 9.0 和 asc-devkit | ✅ |
| Host/Tiling | 动态 AIV 核数、UB 查询；64 位长度；共享 Host tiling | ✅ 真机运行通过 |
| Kernel FP32 | 完成四输入融合链路、非对齐 DataCopyPad 与独立 VECOUT | ✅ |
| Kernel FP16/BF16 | 核内 Cast FP32，最终 CAST_RINT | ✅ |
| 直调全量 | `run.sh --all` 在真实 NPU 上 20/20 无运行错误且精度达标 | ✅ |
| PyTorch 接入 | `torch.ops.npu.apply_adam_w` 启动同一 Kernel；20/20 与直调用例一一对应 | ✅ |
| 独立审查 | Reviewer 独立 clean build、运行和代码审查，结论 PASS/PASS WITH NOTES | ⬜ |
| 性能采集 | 真实 NPU 上 20 case msprof；每 case 5 repeats | ✅ |
| 评分归档 | 修复后代表性能已归档；全量新综合分留待 Step 6b 重采 | 🟨 round_002 3/20 |

## 4. 测试计划

### 4.1 精度口径

权威 golden 为任务目录 `golden.py`。优先采用任务 `proto.yaml` 针对复杂 AdamW 链路给出的阈值：FP32/FP16/BF16 分别为 `0.005/0.01/0.01`，并记录通用社区阈值作为诊断字段。通过条件：

```text
MERE < threshold
MARE < 10 * threshold
```

特殊值比较规则：golden 与 actual 同位置均为 NaN 视为相等；同符号 Inf 视为相等；有限位置再计算 MERE/MARE。任何不对应的 NaN/Inf 都判失败。性能采集后必须重新做精度复检。

### 4.2 20 个强制用例及性能锚点

`baseline_perf_us`/`t_hw_us` 来自 `third_party/cann-bench/tasks/metadata/910b2.json` 的 `apply_adam_w` 条目。每行都执行直调 T 与 PyTorch P 两条路径；T 是主验收路径。

| ID | shape / dtype | 关键覆盖 | baseline µs | T_HW µs | 路径 |
|---:|---|---|---:|---:|---|
| 1 | 1024×1024 FP32 | 对齐、wd=0 | 38.14 | 8.74 | T1/P1 |
| 2 | 2048×2048 FP16 | 升精度、wd | 51.50 | 17.48 | T2/P2 |
| 3 | 4096×4096 BF16 | 升精度、大 Tensor | 244.74 | 69.91 | T3/P3 |
| 4 | 4096×4096 FP32 | 大 Tensor、lr=0.1 | 320.99 | 139.81 | T4/P4 |
| 5 | 4096×8192 FP16 | 最大内存用例；attrs 以 CSV 的 0.1/0.1 为准 | 306.85 | 139.81 | T5/P5 |
| 6 | 1023×1023 BF16 | 非对齐、微小值 | 34.42 | 4.36 | T6/P6 |
| 7 | 1009×1021 FP32 | 质数、beta1=0.5 | 38.56 | 8.58 | T7/P7 |
| 8 | 1537×769 FP16 | beta1/2=0.99、epsilon=1e-6 | 29.74 | 4.92 | T8/P8 |
| 9 | 363×367×373 BF16 | 3D、beta1=0、约 50M 元素 | 764.32 | 207.05 | T9/P9 |
| 10 | 2049×513 FP32 | maximize=true、大值域 | 36.38 | 8.76 | T10/P10 |
| 11 | 3×7×13×4001 FP16 | 4D、非对齐 | 28.70 | 4.55 | T11/P11 |
| 12 | 1000003 BF16 | 1D、Inf 特殊值 | 34.10 | 4.17 | T12/P12 |
| 13 | 11×13×17×67×67 FP32 | 5D、NaN、epsilon=0 | 167.04 | 90.94 | T13/P13 |
| 14 | 3×7×11×13×1013 FP16 | 全零、sqrt(0)+epsilon | 45.12 | 12.68 | T14/P14 |
| 15 | 512×2049 FP32 | epsilon=1e-4 | 38.54 | 8.74 | T15/P15 |
| 16 | 255×8193 BF16 | 非对称值域、wd | 48.32 | 8.71 | T16/P16 |
| 17 | 4097×511 FP16 | 大值域、非对齐 | 38.88 | 8.72 | T17/P17 |
| 18 | 2×511×2049 FP32 | 3D、微小值 | 51.46 | 17.45 | T18/P18 |
| 19 | 4×255×2049 BF16 | 3D、beta=0.99、wd=0.5 | 48.30 | 8.71 | T19/P19 |
| 20 | 2×3×17×1024×101 FP32 | 5D、maximize=true | 158.10 | 87.91 | T20/P20 |

补充 smoke cases（不替代 20 个评分用例）：显式 `step=2/100`、`beta=0.9999`、`epsilon=0 + v_hat=0`、负 `v_hat`、最小 shape `[1]`、8 维 shape、非法 shape/dtype、`beta=1`、`step=0`。其中 step/beta cases 保存 double denominator、float denominator、float reciprocal，并比较“乘倒数”与 golden 直接除法；特殊域 cases 验证 SafeSqrt/SafeDiv 的 zero/negative/±Inf/NaN 恢复。

### 4.3 可复现命令契约

最终 README 应提供并实际执行等价命令：

```bash
# 构建
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j

# 单 case / 全量直调正确性
bash run.sh --case 1 --device 0
bash run.sh --all --device 0

# PyTorch 自定义库通路
python3 scripts/test_torch.py --all --device 0

# 真实 NPU 性能；产生 docs/perf/round_001
python3 scripts/profile_cases.py --all --device 0 --warmup 3 --repeat 5 --output docs/perf/round_001

# 评分与归档
python3 scripts/score_cases.py --perf docs/perf/round_001 --metadata ../../../../third_party/cann-bench/tasks/metadata/910b2.json --output results.json
```

上述命令只是接口契约；Developer 应按最终脚本参数校正文档。每个 case 的结果 JSON 必须保存其实际完整命令、随机种子、device、CANN 版本、NpuArch 和 profiler 原始路径。

## 5. 性能与评分计划

### 5.1 采集规范

- 真实 NPU，设备型号/逻辑 ID/`npu-smi info` 快照归档。
- warmup=3、repeat=5、freq_boost=true、ProfilerLevel1。
- 只统计目标自定义 Kernel；从 `kernel_details.csv`/msprof dequeue 事件读取 Task Duration。
- 不以端到端 Python、文件 I/O 或 ACL Host 墙钟作为 Kernel 时间。
- 每个 case 保存 5 次正式值、聚合方法（与 CANN Bench 保持一致）及最终 `T_candidate`。
- 性能轮换输入后重新验证输出，防止缓存或固定输出。

### 5.2 评分

逐 case：

```text
score_i = (T_baseline_i - T_HW_i) /
          ((T_candidate_i - T_HW_i) + (T_baseline_i - T_HW_i))
```

单算子综合分（N=20，`w_c=0.2,w_f=0.3,w_p=0.5`）：

```text
EachOperatorScore = [0.2*delta_runtime
  + sum(delta_precision_i*(0.3+0.5*score_i)/20)]*100
```

若 `T_candidate <= T_HW`、分母非正或 metadata 缺失，脚本不得静默伪造分数；应记录原始时间和明确的评分状态，按 CANN Bench 当前实现处理/复核。

## 6. 结果文件验收

### 6.1 `results.json`

至少包含：

```json
{
  "operator": "apply_adam_w",
  "environment": {"device": "...", "npu_arch": "dav-2201", "cann": "9.0.0"},
  "build": {"status": "pass", "command": "..."},
  "correctness": {"passed": 20, "total": 20},
  "performance": {"status": "measured_on_npu", "operator_score": null},
  "cases": []
}
```

`cases` 必须正好 20 条且 case_id 唯一。任何尚未在真实 NPU 采集的字段保持 `null/pending`，禁止填入 simulator/CPU 数字。

### 6.2 顶层汇总

完成独立 Reviewer 验收后，更新 `benchmarks/cannbench/benchmark_results.json` 中 `apply_adam_w` 条目：workflow/review/build/correctness/performance/artifacts 均指向实际证据；汇总计数必须由所有 operator 当前状态重新计算，不能只手改一个数字。

## 7. 已知风险与决策记录

| 风险/决策 | 处理 |
|---|---|
| 环境字面型号与实测 NpuArch 有冲突 | 构建前复探；只接受实测 DAV_2201，异常即回退设计 |
| FP16/BF16 复杂链路精度 | 全程 FP32 计算，最终一次 CAST_RINT；按 proto 专用阈值验收 |
| Sqrt(0)、NaN、Inf | case 12～14 为强制真实 NPU 门禁，不基于 simulator 推断 |
| 大 case 内存 | 四输入顺序 H2D；及时释放 CPU/NPU 临时对象；不得用较小 shape 替代 case 5/9 |
| 非对齐尾部越界 | 所有 GM↔UB 尾块统一 DataCopyPad，有效 byte length 单独传递 |
| 单缓冲限制性能 | 四输入双缓冲预取在 DAV_2201 实测触发 Queue/event 死锁，已回退；保持正确单缓冲并在 README 明确限制，后续需专门 event 资源设计 |
| case note 与 attrs 冲突 | 以 CSV attrs 执行并在结果中保留原 note 与 resolved attrs |
| PyTorch 包装作弊风险 | wrapper 只分配输出和 launch 本 Kernel，不调用 torch/torch_npu 计算 API |

## 8. 完成定义

- [x] clean build 同时产出 `build/apply_adam_w` 与 `build/libapply_adam_w_ops.so`。
- [x] 真实 NPU 直调 20/20 无运行错误、20/20 精度通过。
- [x] PyTorch 自定义库 20/20 调用同一 Kernel 并通过。
- [ ] 独立 Reviewer clean build/运行后给出 PASS 或 PASS WITH NOTES。
- [x] 20/20 case 均有真实 NPU Task Duration、HAP score 和复现命令。
- [x] `docs/precision`、`docs/perf/round_001`、`results.json` 本算子产物一致且可追溯；顶层 JSON 交由总协调器合并。

## 9. Developer 当前门禁记录（2026-08-11）

- ✅ `get_npu_arch.py` 在真实设备输出 `dav-2201`，设备 0 可用。
- ✅ `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TORCH_EXTENSION=ON && cmake --build build -j4` 同时产出直调 executable 与 PyTorch shared library。
- ✅ 官方 `verify_cmake_config.py` 通过全部强制项，Kernel 无禁用的 GM↔UB `DataCopy`/SetValue/GetValue。
- ✅ 直调 20/20 cases 在真实 NPU 运行并按 CANN-Bench `MERE=mean(rel) / MARE=max(rel)` 口径通过；特殊值 Inf/NaN/zero 均一致。
- ✅ case 5 的 Axpy 融合舍入问题改为显式 Muls+Add；修复后 FP32/半精度动态 tile 实测为 9216/6144。
- ✅ PyTorch `torch.ops.npu.apply_adam_w` 20/20 调用同一 Kernel 并通过。
- ✅ msprof 20 cases × 5 repeats 全部采集成功；每 case 取目标 Kernel Task Duration 中位数。
- ✅ `results.json` 正好 20 个唯一 case；修复后 correctness=20/20。旧 round_001 分数保留为 pre-fix 证据，当前 operator_score 置 null，避免将旧性能冒充修复版。

已执行的复现命令：

```bash
cd /workspace/tmp/Aprof/benchmarks/cannbench/operators/apply_adam_w
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TORCH_EXTENSION=ON
cmake --build build -j4
bash run.sh --all --device 0
python3 scripts/test_torch.py --all --device 0
python3 scripts/profile_cases.py --all --device 0 --warmup 3 --repeat 5 --output docs/perf/round_001
python3 scripts/score_cases.py --perf docs/perf/round_001 --metadata ../../../../third_party/cann-bench/tasks/metadata/910b2.json --output results.json
```

归档：`docs/precision/{cases.json,summary.txt}`、`docs/perf/round_001/case_XX/{repeat_YY/,performance.json}`、`docs/perf/round_001/summary.txt`、`results.json`。顶层 `benchmarks/cannbench/benchmark_results.json` 由 24 算子总协调器在 Reviewer 验收后统一合并。

## 10. Round 0 审查修复（Step 5a）

- [x] M1：实现 SafeSqrt/SafeDiv；Compare count 256B 对齐，Select 模式 1/2 保留 8KB UB，TilingData 携带 quiet NaN/±Inf bit pattern。
- [x] M1：真机 smoke 覆盖负 `v_hat`、0/0、非零/0，并规避 A2 上 NaN `NE` 比较的不可靠语义。
- [x] M2：全部 GM↔UB 搬运改为五字段 `DataCopyExtParams`；`blockLen` clamp 从 2097151 字节上限公式推导。
- [x] M2：删除固定 8192；Host 按运行时 UB、buffer、mask、8KB Select 临时区和 2KB reserve 动态搜索最大 tile。
- [x] 持久化 smoke 11/11：Level0 8/16、step 2/100、beta near 1、负 v_hat、零分母、最小 shape、8D、非法 step/beta/dtype。
- [x] README：补数学公式、API 映射/约束、已知限制；environment.md 修正为 NPU Name 9362 + dav-2201 运行时证据。
- [x] 修复后真实 NPU device 1：直调 20/20、PyTorch 20/20、smoke 11/11。
- [x] 修复后代表性能 round_002：case 1=37.339us、case 5=517.43us、case 9=764.024us，各 5 repeats。
- [x] 双缓冲探索已停止：四输入预取在 A2 真机触发 Queue/event 死锁，未保留不安全代码；最终实现恢复单缓冲。
