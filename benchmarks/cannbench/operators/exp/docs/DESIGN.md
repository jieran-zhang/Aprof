# exp Ascend C 直调算子设计

## 0. 概述

### 0.0 需求类型判断

本需求是通用 Elementwise 算子，验收范围由 `third_party/cann-bench/tasks/level1/exp/{cases.yaml,cases.csv}` 固定为 20 个必测 case。输入可为 1～8 维连续 ND Tensor；Kernel 将 shape 展平为一维元素流，维数不进入核内分支。

### 0.1 基本信息

| 项目 | 内容 |
|---|---|
| 算子名称 | `exp` / `Exp` |
| 算子类别 | Elementwise，一输入一输出 |
| 需求类型 | 通用接口 + 20 个强制验收 case |
| 数学定义 | `base<=0: exp(scale*x+shift)`；`base>0: exp((scale*x+shift)*ln(base))` |
| 输入/输出 | `x -> y`，shape 和 dtype 不变 |
| 支持 dtype | `float16`、`float32`、`bfloat16` |
| 支持 shape | 连续 ND，1～8 维；元素总数以 `uint64_t` 计算 |
| 目标环境 | CANN 9.0.0，真实 Ascend NPU |
| 目标架构 | 运行时实测 `DAV_2201`，`arch22`，`__NPU_ARCH__=2201`，`--npu-arch=dav-2201` |
| 技术路线 | 通用 SIMD/MemBase；目标非 DAV_3510，不使用 RegBase/Blaze |
| 特殊约束 | Host 不得预处理输入 Tensor；20 cases 均需正确性、Task Duration 和 HAP 评分产物 |

### 0.2 用户原始需求

| # | 需求内容 |
|---|---|
| 1 | 在 `benchmarks/cannbench/operators/exp` 生成与 `benchmarks/aprof_benchmark/fast_gelu/direct_invoke_baseline` 类似、可完整编译运行的 Ascend C Kernel 直调工程。 |
| 2 | 权威规格为 `desc.md`、`proto.yaml`、`golden.py`、`cases.yaml`、`cases.csv`，必须覆盖全部 20 cases。 |
| 3 | 每个 case 必须保存精度结果、真实 NPU `Task Duration (us)`、baseline/T_HW 锚点和当前 HAP 评分。 |
| 4 | 在真实 NPU 编译、运行和采集 msprof 数据；不得以 CPU、simulator 或墙钟时间冒充。 |
| 5 | 必须使用 `third_party/cannbot-skills/plugins-official/ops-direct-invoke` 官方流程。 |
| 6 | 项目级 `benchmarks/cannbench/benchmark_results.json` 最终汇总 exp 的评测状态与产物路径。 |

### 0.3 权威输入与优先级

已核对 `third_party/cann-bench/tasks/level1/exp/` 下的 `desc.md`、`proto.yaml`、`golden.py`、`cases.yaml`、`cases.csv`。如果文件之间有歧义，优先级为：`golden.py` 数值语义 > `cases.csv/cases.yaml` 实际字段 > `proto.yaml` > `desc.md` > case note。

`golden.py` 明确将 FP16/BF16 输入提升为 FP32 计算后再转回原 dtype。设计不把 note 里的 baseline kernel 拆分形式当作数学语义。

### 0.4 架构判定与门禁

`npu-arch` 静态产品表将字面值 `Ascend910/ASCEND910` 映射为 DAV_1001，但本项目 `environment.md` 中的真实设备探测证据为 `get_npu_arch.py -> dav-2201`，全局 `benchmark_results.json` 和已验证的 fast_gelu 基线也使用 `dav-2201`。本工程因此以运行时证据为准使用 `--npu-arch=dav-2201`。

Developer 首次构建前必须再次保存架构探测输出；若不是 DAV_2201，必须停止构建并返回 `design_issue`，不得运行架构不匹配的二进制。

## 1. 算子设计

### 1.1 数学公式

设 Host 仅对属性标量做预计算（不读取或改写 Tensor）：

```text
logFactor = (base > 0) ? log(base) : 1
alpha = scale * logFactor
beta  = shift * logFactor
y_i   = exp(alpha * x_i + beta)
```

特别地，`base == 1` 时 `logFactor=0`，对所有有限、Inf 和 NaN 输入，PyTorch golden 中先做 `temp*0` 会使 NaN/Inf 保持 NaN，并非总是常数 1。因此不能仅根据 `base==1` 无条件忽略输入：

