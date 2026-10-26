# case-04 / 重复2 / A

本页仅本地化原答案中的链接，评分使用[原文](./r12-7dcb8fd5.txt)。题面及源码见[固定输入](../sources/inputs/case-04.txt)。

---

## 1. 输入输出与数值语义

以下行号均指 `source/matmul_leakyrelu_basic_api.asc`，另有标注除外。

`main`（197–247行）读取连续 ND、half 类型的 A[512,128]、B[128,128]，输出同为连续 ND、half 的 C[512,128]。A、B、C 的分配大小分别为 **128 KiB、32 KiB、128 KiB**。无转置、bias 或其他输入。

对每个输出元素，算法为矩阵乘后接 LeakyReLU，但**中间存在一次 half 落地**：

1. `Mmad` 用 half 输入，在 float 类型 L0C 中产生矩阵乘结果 \(s_{ij}=\sum_{k=0}^{127}A_{ik}B_{kj}\)（115行）。
2. `Fixpipe` 将结果转换成 half，记为 \(h_{ij}\)，写到 C 的 GM 地址；这里 `reluEn=false`（125–127行）。
3. Vector 再读取 \(h_{ij}\)，原地执行 LeakyReLU：非负部分保留，负值部分乘 `(half)0.001`，结果仍为 half（155–176行）。

因此不能将它等同于“float 累加结果直接激活后只舍入一次”。斜率也是 half 表示的近似值。源码能确定接口类型和转换位置，但不能单凭这些代码确定 Cube 的逐项累加顺序、所有舍入细节以及 NaN、带符号零等特殊值行为。

## 2. 实际分派与覆盖范围

启动块数为 `(512/256)*(128/128)=2`（215、242–243行）。入口 `mmad_vec_custom` 使用 `__mix__(1,2)`（188行）；按本题混合核语义及文件注释，实际为 **2 个 AIC/Cube、4 个 AIV/Vector**，每个 Cube 对应两个 Vector，而非只启动两个 Vector。

`Init`（31–45行）中，GlobalTensor 下标均以 **half 元素**计：

- AIC 索引 \(q=0,1\)：A 和 C 分别偏移 `q*256*128=q*32768` 个 half，即 `q*65536` 字节；B 不偏移。
- AIV 索引 \(v=0,1,2,3\)：先把 C 定位到 `floor(v/2)*32768`，再由150行加上 `(v%2)*16384` 个 half。

| 执行者 | 完整输出行范围，列均为0–127 |
|---|---|
| AIC 0 / AIC 1 | 0–255 / 256–511 |
| AIV 0、1、2、3 | 分别为0–127、128–255、256–383、384–511 |

四个 Vector 的绝对输出起点分别是 **0、16384、32768、49152 个 half**，即 **0、32768、65536、98304 字节**。它们彼此不重叠。

本 workload 下，每个 Cube 只执行一个完整的 **256×128×128** 矩阵乘 tile；每个 Vector 只调用一次激活，处理 **128×128=16384** 个 half。没有输出 tile 循环、软件 K 累加循环或尾块处理。79、87行的循环是格式搬运循环，不是多次矩阵乘。

这里 `baseM=singleCoreM`、`baseK=K`、`baseN=N`，所以完整覆盖成立。`singleCoreK` 没有参与实际循环，`singleCoreN` 仅参与启动数量计算；地址映射仅沿 M 分核，不能据模板参数推断它支持任意 M/N/K 分块。

## 3. 数据通路与片上排布

### Cube 路径

每个 AIC 独立申请以下局部存储（52–61行），没有显式双缓冲：

| 存储 | 类型、元素数与容量 | 排布 |
|---|---|---|
| L1 A | half，32768，64 KiB | NZ |
| L1 B | half，16384，32 KiB | NZ |
| L0A | half，32768，64 KiB | 2201 分支为 ZZ |
| L0B | half，16384，32 KiB | ZN |
| L0C | float，32768，128 KiB | 矩阵分形/NZ结果 |

L1 中 A、B 按申请顺序分配，合计 **96 KiB/核**。这些是源码申请量，不等于对可用容量或其他隐含开销的测量。

65、68行的 `DataCopy + Nd2NzParams` 把 GM 中 A 的256行、B的128行从 ND 转为 NZ；源行距均为128个 half，即256字节。A 分核读取不同的半矩阵；两个 Cube 都读取完整 B，但各自有片上副本。

**实际 device 宏为2201**，因此执行75–91行：

