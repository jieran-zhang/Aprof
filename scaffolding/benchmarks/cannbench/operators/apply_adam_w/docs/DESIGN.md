# apply_adam_w Ascend C 直调算子设计

## 0. 概述

### 0.0 需求类型判断

本需求是通用算子需求，但验收范围被 `third_party/cann-bench/tasks/level2/apply_adam_w/cases.csv` 固定为 20 个必测用例。实现必须支持 1～8 维连续 ND Tensor；Kernel 将 shape 展平为一维元素流，因此维数不进入核内计算分支。

### 0.1 基本信息

| 项目 | 内容 |
|---|---|
| 算子名称 | `apply_adam_w` / `ApplyAdamW` |
| 算子类别 | FusedComposite；四输入逐元素融合链路 |
| 需求类型 | 通用接口 + `cases.csv` 20 个强制验收用例 |
| 输入/输出 | `var, grad, m, v -> y`；shape、dtype 均一致 |
| 支持数据类型 | `float32`、`float16`、`bfloat16`；半精度输入在核内升为 FP32 计算 |
| 支持 shape | 连续 ND，1～8 维；总元素数用 `uint64_t` 表示 |
| 目标环境 | CANN 9.0.0，真实 Ascend NPU |
| 目标架构 | 运行时探测 `DAV_2201`，`arch22`，`__NPU_ARCH__=2201`，编译参数 `--npu-arch=dav-2201` |
| 技术路线 | 通用 SIMD/MemBase；目标不是 DAV_3510，不采用 RegBase/Blaze |
| 特殊约束 | 不更新输入 `m/v/var`，只产生 `y`；Host 不得预处理输入 Tensor；性能必须来自真实 NPU 的 msprof Task Duration |

### 0.2 用户原始需求

| # | 需求内容 |
|---|---|
| 1 | 在 `benchmarks/cannbench/operators/apply_adam_w` 生成与 `benchmarks/aprof_benchmark/fast_gelu/direct_invoke_baseline` 类似、可完整编译和运行的 Ascend C Kernel 直调工程。 |
| 2 | 权威规格为 `desc.md`、`proto.yaml`、`golden.py`、`cases.yaml`、`cases.csv`；必须覆盖 `cases.csv` 全部 20 个 cases。 |
| 3 | 逐 case 保存正确性、Task Duration、性能评分以及可复现命令，最终汇总到 `benchmarks/cannbench/benchmark_results.json`。 |
| 4 | 必须在真实 NPU 编译、运行和采集性能；禁止用 CPU 或 simulator 数据冒充 NPU 数据。 |
| 5 | 必须按官方 `third_party/cannbot-skills/plugins-official/ops-direct-invoke` 工作流开发。 |
| 6 | 数学语义、默认 `step=1`、`maximize`、epsilon 在 sqrt 外部等行为必须和任务目录中的 `golden.py` 一致。 |

### 0.3 权威输入与冲突处理

已完整读取以下文件：

- `third_party/cann-bench/tasks/level2/apply_adam_w/desc.md`
- `third_party/cann-bench/tasks/level2/apply_adam_w/proto.yaml`
- `third_party/cann-bench/tasks/level2/apply_adam_w/golden.py`
- `third_party/cann-bench/tasks/level2/apply_adam_w/cases.yaml`
- `third_party/cann-bench/tasks/level2/apply_adam_w/cases.csv`

发生歧义时采用如下优先级：`golden.py` 数学行为 > `cases.csv` 的实际字段 > `proto.yaml` 接口与精度配置 > `desc.md` 说明文字 > case `note`。例如 case 5 的 note 写有 `lr=1.0-wd=1.0`，但 CSV/YAML attrs 都是 `lr=0.1, weight_decay=0.1`，执行时必须使用 attrs。case 5 的 “268M” 指四个 FP16 输入约 268 MB，而单 Tensor 实际为 33,554,432 个元素。

### 0.4 架构判定与风险门禁

