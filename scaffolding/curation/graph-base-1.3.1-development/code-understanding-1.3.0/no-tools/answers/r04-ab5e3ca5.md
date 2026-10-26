# case-01 / 重复2 / B

本页仅本地化原答案中的链接，评分使用[原文](./r04-ab5e3ca5.txt)。题面及源码见[固定输入](../sources/inputs/case-01.txt)。

---

# Exp 实现理解说明

以下以题定 **910C / Atlas A3、device `__NPU_ARCH__=2201`** 为范围；源码事实、API 行为与静态推导分别说明，不包含运行或性能结论。下文文件简称均对应题面 `source/op_host`、`source/op_kernel` 下文件。

## 1. 输入输出与数值语义

这是一个独立启动的逐元素算子，不含归约、广播或核间结果合并。输入、输出均为一维连续 ND、同 dtype、同长度。host 只接受 float16、float32、bfloat16（`exp.asc:20–24,38–43`）；本次为 **25019 个 bfloat16**，每份输入/输出各 **50038B**。

`ComputeExpTiling` 在 host 上预先计算两个 float 系数（`exp_tiling.h:27–28`）：

\[
L=\begin{cases}\log(base),&base>0\\1,&其他\end{cases},
\quad m=scale\cdot L,\quad s=shift\cdot L.
\]

kernel 对每个元素依次执行乘、加、自然指数，数学目标为：

\[
y_i=\exp(m x_i+s).
\]

因此，正 base 时等价于 \(base^{scale x_i+shift}\)；base≤0（包括默认 -1）实际走自然指数语义，而不是计算负底数幂，也不报非法底数错误。

本次 `base=2, scale=0.5, shift=-1`，故 \(m=0.5\ln2\)、\(s=-\ln2\)，理想结果为 \(2^{0.5x-1}\)。代表性输入 -2、0、2 对应理想输出 **0.25、0.5、1**，这些值均可由 bfloat16 精确表示。但实际路径使用 host float 对数及系数、device float 逐步运算和 `Exp`，最后再舍入，不能仅凭代数等价保证逐位结果。

不同 dtype 的处理见 `exp_kernel.asc:45–64,85–93`：

- **float32**：直接在输入/输出 UB tensor 上执行 `Muls→Adds→Exp`，无显式 Cast。
- **float16、bfloat16**：先 `Cast(CAST_NONE)` 到 float，在 float 中完成上述三步，再转回原 dtype；不是直接以低精度执行指数。
- bfloat16 回转明确使用 `CAST_RINT`，即最近偶数舍入语义；float16 回转使用 `CAST_NONE`。不能把后者按名称解释为截断，具体转换细节依赖 API 契约。
- 源码未做限幅、NaN/Inf 检查或溢出保护；特殊值、下溢及指数近似精度需结合实际 SDK 指令语义确认。

## 2. Host 到实际分派

`exp.asc:45–60` 初始化 ACL、选设备、查询向量核数，再计算 tiling；本题固定查询结果为 **3**。随后分配 host 输入/输出、device 输入/输出和 tiling 空间，读取输入文件，复制输入及 tiling 到 device，最后以：

```cpp
exp_kernel<<<tiling.blockNum, nullptr, stream>>>(devIn, devOut, devTiling)
```

启动一次 kernel。这里没有额外 workspace 参数。

输入读取要求完成指定字节数，文件内容按 dtype 原始位模式使用，没有数值转换（`data_utils.h:6–9`）。host 等待 stream 完成后才 D2H、写输出文件并释放资源（`exp.asc:61–68`）。

本次 tiling 推导（`exp_tiling.h:18–29`）：

- `useful=max(1,ceil(25019/4096))=7`
- `blockNum=max(1,min(3,7))=3`
- `blockLength=ceil(25019/3)=8340`，单位是**元素**
- `tileElements=4096`，单位也是**元素**
- `dtype=EXP_BFLOAT16=2`

入口据 dtype 进入 `KernelExp<bfloat16_t>`，不是按架构或 tile 大小再选另一套算法。可见源码没有 host `NPU_ARCH` 分派条件，也没有 3510 分支；不能将 host 配置与 device 架构宏混用。

## 3. 分核、循环与尾块

`KernelExp::Init` 用 `GetBlockIdx()*blockLength` 得到元素起点，再把长度限制为剩余元素数与 blockLength 的较小值；`Process` 每次推进 4096 元素，计算有效 `count`（`exp_kernel.asc:9–33`）。

由此得到：

| block | 全局元素范围（半开） | GM 相对起点 | 三轮 count |
|---|---|---:|---|
| 0 | `[0,8340)` | 0B | 4096、4096、148 |
| 1 | `[8340,16680)` | 16680B | 4096、4096、148 |
| 2 | `[16680,25019)` | 33360B | 4096、4096、147 |