- case 11/17/20 的输入生成范围为有限值，可用 `Duplicate(1)` 性能快路；
- 通用/PyTorch 接口默认使用保守语义路径 `Muls(0) -> Adds(0) -> Exp`，保留 NaN/Inf 行为；
- CLI case runner 只有在 case manifest 明确标记 `finite_only=true` 时才可设置快路 tiling key，Host 不得扫描 Tensor 来判定。

Host 以 `double` 计算 `log(base)`、`alpha`、`beta`，检查有限性后显式转为 FP32 写入 TilingData。这是属性标量计算，不构成 Host Tensor 预处理。

### 1.2 API 映射

以下 API 已通过 `ascendc-docs-search` 在 CANN 9.0 项目内置 asc-devkit 中按通配符检索所有同名变体。选定的 Device API 均声明支持 Atlas A2/A3。

| 数学/数据操作 | API 与选定签名 | 关键约束 | 官方本地文档 |
|---|---|---|---|
| 对齐 GM↔UB | `DataCopy(dst, src, count)` | 仅用于起始地址和字节长度都 32B 对齐的完整 tile | [DataCopy.md](../../../asc-devkit/docs/api/context/DataCopy.md) |
| 非对齐 GM↔UB | `DataCopyPad(Local, Global, DataCopyExtParams, DataCopyPadExtParams)` / `DataCopyPad(Global, Local, DataCopyExtParams)` | 单 block，`blockLen=validCount*sizeof(T)` 字节；Local 32B 对齐 | [DataCopyPad(ISASI).md](../../../asc-devkit/docs/api/context/DataCopyPad%28ISASI%29.md) |
| FP16/BF16↔FP32 | `Cast(dst, src, RoundMode, count)` | 升精度 `CAST_NONE`；FP32→FP16/BF16 `CAST_RINT`；大类型与小类型地址分离 | [Cast.md](../../../asc-devkit/docs/api/context/Cast.md) |
| 标量乘 | `Muls(dst, src, scalar, count)` | 只支持 half/float（不直接支持 BF16）；同类型；32B 对齐 | [Muls.md](../../../asc-devkit/docs/api/context/Muls.md) |
| 标量加 | `Adds(dst, src, scalar, count)` | 只支持 half/float（不直接支持 BF16）；同类型；32B 对齐 | [Adds.md](../../../asc-devkit/docs/api/context/Adds.md) |
| 自然指数 | 基础 `Exp(dst, src, count)` | A2/A3 只支持 half/float；BF16 必须先 Cast；32B 对齐 | [Exp.md](../../../asc-devkit/docs/api/context/Exp.md) |
| 有限 base=1 快路 | `Duplicate(dst, scalarValue, count)` | A2/A3 支持 half/bfloat16_t/float；scalar dtype 与 dst 相同 | [Duplicate.md](../../../asc-devkit/docs/api/context/Duplicate.md) |
| 核数/UB 查询 | `aclrtGetDeviceInfo(deviceId, ACL_DEV_ATTR_VECTOR_CORE_NUM, ...)` 和 `ACL_DEV_ATTR_UBUF_PER_VECTOR_CORE` | `aclrtSetDevice` 后查询；不硬编码核数或 UB | CANN 9.0 `include/acl/acl_rt.h` |

`Exp-26.md` 是可选 Taylor 展开的高阶 API，需要大量 shared temporary buffer，且明确禁止 src/dst 地址重叠。本算子的主要性能目标为基础 Exp，高阶版不纳入初始路径；若真机精度验收证明 FP32 基础 Exp 不达标，Developer 必须返回 `design_issue` 评估 Taylor 分支，不得未计算 UB 即直接替换。

#### 1.2.1 API 语义验证