`npu-arch` 的静态产品表把字面 `Ascend910/ASCEND910` 映射为 DAV_1001，但本项目环境报告中的实际探测证据为 `get_npu_arch.py -> dav-2201`，且全局 benchmark manifest 也记录 `dav-2201`。本工程按实测架构生成 `--npu-arch=dav-2201`。Developer 在首次构建前必须再次保存探测输出；若再次探测不是 DAV_2201，应停止构建并回退设计，不能把 DAV_2201 二进制运行到其他架构。

## 1. 算子设计

### 1.1 数学公式

对每个元素独立计算：

```text
m_new = beta1 * m + (1 - beta1) * grad
v_new = beta2 * v + (1 - beta2) * grad * grad
m_hat = m_new / (1 - beta1 ** step)
v_hat = v_new / (1 - beta2 ** step)
adaptive = m_hat / (sqrt(v_hat) + epsilon)
update = adaptive + weight_decay * var
y = var + lr * update,  maximize = true
y = var - lr * update,  maximize = false
```

`epsilon` 位于 `sqrt(v_hat)` 外部。`maximize` 只决定最终 `lr * update` 的符号，完全遵循任务 `golden.py`；不得擅自替换成其他 AdamW 变体。Host 只计算标量 `inv_bias1 = 1/(1-beta1^step)`、`inv_bias2 = 1/(1-beta2^step)` 和 `signed_lr`，不读取、不转换、不改写输入 Tensor。标量计算契约固定为：将 attrs 提升为 `double`，按 `pow(double beta, int64_t step)`、`1.0-power` 的顺序求 bias denominator，检查 denominator 有限且大于 0，再显式转为 `float biasDenom`，最后执行一次 `float invBias = 1.0f / biasDenom` 写入 TilingData。测试同时保存 double denominator、float denominator 和 float reciprocal，便于区分 Host 标量舍入与 Kernel 误差。

参数前置校验：四输入 shape/dtype 相同；`step >= 1`；`0 <= beta1,beta2 < 1`；`lr, weight_decay, epsilon` 位于接口支持范围。case 数据保证初始 `v >= 0`；Kernel 仍显式处理计算后 `v_hat` 的零值、负值和 NaN，并显式规避 `Div` 的零分母，不能依赖 `Sqrt/Div` 对文档未承诺输入域的硬件行为。

### 1.2 API 映射

下列 API 已在项目自带 CANN 9.0 asc-devkit 文档中核验，文档均声明支持 Atlas A2/A3。实现只使用“Tensor 前 n 个数据计算”重载，以 `validCount` 精确限定尾块。