- A：16次 `LoadData`，每次搬8个16×16 half 子块。目标起点每次增加 `128*16=2048` 个 half，即4096字节；源起点每次增加 `512/sizeof(half)=256` 个 half，即512字节。`srcStride=16` 按 API 的分形块单位跨越 L1 中不同 K 块，形成 NZ→ZZ。
- B：8次 `LoadData`，每次也搬8个16×16子块；目标步长同为4096字节，源起点步长512字节，`srcStride=8`。`ifTranspose=true` 配合布局转换形成 NZ→ZN；这是供 Cube 使用的内部重排，**不是把数学运算改成 \(AB^T\)**。

这里一个16×16 half 子块是512字节；它不同于其他搬运接口可能使用的32字节块单位。

随后一次 `Mmad({256,128,128,0,false,true})` 完成全部 K；`cmatrixInitVal=true` 表示初始化当前累加结果，不依赖未初始化的 L0C 或原 C。`Fixpipe` 按 `nSize=128,mSize=256` 将 float 分形结果转为 half ND，GM 行距为 N=128个 half，并写回对应 C tile（113–127行）。

### Vector 路径

每个 AIV 申请 **16384个 half，即32 KiB UB**（133–134行），以连续 ND 半块存放。

`LeakyReluCompute` 本次 `mIndex=nIndex=0`。两次 `DataCopyPad` 均为128行，每行 `blockLen=128*2=256` **字节**；GM 行间跳过量 `(N-baseN)*2=0` 字节，UB 侧间隔也为0。虽开启输入 padding 参数，但左右 padding 都是0，本例没有实际补齐或尾部屏蔽。激活在同一 UB tensor 上原地完成，再写回原 GM 区域（143–176行）。

因此融合发生在同一混合 kernel 内，**Cube 与 Vector 间仍经 GM 中转**，不是直接共享 L0C/UB。

## 4. 关键依赖与910C执行行为

按源码及 AscendC 的流水/事件语义，依赖链为：

1. **MTE2→MTE1**：GM→L1 的两次搬运后，72–73行事件保证 LoadData 不提前读取 L1。
2. **MTE1→M**：110–111行保证所有 L0A/L0B 装载完成后，Cube 才执行 `Mmad`。
3. **M→FIX**：119–120行保证 Fixpipe 读取已完成的 L0C。
4. **Cube→对应两个Vector**：`CrossCoreSetFlag<0x2,PIPE_FIX>(0)` 位于 Fixpipe 之后，AIV 在136行等待同一模式和标志；按该 API 的配对同步语义，Vector 的 GM 读取不会早于对应 tile 写回。
5. **MTE2→V→MTE3**：162–171行的事件依次保证 GM→UB 完成、激活完成，再将 UB 写回 GM。

各事件虽都用 `EVENT_ID0`，但属于不同硬事件类型；本例没有循环复用同一缓冲区的额外依赖。A/B 只读；Cube 输出区域互不重叠，Vector 半块互不重叠，原地更新由上述核间同步保护。

入口末尾 `PipeBarrier<PIPE_ALL>()`（194行）收束本核流水；它不能代替中间的生产者—消费者核间同步。host 在 kernel 后执行 `aclrtSynchronizeStream`，再拷回结果（244–247行），保证输出获取发生在任务完成之后。

910C 上可静态确认的执行结构是：MTE2搬运/ND转换、MTE1装载重排、Cube矩阵计算、FIX转换写回，以及Vector侧MTE2/V/MTE3链。每个 Vector 必须等对应 Cube 的整个 tile 写回；不同组之间没有额外源码依赖，是否及如何重叠由调度决定，不能据此断言实际重叠率或性能瓶颈。

## 5. 分支地位与证据边界

3510 的92–106行是编译期另一平台实现：使用 `LoadData2DParamsV2`，A 的 L0A 排布为 NZ；**本次2201不执行它**。源码没有 host `NPU_ARCH` 分派，不能将 host 架构值与 device `__NPU_ARCH__` 混用。若 device 宏两者均不匹配，这段代码也没有其他 LoadData 后备路径。

本次尺寸均为16的整数倍且整除分核大小，无边界判定需求；源码并非通用尾块实现。host 未检查 ACL 或文件函数返回值；`data_utils.h:25–61` 也不强制文件大小等于期望大小。因此完整算法成立还以输入文件完整、运行时调用成功为前提。没有编译、运行或 profiling 证据，不能进一步确认精确指令展开、资源驻留、带宽利用率或耗时。