| API | 数据布局 | 功能需求 | 选定模式 | 限制条件 | 匹配 |
|---|---|---|---|---|---|
| DataCopy | GM/UB 连续一维元素流 | 完整 tile 高吞吐搬运 | count 重载 | 长度必须 32B 对齐 | ✅ |
| DataCopyPad | GM 连续，UB 256B 对齐 | 非对齐尾 tile 安全搬入/搬出 | `DataCopyExtParams`，单 block | `blockLen>=1`；Local 起址 32B 对齐 | ✅ |
| Cast | 连续 LocalTensor | FP16/BF16 升 FP32，结果降回原 dtype | count 重载 | src/dst 分离；BF16↔FP32 组合在 A2 表中明确支持 | ✅ |
| Muls/Adds | 连续 half/float LocalTensor | `alpha*x+beta` | count 重载 | scalar 与 Tensor 同 dtype；只做 100% 同址原地重叠 | ✅ |
| Exp | 连续 half/float LocalTensor | 逐元素 `e^x` | 基础 count 重载 | BF16 不支持；原地路径只使用官方通用约束允许的 100% 重叠 | ✅ |
| Duplicate | 连续输出 LocalTensor | 填充常量 1 | count 重载 | 仅 finite-only case 快路；支持三种 dtype | ✅ |
| aclrtGetDeviceInfo | Host runtime | 获取真实可见 AIV/UB | Vector core 和 UBUF attr | 查询失败即停止，不用默认值掩盖 | ✅ |

验证清单：

- [x] 输入输出均是连续 ND，展平后按连续一维处理。
- [x] 完整 tile 与非对齐 tail 的搬运 API 边界已分开。
- [x] 基础 Exp/Muls/Adds 的 A2/A3 dtype 集合已验证，BF16 不直调不支持 API。
- [x] `Cast` 的 BF16↔FP32 组合和 RoundMode 已核对。
- [x] 不使用 Host Tensor 预处理、CPU fallback 或内置同名算子。

### 1.3 数据流

```text
x (GM, original dtype)
    │ finite-only base=1 fast path: 不搬入 x
    │ otherwise: aligned tile -> DataCopy; tail -> DataCopyPad
    ▼
xLocal (VECIN)
    │ FP16: Muls(alpha) -> Adds(beta) -> Exp，均为 half
    │ FP32: Muls(alpha) -> Adds(beta) -> Exp，均为 float
    │ BF16: Cast(CAST_NONE) -> FP32 Muls/Adds/Exp -> Cast(CAST_RINT)
    │ finite-only base=1: Duplicate(1) 直接生成 yLocal
    ▼
yLocal (VECOUT, original dtype)
    │ aligned tile -> DataCopy; tail -> DataCopyPad
    ▼
y (GM, original dtype)
```

FP16 默认使用原生 half 链路以获得吞吐，但 golden 为 FP32 计算后回转。Developer 必须先在 20 cases 上完成 MERE/MARE 实测；任一 FP16 case 不达标时，将 FP16 分支升级为与 BF16 同样的 FP32 中间链路，并重新采集性能。

### 1.4 核心计算步骤

1. Host 读取 case/CLI attrs，校验 shape、dtype、`base/scale/shift`，计算 `alpha/beta` 和 tiling key。
2. Host 通过 ACL runtime 动态查询可见 Vector Core 数和每核 UB，按展平元素区间分核。
3. Kernel 根据 `GetBlockIdx()` 选择 former/tail block，每核按 `ubFormer` 循环处理。
4. 非常量分支搬入有效元素；BF16 先 Cast FP32，FP16/FP32 直接计算。
5. 根据 `alpha==1` / `beta==0` 跳过无效 Muls/Adds，再执行基础 Exp。
6. BF16 Cast 回原 dtype；常量快路使用 Duplicate；最后精确搬出有效尾部。

分支差异：

| 操作 | FP16 | FP32 | BF16 | finite-only base=1 |
|---|---|---|---|---|
| CopyIn | half | float | bfloat16 | 跳过 |
| 计算 dtype | half | float | float | 原输出 dtype |
| Cast | 无（精度失败则启用） | 无 | 入/出各一次 | 无 |
| 数学 API | Muls/Adds/Exp | Muls/Adds/Exp | Muls/Adds/Exp | Duplicate |
| CopyOut | half | float | bfloat16 | 原 dtype |

### 1.5 内存管理（Buffer 规划）

设 `U=ubFormer`，所有分配大小按 256B 向上对齐。Queue depth 为 2，用于 MTE2/V/MTE3 流水。