| 数学/数据操作 | 对应 API 与签名要点 | 数据布局与限制 | 官方本地文档 |
|---|---|---|---|
| 非对齐 GM↔UB | `DataCopyPad(Local, Global, DataCopyExtParams, DataCopyPadExtParams)`；`DataCopyPad(Global, Local, DataCopyExtParams)` | 仅通过 VECIN/VECOUT depth=1 Queue 搬运；`blockLen` 单位为字节 | [DataCopyPad(ISASI).md](../../../../../third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/DataCopyPad%28ISASI%29.md) |
| FP16/BF16↔FP32 | `Cast(dst, src, RoundMode, count)` | FP16/BF16→FP32 用 `CAST_NONE`；FP32→FP16/BF16 用 `CAST_RINT`；src/dst 分离 | [Cast.md](../../../../../third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/Cast.md) |
| Tensor×标量 | `Muls(dst, src, float scalar, int32_t count)` | FP32 LocalTensor，32B 对齐；src/dst 完全重叠可原地计算 | [Muls.md](../../../../../third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/Muls.md) |
| dst += scalar×src | `Muls(tmp, src, scalar, count)` + `Add(dst,dst,tmp,count)` | 显式分步舍入，与权威 PyTorch golden 一致；避免 Axpy 融合舍入在近零位置产生 1 ULP 偏差 | [Muls.md](../../../../../third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/Muls.md)、[Add.md](../../../../../third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/Add.md) |
| grad² | `Mul(dst, src0, src1, int32_t count)` | FP32；`dst=src0=src1` 100% 重叠，无部分重叠 | [Mul.md](../../../../../third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/Mul.md) |
| 安全域 mask | `CompareScalar(mask, src, scalar, CMPMODE, alignedCount)`；`Compare(mask,src0,src1,CMPMODE,alignedCount)` | FP32→bit-packed uint8；count 对应字节数必须 256B 对齐 | [CompareScalar.md](../../../../../third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/CompareScalar.md)、[Compare.md](../../../../../third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/Compare.md) |
| 安全值/特殊值选择 | `Select(..., VSEL_TENSOR_SCALAR_MODE/ VSEL_TENSOR_TENSOR_MODE, count)` | 模式 1/2 在 A2 需额外预留 8KB UB | [Select.md](../../../../../third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/Select.md) |
| 构造安全 Tensor | `Duplicate(dst, float scalar, count)` | 用于 `FLT_MIN`/±Inf/NaN 中间值 | [Duplicate.md](../../../../../third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/Duplicate.md) |
| sqrt(v_hat) | `Sqrt(dst, src, int32_t count)` | 只接收经 Select 替换后的严格正有限/NaN 输入，不直接接收零/负值 | [Sqrt.md](../../../../../third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/Sqrt.md) |
| +epsilon | `Adds(dst, src, float scalar, int32_t count)` | FP32；原地完全重叠 | [Adds.md](../../../../../third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/Adds.md) |
| m_hat/denom | `Div(dst, src0, src1, int32_t count)` | FP32；零分母先替换成 1，Div 后再按 mask 恢复 IEEE ±Inf/NaN | [Div.md](../../../../../third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/Div.md) |
| 最终 var±update | `Add(dst, src0, src1, int32_t count)` | FP32；结果写独立 VECOUT Queue（FP32）或 bufA（半精度） | [Add.md](../../../../../third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/Add.md) |

检索时已用通配符检查同名前缀变体。`AddRelu*`、`AddDeqRelu`、`MulCast`、Matmul tiling helper 等变体与本算子语义或 dtype 不匹配，未选用；`Axpy.md`、`Axpy-25.md`、`Axpy接口.md` 均已检查，高级 `Axpy-25.md` 需要 shared temporary buffer，本设计选用基础 `Axpy.md`。API 链接直接指向官方 plugin 的 asc-devkit；`benchmarks/cannbench/asc-devkit` 虽是同一目录的有效符号链接，但不再作为证据路径。

#### 1.2.1 API 语义验证

| API | 数据布局 | 功能需求 | 选定签名/模式 | 限制条件 | 匹配 |
|---|---|---|---|---|---|
| DataCopyPad | GM 中连续 ND 字节流；UB 32B 对齐 | 任意元素数尾块安全搬入/搬出 | 单 block，`blockLen=validCount*sizeof(T)`，stride=0 | `blockLen>=1`；Local 32B 对齐 | ✅ |
| Cast | 连续 LocalTensor | 半精度输入升 FP32、输出降回原 dtype | count 重载；升精度 `CAST_NONE`，降精度 `CAST_RINT` | src/dst 分离，均 32B 对齐 | ✅ |
| Muls/Adds/Sqrt | 连续 FP32 LocalTensor | 标量乘/加与一元 sqrt | count 重载 | count 为有效元素数，完全原地重叠 | ✅ |
| Muls+Add | 连续 FP32 LocalTensor | 显式 `tmp=scalar*src; dst=dst+tmp` | count 重载 | tmp 独立；完整重叠仅用于允许的原地输入 | ✅ |
| Mul | 连续 FP32 LocalTensor | grad 原地平方 | count 重载 | 三者同址为 100% 重叠，不允许部分重叠 | ✅ |
| Div | 连续 FP32 LocalTensor | m_hat 除以 denom | count 重载 | src1 分母独立；dst 与 src0 完全重叠 | ✅ |
| Add | 连续 FP32 LocalTensor | var 加 signed update | count 重载 | dst 与 src0 完全重叠，src1 独立 | ✅ |
| Compare/CompareScalar | 连续 FP32，mask bit-packed | 识别 `<=0/==0/>=0/!=0` 以及 `x==x` ordered 检查 | count 重载，`cmpCount=AlignUp(valid,64)` | `cmpCount*4` 为 256B 倍数；mask `Align256(cmpCount/8)` | ✅ |
| Select/Duplicate | 连续 FP32 + bit mask | Sqrt/Div 安全域替换及特殊值恢复 | Select 模式1/2 + Duplicate count 重载 | 额外固定预留 8KB；不使用部分重叠 | ✅ |