三核各循环三次，共 **9 次 tile 处理**。每核相对元素偏移均为 0、4096、8192；尾轮全局元素起点分别为 **8192、16532、24872**。所有区间互不重叠，合起来恰好覆盖 25019 个元素，最后一核少处理一个元素，无重复计算或核间合并。

`x_[off]`、`y_[off]` 是按 T 元素索引，不是字节索引。实际搬运时才乘 `sizeof(T)`：

- 每个满 tile：4096×2＝**8192B**
- 三个尾 tile：**296B、296B、294B**

核起点没有强制按 32B 对齐；本次第二、第三核的相对字节起点分别模 32 为 8、16，走的是 `DataCopyPad` 非对齐有效搬运路径，而不能当作普通整块对齐拷贝理解。

## 4. 存储、搬运与依赖

每轮源码顺序为 `CopyIn→Compute→CopyOut`。在 A3/2201 上，数据流为：

```text
GM 输入 → MTE2 → UB 输入 → Vector Cast/乘/加/Exp/Cast
                              ↓
GM 输出 ← MTE3 ← UB 输出
```

`VECIN`、`VECOUT`、`VECCALC` 都映射 **UB**，不是三层物理存储；本算子没有 Cube、L1/L0 或 AIC/AIV 间协作路径（平台资料 H02–H04）。

### 搬运与尾部

`CopyIn/CopyOut` 的 `DataCopyExtParams` 都是单块，`blockLen=count*sizeof(T)` 为有效**字节数**，两侧 stride 为零（`exp_kernel.asc:37–42,69–73`）。本次不存在跨行、格式转换或 ND→NZ 重排。

按给定 A3 API 规则 H05/H06，GM→UB 的普通路径将局部块补齐到 32B 边界；三份尾块各需要 **320B 局部跨度**。`isPad=false` 不表示补零，也不取消对齐空间要求。有效计算只传入 count，补齐部分不是数学输入；写回只输出有效的 296/294B，不把补齐内容写到相邻元素或分配范围外。

### 资源组织

`InitBuffer` 分配情况见 `exp_kernel.asc:16–23,80–82`：

| 每核对象 | 容量 |
|---|---:|
| 输入队列：1 个 raw 槽 | 8192B |
| 输出队列：1 个 raw 槽 | 8192B |
| `fpIn_`：4096 个 float | 16384B |
| `fpOut_`：4096 个 float | 16384B |
| **显式用户数据区合计** | **49152B＝48KiB** |

这些容量在尾轮不会缩小，并在各轮复用。float16 分支同样是 48KiB；float32 不申请两个 float 临时区，输入/输出各 16384B，合计 **32KiB**。这只统计可见数据分配，不包含框架、编译器或 API 潜在临时空间。

两个队列既是 depth=1，又各只申请一个物理槽；依 H07/H08，队列深度与物理缓冲数是不同概念。本实现确实是**单槽循环复用**，不能据队列存在声称使用双缓冲。

### 生命周期与同步

输入由 `AllocTensor→DataCopyPad→EnQue→DeQue` 交给计算；计算完成后释放输入。输出由计算分配并入队，`CopyOut` 出队搬出后释放（`exp_kernel.asc:37–73`）。

必要依赖包括：

1. MTE2 写完输入后，Vector 才能读取；
2. Vector 读完输入后，下一轮才能覆盖输入槽；
3. Vector 写完输出后，MTE3 才能读取；
4. MTE3 读完输出后，下一轮才能覆盖输出槽；
5. float 临时区及原地 `Adds/Exp` 的前后读写也须保持依赖。

源码没有手写 flag/barrier，而依赖 TPipe/TQue 资源与同步机制，以及编译器对相应计算依赖的处理；具体事件和屏障展开未提供。host stream 同步保护整个 kernel 完成到 D2H 的边界，不能代替核内依赖。

## 5. 910C 执行含义与证据边界

本次是 **3 个独立的向量工作分块**，Scalar 负责控制、地址和指令发射，MTE2、Vector、MTE3 承担搬入、计算、搬出。3 来自题定查询与分核公式，不是对 910C 物理核总数的断言。

源码请求的有效输入读取和输出写入各 50038B，合计 **100076B**；这是逻辑 payload，不含 tiling 访问，也不等于实际 HBM 事务量。单槽复用约束明确，但不同流水可能异步执行；静态调用顺序既不能证明完全串行，也不能证明已有效重叠。

本次覆盖范围及尾块容量可由源码闭合推导。尚无实际 SDK 编译产物、运行正确性或 profiling 证据，因此实际指令展开、完整资源占用、特殊数值行为、流水重叠率和耗时均未确认；这些边界不影响上述算法、分派、地址及依赖关系的静态理解。