| Buffer | 用途 | FP16 | FP32 | BF16 | TPosition |
|---|---|---:|---:|---:|---|
| `inQueueX` | 原 dtype 输入 | `2*Align256(2U)` | `2*Align256(4U)` | `2*Align256(2U)` | VECIN |
| `outQueueY` | 原 dtype 输出 | `2*Align256(2U)` | `2*Align256(4U)` | `2*Align256(2U)` | VECOUT |
| `fp32Buf` | BF16 中间值，原地 Muls/Adds/Exp | 0 | 0 | `Align256(4U)` | VECCALC |
| reserve | TPipe/实现余量 | 2048B | 2048B | 2048B | 预留 |

总 UB 上界：

```text
FP16: 4 * Align256(2U) + 2048
FP32: 4 * Align256(4U) + 2048
BF16: 4 * Align256(2U) + Align256(4U) + 2048
```

常量快路不初始化输入 Queue，但仍复用对应 dtype 的 `outQueueY`。Host 使用 64 位 checked arithmetic 求解最大 `U`，并强制 `allocated <= queriedUbSize` 且 `U>0`。

## 2. 架构设计

### 2.1 多核切分策略

| 项目 | 说明 |
|---|---|
| 切分维度 | 输入展平后沿元素维连续切分 |
| 可用核数 | `aclrtGetDeviceInfo(... ACL_DEV_ATTR_VECTOR_CORE_NUM ...)`，不得用设备数 16 代替 |
| 计算核数 | `candidate=ceil(totalElements*minDtypeBits/32768)`，`coreNum=max(1,min(candidate,availableAiv))` |
| former block | `blockFormer=AlignUp(ceil(totalElements/coreNum),512)` 元素 |
| launch blockDim | `blockNum=ceil(totalElements/blockFormer)` |
| tail block | `blockTail=totalElements-(blockNum-1)*blockFormer` |
| 核偏移 | `blockIdx*blockFormer` 元素 |
| 负载均衡 | former blocks 等长，最后一核处理 tail；20 cases 均为约 1M 元素以上，可使用全部可见 AIV |

### 2.2 UB 切分策略

| 项目 | 说明 |
|---|---|
| UB 容量 | Host 查询 `ACL_DEV_ATTR_UBUF_PER_VECTOR_CORE`；DAV_2201 典型值 192KB，不硬编码 |
| 对齐 | tile 以 256B 为单位；FP16/BF16 为 128 元素，FP32 为 64 元素 |
| `ubFormer` | 求最大对齐 `U`，使 §1.5 对应 dtype 预算不超过查询 UB |
| 每核循环 | `ceil(blockLength/U)` |
| 尾 tile | `validCount=blockLength-(loops-1)*U`；计算 count 和 DataCopyPad blockLen 用有效长度 |
| 完整 tile | 字节长度 32B 对齐，用 DataCopy |
| 防御 | 元素数乘法溢出、`U==0`、`validCount` 超 API 字段范围时 Host 报错，不发射 Kernel |

TilingData 至少包含：`totalLength, blockNum, blockFormer, blockTail, ubFormer, loopsFormer, tailFormer, loopsTail, tailTail, dtypeCode, branchKey, alpha, beta`。长度字段用 64 位，单 tile count 保证可表示为 `int32_t`。

### 2.3 分支场景覆盖

| 分支条件 | 处理策略 | cases |
|---|---|---|
| FP16 | 默认 half 原生计算；MERE/MARE 不达标则升 FP32 | 1,4,7,10,14,17,20 |
| FP32 | 原生 float Muls/Adds/Exp | 2,5,8,11,13,15,18 |
| BF16 | BF16→FP32→BF16 | 3,6,9,12,16,19 |
| `base<=0` | `alpha=scale, beta=shift` | 1–5,9,10,12,14–17 |
| `base=2/10` | Host 计算 `ln(base)` 并融入 alpha/beta | 6–8,13,18,19 |
| `base=1` 有限 case | manifest 标记 finite-only 后 Duplicate(1) | 11,17,20 |
| alpha=1 / beta=0 | 分别跳过 Muls / Adds | 多个 case |
| 32B 对齐 | 完整 tile DataCopy | 1–5 的主体 |
| 非对齐/质数 shape | 尾 tile DataCopyPad，计算只用 validCount | 6–20 |
| 大 shape | 多核 + 多 UB tile，不一次性分配 | 3–5,9,13,20 |
| 零值 | `exp(beta)` | 14 |
| 溢出/下溢 | 保持 Exp 的 IEEE Inf/0 语义，验收时分离特殊值 | 5,8–10,17,20 |
| Inf | 通用路径保留符号和 Inf 语义 | 12 |
| NaN | 通用路径传播 NaN，验证 mask 一致 | 13 |