验证清单：

- [x] 数据布局、连续性和 32B 对齐要求已确认。
- [x] 所有 API 均查阅 CANN 9.0 本地文档并核验 A2/A3 支持。
- [x] FP16/BF16 的核心计算统一为 FP32，避开基础算术 API 不直接支持 BF16 的限制。
- [x] 所有尾块计算使用有效长度，UB 分配和偏移使用对齐长度。
- [x] 不使用 Host Tensor 预处理、内置同名算子或 CPU fallback。

### 1.3 数据流

```text
var/grad/m/v (GM, original dtype)
    │ FP32: 四个 VECIN Queue(depth=1) 分别 Alloc→DataCopyPad→EnQue→DeQue
    │ FP16/BF16: rawIn VECIN Queue 逐输入 Alloc→Copy→EnQue→DeQue→Cast→Free
    ▼
A=var_fp32, B=grad_fp32, C=m_fp32, D=v_fp32
    │ C=Muls(beta1); E=Muls(B,1-beta1); Add(C,C,E); Muls(C,inv_bias1)
    │ B=Mul(B,B)  // grad²，m_hat 完成后才覆盖 grad
    │ D=Muls(beta2); B=Muls(B,1-beta2); Add(D,D,B); Muls(D,inv_bias2)
    │ B=SafeSqrt(D, mask): 零恢复为0，负数恢复为NaN
    │ B=Adds(B,epsilon)
    │ C=SafeDiv(C,B,mask,D): 零分母不直接送入 Div，显式恢复±Inf/NaN
    │ if weight_decay != 0: E=Muls(A,weight_decay); Add(C,C,E)
    │ C=Muls(C,signed_lr)
    │ A=Add(A,A,C)
    ▼
y_fp32
    │ FP32: 写 VECOUT Queue→EnQue→DeQue→DataCopyPad→Free
    │ FP16/BF16: Cast 到 rawOut VECOUT Queue→EnQue→DeQue→DataCopyPad→Free
    ▼
y (GM, original dtype)
```

该顺序保证构造 `m_hat` 时 grad 尚未被平方覆盖。Queue 的 EnQue/DeQue 建立 MTE2→V 依赖，输出 Queue 建立 V→MTE3 依赖；`rawIn` 必须在每次 Cast 消费完成并 `FreeTensor` 后才能用于下一个输入，不依赖源码语句顺序猜测同步。

### 1.4 核心计算步骤

1. Host 从 CLI/case 描述读取 attrs，计算元素总数、可见 AIV 核数、UB 大小和标量偏差修正值，形成 `ApplyAdamWTilingData`。
2. 按线性元素区间多核切分；Kernel 根据 `GetBlockIdx()` 选择 former/tail block。
3. 每核循环处理 `ubFormer` 大小的 tile，最后一次只处理 `validCount`。
4. 使用 VECIN/VECOUT depth=1 Queue 包装全部 `DataCopyPad`；padding 数据不参与普通计算 count，也不写回 GM。
5. FP16/BF16 在核内 Cast 为 FP32，执行完整 AdamW 融合链路，再 Cast 回原 dtype。
6. FP32 直接计算，避免无意义 Cast。
7. 结果逐 tile 搬出；Host 同步 stream 后落盘或进入正确性/性能采集。

关键设计要点：

- `validCount` 只用于 DataCopyPad 的 `blockLen` 和计算 API 的 count。
- `alignedCount=AlignUp(validCount, 64)`（FP32 256B）只用于 UB 大小和 LocalTensor 切片偏移。
- `step` 的幂和倒数仅是标量 Host 计算，不是对 Tensor 的预处理。
- `weight_decay==0` 时跳过一次 Muls+Add；`maximize` 通过 `signed_lr` 消除核内控制分歧。
- `SafeSqrt/SafeDiv` 仅规避官方文档未定义/警告的输入，随后显式恢复 golden 所需的零、负数、±Inf/NaN 结果；case 12/13 仍按 equal-NaN/Inf 规则验收。

### 1.5 内存管理（Buffer 规划）

设 `U=ubFormer`，`E=sizeof(input dtype)`，主计算类型恒为 FP32。

| Buffer | 用途 | 大小 | TPosition/生命周期 |
|---|---|---:|---|
| `qVar/qGrad/qM/qV` | FP32 输入 | 各 `Align256(U*4)` | 仅 FP32：`TQue<VECIN,1>`，depth=1 |
| `qOut` | FP32 输出 | `Align256(U*4)` | 仅 FP32：`TQue<VECOUT,1>`，depth=1 |
| `qRawVar/qRawGrad/qRawM/qRawV` | FP16/BF16 四路输入 | 各 `Align256(U*2)` | 半精度：独立 `TQue<VECIN,1>` |
| `qRawOut` | FP32 结果 Cast 回原 dtype | `Align256(U*2)` | 半精度：`TQue<VECOUT,1>`，depth=1 |
| `bufA/B/C/D/E` | 半精度分支的 var/grad/m/v FP32 主缓冲及分步 Mul+Add scratch | 各 `Align256(U*4)` | 半精度：`TBuf<VECCALC>`；E 避免 Axpy 融合舍入偏离 golden |
| `maskBuf` | CompareScalar bit-packed mask | `Align256(U/8)` | 两分支：`TBuf<VECCALC>` |
| Select 临时区 | Select 模式1/2 的隐式临时空间要求 | 固定 8192B | 两分支：从 UB 预算中固定扣除 |

总 UB 预算：

```text
FP32:        5 * Align256(U*4) + Align256(U/8) + 8192 + reserve
FP16/BF16:   5 * Align256(U*4) + 5 * Align256(U*2) + Align256(U/8) + 8192 + reserve
reserve:     2048 bytes（仅常数级实现余量，不承接任何整 tile Buffer）
```

FP32 tile 系数为 20B/元素，FP16/BF16 为 30B/元素，另有对齐 mask、8KB Select 临时区和固定 reserve。真实 NPU case 5 发现 Axpy 的融合舍入可在近零位置产生 1 ULP 差异，因此实现使用第五个 FP32 scratch 做显式 Muls+Add。Host 以 64 位无符号整数动态搜索最大合法 `U=64*k`，并按 `DataCopyExtParams::blockLen<=2097151` 推导 API clamp，不使用固定 tile。DAV_2201 UB 通过 ACL attr 查询；当前驱动该 attr 返回 0 时按官方示例回退到 `PlatformAscendCManager::GetCoreMemSize(UB)`。四输入 Queue 的 A2 双缓冲预取实测会触发 event/queue 死锁，已回退为正确的单缓冲组织并列为已知性能限制。

## 2. 架构设计

### 2.1 多核切分策略

| 项目 | 说明 |
|---|---|
| 切分维度 | 四输入共同展平后沿元素维切分 |
| 可用核数 | Host 查询 `ACL_DEV_ATTR_VECTOR_CORE_NUM`；不得用设备数 16 或固定典型核数代替 |
| 计算核数 | `candidate=ceil(totalElements*minDtypeBits/32768)`，`coreNum=max(1,min(candidate,availableAiv))`，保证每核约不少于 4KB 输入 |
| former block | `blockFormer=AlignUp(ceil(totalElements/coreNum),512)` 元素 |
| 实际 block 数 | `blockNum=ceil(totalElements/blockFormer)`；launch blockDim 使用 `blockNum` |
| tail block | `blockTail=totalElements-(blockNum-1)*blockFormer` |
| 核偏移 | `blockOffset=blockIdx*blockFormer` 元素；四输入/输出使用相同偏移 |
| 负载均衡 | former blocks 等长，最后一核处理 tail；20 个 case 的规模足以使用所有可见 AIV 核 |