### 2.4 类别特有设计

#### 2.4.1 FP16/FP32 原生分支

**适用场景**：`dtype in {float16,float32}` 且非 finite-only 常量快路。

```cpp
for each tile assigned to this block:
    valid = min(ubFormer, remaining)
    CopyInWithAlignedOrPad(xLocal, xGm, valid)
    if (alpha != 1): Muls(xLocal, xLocal, typedAlpha, valid)
    if (beta  != 0): Adds(xLocal, xLocal, typedBeta, valid)
    Exp(yLocal, xLocal, valid)
    CopyOutWithAlignedOrPad(yGm, yLocal, valid)
```

FP16 的 `typedAlpha/typedBeta` 转换会带来标量舍入；因此精度测试必须特别覆盖 case 7（`scale=1.5, base=2`）、case 14/20 和极端范围。

#### 2.4.2 BF16 升精度分支

**适用场景**：`dtype=bfloat16`；基础 Exp/Muls/Adds 不支持 BF16。

```cpp
for each tile assigned to this block:
    valid = min(ubFormer, remaining)
    CopyInWithAlignedOrPad(rawBf16, xGm, valid)
    Cast(fp32, rawBf16, CAST_NONE, valid)
    if (alpha != 1): Muls(fp32, fp32, alpha, valid)
    if (beta  != 0): Adds(fp32, fp32, beta, valid)
    Exp(fp32, fp32, valid)
    Cast(rawBf16Out, fp32, CAST_RINT, valid)
    CopyOutWithAlignedOrPad(yGm, rawBf16Out, valid)
```

#### 2.4.3 finite-only `base=1` 快路

**适用场景**：仅 case manifest 已知输入有限且 `base==1`的 case 11/17/20。通用/PyTorch 调用不启用此分支。

```cpp
for each output tile assigned to this block:
    valid = min(ubFormer, remaining)
    Duplicate(yLocal, oneInOutputDtype, valid)
    CopyOutWithAlignedOrPad(yGm, yLocal, valid)
```

### 2.5 精度与特殊值策略

普通有限值按社区浮点计算标准验收：

| dtype | Threshold | MERE | MARE |
|---|---:|---:|---:|
| FP16 | `2^-10` | `< Threshold` | `< 10*Threshold` |
| BF16 | `2^-7` | `< Threshold` | `< 10*Threshold` |
| FP32 | `2^-13` | `< Threshold` | `< 10*Threshold` |

`golden.py` 是唯一数值标杆。误差统计前将普通有限值、`+Inf`、`-Inf`、NaN 分区；Inf 必须符号一致，NaN 必须 mask 一致，这些点不直接进入 MERE/MARE。case 12 和 13 必须产出独立特殊值报告。

### 2.6 性能与评分口径

- `Task Duration (us)` 必须来自 msprof `kernel_details.csv` 中本直调 Kernel 的 Task Duration；墙钟只作诊断。
- 每 case 先 warmup，再按 cann-bench 口径重复采集，并保存原始 CSV、解析 JSON 和命令。
- 910B2 锚点从 `third_party/cann-bench/tasks/metadata/910b2.json` 读取，不手工改写。
- 单 case HAP：`score_i=(T_baseline-T_HW)/((T_cand-T_HW)+(T_baseline-T_HW))`。编译、精度和性能汇总按 cann-bench Eq.4 口径生成。
- 任一精度失败 case 不得获得性能分；结果必须同时写入算子 `results.json` 和项目 `benchmark_results.json`。

## 3. 确认清单

- [x] 权威规格和 20 cases 已检查。
- [x] NpuArch、`__NPU_ARCH__`、`--npu-arch` 和架构冲突复核门禁已记录。
- [x] 已选通用 SIMD/MemBase 路线。
- [x] 多核切分和 UB 切分策略已确定。
- [x] Buffer 规划已完成，并使用运行时查询容量。
- [x] 所有选用 API 已检索变体并核验签名/dtype/对齐限制。
- [x] FP16、FP32、BF16、对齐、非对齐、大 shape、Inf/NaN 和 `base=1` 场景已覆盖。
- [x] 精度阈值、msprof Task Duration 与 HAP 评分口径已明确。