### 2.2 UB 切分策略

| 项目 | 说明 |
|---|---|
| UB 容量 | 运行时查询；DAV_2201 典型 192 KB |
| 元素对齐 | FP32 主缓冲按 64 元素/256B 对齐 |
| 两分支 tile | 按 FP32 20B/元素、半精度 30B/元素、mask、8KB Select 临时区和 2KB reserve 动态搜索最大 `U=64*k`；当前 192KB UB 实测分别为 9216/6144 元素 |
| 每核循环 | `ceil(blockLength/U)` |
| 尾 tile | `validCount=blockLength-(loops-1)*U`；DataCopyPad 和 count API 均使用 validCount |
| 防御条件 | 若 `U==0` 或 `blockLen` 超过 DataCopyExtParams 范围则 Host 报错，不发射 Kernel |

TilingData 至少包含：`totalLength, blockNum, blockFormer, blockTail, ubFormer, loopsFormer, tailFormer, loopsTail, tailTail, dtypeCode, beta1, beta2, oneMinusBeta1, oneMinusBeta2, biasDenom1, biasDenom2, invBias1, invBias2, weightDecay, epsilon, signedLr, quietNanBits, positiveInfBits, negativeInfBits`。长度字段用 64 位，普通标量用 float，特殊值用固定 `uint32_t` IEEE-754 bit pattern；单 tile count 保证落入 `int32_t`。

### 2.3 分支场景覆盖

| 分支条件 | 处理策略 | 对应用例 |
|---|---|---|
| FP32 | 无 Cast，FP32 全链路 | 1,4,7,10,13,15,18,20 |
| FP16 | 核内 FP16→FP32，结果 FP32→FP16 | 2,5,8,11,14,17 |
| BF16 | 核内 BF16→FP32，结果 FP32→BF16 | 3,6,9,12,16,19 |
| 32B 对齐 shape | former/tail 均可走相同 DataCopyPad 路径 | 1～5 |
| 非对齐/质数 shape | 最后一核、最后 tile 使用有效字节数 | 6～20 |
| `weight_decay=0` | 跳过 weight-decay Axpy | 1,4,8,11～15,18 |
| `maximize=true` | `signedLr=+lr` | 10,20 |
| `maximize=false` | `signedLr=-lr` | 其余用例 |
| `beta1=0` | `oneMinusBeta1=1`，正常公式，无除零 | 9 |
| 大 epsilon | epsilon 仍位于 sqrt 外 | 15 |
| zero + 小 epsilon | SafeSqrt 以正值执行 Sqrt，再按 zero mask 恢复 0 | 14 |
| 负 `v_hat` | SafeSqrt 不把负值送入 Sqrt，显式选择 quiet NaN | 补充 smoke |
| epsilon=0 + 零分母 | SafeDiv 以 1 作安全分母，再根据 numerator 符号恢复 ±Inf/NaN | 补充 smoke |
| Inf/NaN | mask/Select 保持 golden 特殊值语义；equal-NaN/Inf 验收 | 12,13 |
| 1D～5D | 展平处理，无维度分支 | 9,11～14,18～20 |
| 显式 `step>1` / beta near 1 | 按 double→float 契约计算并保存 denominator/reciprocal；覆盖 step=1/2/100 与 beta=0.9999；乘倒数若超阈值则返回 design_issue 改用 denominator Tensor + Div | 评分 cases 默认 step=1 |

### 2.4 类别特有设计

#### 2.4.1 FP32 直算分支

**适用场景**：输入 dtype 为 FP32。

```cpp
for each tile of this block {
    valid = min(ubFormer, blockRemaining);
    // 每个 CopyIn 都使用独立的 depth=1 VECIN Queue；EnQue/DeQue 建立 MTE2→V 依赖。
    A = qVar.AllocTensor<float>();  DataCopyPad(A, varGm[offset], bytes);  qVar.EnQue(A);
    B = qGrad.AllocTensor<float>(); DataCopyPad(B, gradGm[offset], bytes); qGrad.EnQue(B);
    C = qM.AllocTensor<float>();    DataCopyPad(C, mGm[offset], bytes);    qM.EnQue(C);
    D = qV.AllocTensor<float>();    DataCopyPad(D, vGm[offset], bytes);    qV.EnQue(D);
    A=qVar.DeQue<float>(); B=qGrad.DeQue<float>(); C=qM.DeQue<float>(); D=qV.DeQue<float>();
    E = qOut.AllocTensor<float>();

    Muls(C, C, beta1, valid);
    Muls(E, B, oneMinusBeta1, valid); Add(C, C, E, valid);
    Muls(C, C, invBias1, valid);          // C = m_hat

    Mul(B, B, B, valid);                  // B = grad^2
    Muls(D, D, beta2, valid);
    Muls(B, B, oneMinusBeta2, valid); Add(D, D, B, valid);
    Muls(D, D, invBias2, valid);          // D = v_hat
    SafeSqrt(B, D, maskBuf, valid);        // B=sqrt(v_hat)，D 保留原 v_hat
    Adds(B, B, epsilon, valid);            // B=denominator
    SafeDiv(C, B, D, maskBuf, valid);      // C=adaptive；D 作安全分母/特殊值暂存
    if (weightDecay != 0) { Muls(E, A, weightDecay, valid); Add(C, C, E, valid); }
    Muls(C, C, signedLr, valid);
    Add(E, A, C, valid);                   // E = y，独立 VECOUT Tensor
    qOut.EnQue(E);                         // 建立 V→MTE3 依赖
    E=qOut.DeQue<float>(); DataCopyPad(yGm[offset], E, bytes); qOut.FreeTensor(E);
    qVar.FreeTensor(A); qGrad.FreeTensor(B); qM.FreeTensor(C); qV.FreeTensor(D);
}
```

#### 2.4.2 FP16/BF16 升精度分支

**适用场景**：输入 dtype 为 FP16 或 BF16。

```cpp
for each tile of this block {
    valid = min(ubFormer, blockRemaining);
    for (input in [var, grad, m, v]) {
        rawIn = qRawIn.AllocTensor<InputT>();
        DataCopyPad(rawIn, inputGm[offset], valid * sizeof(InputT), zeroPad);
        qRawIn.EnQue(rawIn);
        rawIn = qRawIn.DeQue<InputT>();     // 等待 MTE2 完成
        Cast(targetFp32Buffer, rawIn, CAST_NONE, valid);
        qRawIn.FreeTensor(rawIn);           // Cast 消费完成后才允许下一输入复用
    }
    // A/B/C/D 上执行同一矩估计链路，随后 SafeSqrt(B,D)、SafeDiv(C,B,D)。
    if (weightDecay != 0) { Muls(E, A, weightDecay, valid); Add(C, C, E, valid); }
    Muls(C, C, signedLr, valid);
    Add(A, A, C, valid);
    rawOut = qRawOut.AllocTensor<InputT>();
    Cast(rawOut, A, CAST_RINT, valid);
    qRawOut.EnQue(rawOut);                  // 建立 V→MTE3 依赖
    rawOut=qRawOut.DeQue<InputT>(); DataCopyPad(yGm[offset], rawOut, valid*sizeof(InputT));
    qRawOut.FreeTensor(rawOut);
}
```

该分支禁止用 FP16/BF16 直接完成 sqrt/div，也禁止 Host 预先 cast 输入。

#### 2.4.3 SafeSqrt / SafeDiv 特殊域分支

**适用场景**：所有 dtype。普通正值同样经过该路径，以保证强制 case 和通用接口具有单一确定语义。`cmpCount=AlignUp(valid,64)`，仅前 `valid` 个结果写出；mask buffer 大小为 `Align256(cmpCount/8)`。

```cpp
// SafeSqrt(out=B, originalVhat=D)
CompareScalar(maskBuf, D, 0.0f, CMPMODE::LE, cmpCount); // non-positive mask
Duplicate(B, FLT_MIN, valid);                           // 严格正的安全输入
Select(B, maskBuf, B, D, VSEL_TENSOR_TENSOR_MODE, valid); // <=0:FLT_MIN, else:D
Sqrt(B, B, valid);
CompareScalar(maskBuf, D, 0.0f, CMPMODE::NE, cmpCount);
Select(B, maskBuf, B, 0.0f, VSEL_TENSOR_SCALAR_MODE, valid); // zero 恢复 sqrt(0)=0
CompareScalar(maskBuf, D, 0.0f, CMPMODE::GE, cmpCount);
Select(B, maskBuf, B, quietNaN, VSEL_TENSOR_SCALAR_MODE, valid); // negative/NaN→NaN

// SafeDiv(numerator/result=C, denominator=B, scratch=D)
CompareScalar(maskBuf, B, 0.0f, CMPMODE::NE, cmpCount);
Select(D, maskBuf, B, 1.0f, VSEL_TENSOR_SCALAR_MODE, valid); // 零分母替换为1
Div(C, C, D, valid);                                        // 不发生除零
// 此时零分母位置的 C 等于原 numerator，可据其符号构造特殊值。
Duplicate(D, positiveInf, valid);
CompareScalar(maskBuf, C, 0.0f, CMPMODE::GE, cmpCount);
Select(D, maskBuf, D, negativeInf, VSEL_TENSOR_SCALAR_MODE, valid);
Compare(maskBuf, C, C, CMPMODE::EQ, cmpCount);       // ordered：NaN 的 C==C 为 false
Select(D, maskBuf, D, quietNaN, VSEL_TENSOR_SCALAR_MODE, valid);
CompareScalar(maskBuf, C, 0.0f, CMPMODE::NE, cmpCount);
Select(D, maskBuf, D, quietNaN, VSEL_TENSOR_SCALAR_MODE, valid); // 0/0→NaN
CompareScalar(maskBuf, B, 0.0f, CMPMODE::NE, cmpCount);
Select(C, maskBuf, C, D, VSEL_TENSOR_TENSOR_MODE, valid); // 非零:quotient，零:special
```

quiet NaN/±Inf 以 TilingData 中的 IEEE-754 `uint32_t` bit pattern 传入并在 Device 侧 bit-cast 为 float，避免 Host/编译器文本常量改写。Developer 必须先用最小 Kernel 在真实 DAV_2201 上验证 Compare 对 NaN 的 EQ/NE mask 语义；若硬件实测不符合 IEEE 比较，立即返回 `design_issue`，不得删除 Safe 分支后继续。

### 2.5 正确性与性能产物契约

每个 case 的结果记录至少包含：`case_id, dtype, shape, attrs, command, build_status, runtime_status, precision_pass, MERE, MARE, threshold, task_duration_us, baseline_perf_us, t_hw_us, perf_score, device, profiler_source`。`perf_score` 按 CANN Bench HAP 公式：

```text
perf_score = (T_baseline - T_HW) /
             ((T_candidate - T_HW) + (T_baseline - T_HW))
```

性能时间必须从 msprof 目标 Kernel 的 Task Duration/`kernel_details.csv` 得到，禁止使用 Host wall-clock 替代。采集采用 warmup=3、repeat=5、freq_boost=true、ProfilerLevel1，并保存原始 profiler 目录与解析后的 JSON/CSV。

## 3. 确认清单

- [x] 数学语义、attrs 默认值和 `maximize` 行为已对齐任务 golden。
- [x] NpuArch、`__NPU_ARCH__` 与 `--npu-arch` 已记录，并设置架构冲突复核门禁。
- [x] 技术路线已确定为 DAV_2201 通用 SIMD/MemBase。
- [x] 多核与 UB Tiling 策略已确定，长度和尾块覆盖完成。
- [x] FP32 五个 Queue Buffer、半精度四个 FP32 TBuf + raw Queue、mask 与 Select 8KB 临时区的闭合规划已完成。
- [x] 所有选用 API 均在 CANN 9.0 本地官方文档中验证。
- [x] FP32、FP16、BF16、对齐、非对齐、Inf、NaN、zero、maximize、weight decay 分支已覆盖。
- [x] 20 个 cases、逐 case Task Duration、HAP 评分和可复现命令已纳入验收契约。
