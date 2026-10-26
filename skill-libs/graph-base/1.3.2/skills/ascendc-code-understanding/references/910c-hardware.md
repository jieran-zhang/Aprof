# 910C：从数据路径解释硬件行为

查阅顺序可按问题选择：适用架构、存储与路径、布局与搬运单位、buffer 生命周期、同步。这里的硬件知识服务于理解当前算法如何执行，不构成瓶颈诊断或优化建议。

## 适用边界与证据层级

本版面向用户已指定的 910C 工程。固定版本 devkit 文档明确标记 Atlas A3 对应 `__NPU_ARCH__ == 2201`；cannbot 产品表将 A3 与 `Ascend910_93` 联系起来。这些支持选择 A3/2201 内容，并不代替项目已有的具体型号、SDK 和编译目标证据。[文档 H01/H02；辅助映射 M02，见来源索引]

同一 Markdown 经常同时含 `npu="910b,A3"`、`npu="950"` 分区，公共 API 名称也可能跨架构重载。解释前先确认产品支持表、函数原型、条件编译，再进入实现。`__NPU_ARCH__==2201` 的数据搬运实现选入 `dav_c220`；`3510` 选入另一目录。[源码 H11] 本文不把 950/3510 的 Compact、负 stride、loop/regbase 或 CV 直通行为移植到 910C。

用于解释硬件的依据按用途区分：A3/2201 文档给出 API 和架构契约；`dav_c220` 源码说明该版本怎样实现具体重载；由二者与项目代码计算出的占用、地址覆盖或依赖属于推导。内部头文件是理解依据，不是建议业务代码直接 include 的公共 API。[源码 H10 的文件告示]

核数、总带宽、频率、设备拓扑和项目可用内存不在本包固定。文档中的存储规格与实际用户可分配容量也有区别，预留空间可能受 SDK、融合场景及编译选项影响。解释资源约束时应以当前工程的平台信息、分配方式和构建条件为边界，不用其他 SKU 的峰值补空白。[文档 H02 的容量及预留说明；M02]

## 先区分 AIC/AIV 与逻辑位置

2201 文档把 Cube 与 Vector 放在独立的 AIC 和 AIV 核上，各自拥有 Scalar；AIC/AIV 间通过 GM 传递数据。因此一个融合算法可由多个角色协作，源码写在同一文件不代表共享一套片上内存，也不代表核内事件可以保护跨核读写。[文档 H02]

| 代码位置/对象 | A3 下的物理存储 | 在算法理解中的含义 |
| --- | --- | --- |
| GlobalTensor、GM | Global Memory | 输入、最终输出，也可能保存核间中间值/workspace |
| VECIN、VECCALC、VECOUT | 均为 UB | Vector 使用的数据；标签体现角色，不是三个物理层级 |
| A1、B1、TSCM | L1 | Cube 输入暂存；A1/B1 可以占同一 L1 的不同区域 |
| A2 / B2 | L0A / L0B | Cube 左/右矩阵输入 |
| CO1 | L0C | Cube 输出与累加中间结果 |
| CO2 | GM | A3 的映射；不能套用旧产品 CO2→UB |

表中映射来自 [H03 的 TPosition 表](source-index.md#h03)。C1/C2、BiasTable 等在项目实际使用时再按同一文档 A3 分区解释，不凭相邻名称猜测存储。

## 沿数学对象追踪搬运和执行单元

典型 Vector 路径是 `GM --MTE2--> UB --V计算--> UB --MTE3--> GM`。典型基本 Cube 路径是 `GM --MTE2--> L1 --MTE1--> L0A/L0B --M计算--> L0C --FIX--> GM`。Scalar 发射指令并处理标量控制，各流水可异步执行；图中的箭头只表达数据关系。[文档 H04/H14；Cube 源码 C01]

但不能按 `DataCopy` 名字把所有搬运都归 MTE：

| 实际路径 | 该版本的证据 | 应怎样解释 |
| --- | --- | --- |
| GM→UB、UB→GM | `DataCopyGM2UBImpl` / `DataCopyUB2GMImpl` 及核内流水表 | 分别读入/写出 Vector 数据，涉及 MTE2/MTE3 |
| UB→UB | `DataCopyUB2UBImpl` 调 `copy_ubuf_to_ubuf`；C API 同 intrinsic 的实现与文档明确 `PIPE_V` | 消耗 V 流水的搬运，也要考虑与 V 计算的数据依赖 |
| L0C→GM | `DataCopyL0C2GMImpl` 调 `copy_matrix_cc_to_gm`；流水表为 FIX | 输出可伴随类型/布局处理，不是 UB→GM 的 MTE3 路径 |
| 某些 AIV UB→L1/TSCM 重载 | `DataCopyUB2L1Impl`、`DataCopyPadUB2L1Impl` 注明 Matmul 软件模拟，经 workspace GM 并向 AIC 发消息 | 把 UB→GM、中转及 AIC 侧工作纳入链条，不能画成天然片上直连 |

依据：[源码 H10/H11/H13；文档 H04/H12](source-index.md)。最后一行限定具体重载和 Matmul 上下文，不能扩大为所有 API、所有代际都相同。类型转换、ND/NZ 转换与填充也都需读匹配的重载。

## layout 是算法索引与物理地址之间的桥

以 half 的基本矩阵乘为例，数学上 A 为 `[M,K]`、B 为 `[K,N]`、C 为 `[M,N]`；在 2201 示例中，A/B 由 GM 的 ND 变成 L1 的 NZ，再分别进 L0A 的 ZZ、L0B 的 ZN，结果位于 L0C 的 NZ，最后写回 GM ND。转换不等于数学转置，更不能把 `ifTranspose=true` 单独解释成算法换成 `A×Bᵀ`。[文档 H02/H09；源码 C01 的 2201 分支]

以下偏移公式是由 H09 的 reshape/transpose 定义推导，用于阅读 half 示例。令 `q=16`，将已 padding 的维度分成 16×16 分形；所有偏移均以元素计，padding 后维度须用于分形数。

| 位置与布局 | 原坐标的物理偏移（half 示例） |
| --- | --- |
| ND A `[M,K]` | `m*K + k` |
| NZ A `[K/16,M/16,16,16]` | `((k/16*(M/16)+m/16)*16+m%16)*16+k%16` |
| ZZ A `[M/16,K/16,16,16]` | `((m/16*(K/16)+k/16)*16+m%16)*16+k%16` |
| ZN B `[K/16,N/16,16,16]` | `((k/16*(N/16)+n/16)*16+n%16)*16+k%16` |

这里 `/` 表示整除。half 的一个 L1/L0A/L0B 分形含 256 元素、512 字节；L0C 的 NZ 分形为 16×16 元素，示例 float 累加时是 1024 字节。不能把“512 字节分形”套给所有 dtype 和所有存储位置。[文档 H09；推导]

有效 shape、padding shape、local 排布与 GM 行跨度要一起说明。地址运算支持证明“读取原矩阵哪些元素”，layout 公式支持证明“它们以什么顺序送入 Cube”。跨 dtype 情况重新查分形规则，不从 half 例子外推。

## DataCopyPad：先核对方向，再换算单位

下面仅讨论 A3 支持的、不含 `PaddingMode` 模板参数的 `DataCopyExtParams` 重载。GM→UB 文档虽然共享表中出现 Compact 文字，但其产品支持表与原型明确 A3 不支持 mode；A3 的普通路径逐块补齐至 32B。[文档 H05/H06]

| 参数 | GM→UB | UB→GM |
| --- | --- | --- |
| `blockCount` | 连续数据块数 | 连续数据块数 |
| `blockLen` | 每块有效字节数 | 每块有效字节数 |
| `srcStride` | GM 中前块末尾至后块开头的字节间隔 | UB 侧块间间隔，以 32B dataBlock 计 |
| `dstStride` | UB 侧块间间隔，以 32B dataBlock 计 | GM 中前块末尾至后块开头的字节间隔 |
| `leftPadding/rightPadding` | 元素个数，换字节时乘 `sizeof(T)` | 此重载无对应填充参数 |

`srcStride`/`dstStride` 是间隔，不是整行起点到下一行起点的跨度。示例推导：GM 每行含 11 个 float 有效值、物理行长 16 个 float，连续读 3 行；`blockLen=44B`、`srcStride=(16-11)*4=20B`。若 UB 每行显式右补 5 个 float，填充值设为 0，`dstStride=0`，每行占 `(11+5)*4=64B`，3 行共 192B。写回紧凑输出时 `blockLen=44B`、UB `srcStride=0`、GM `dstStride=0`，输出有效 132B；每个 UB 块按 32B 对齐读取，非有效部分不写入 GM。[H05/H06 的单位与普通非对齐行为；本文教学推导，不引用评测样例]

若 padding 参与归约，其值须与数学运算相容；若只是对齐产生的 dummy，则不要当作有效输入。`isPad=false` 不等于“自动补零”，也不等于“无需 local 对齐空间”。本阶段说明源码实际的有效范围和补充值，未见相应约束就保留未知。[文档 H05/H06；算法层推导]

## 分配与生命周期：三个量不能合并

`TPipe::InitBuffer(que,num,len)` 的 `num` 是物理内存块数量，`len` 是每块字节数，非 32B 对齐时内部向上补齐。`TQue<pos,depth>` 的 depth 约束没有 DeQue 间隔的连续 EnQue 次数，文档明确它与 double buffer 不同：depth 为 1 也可以分配双缓冲。[文档 H07/H08]

例如三条独立 UB 队列均调用 `InitBuffer(q,2,100*sizeof(float))`：单块 400B 向上对齐为 416B，用户分配合计 `3*2*416=2496B`；不能再乘 depth。这个数只统计所列分配，不包含其他 TBuf、临时区、API scratch、框架预留。存在重用/别名时按实际存活的物理区域解释，不能直接把每个变量都当一份内存。[H07/H08；推导]

静态 `LocalMemAllocator::Alloc<T,N>()` 中 N 是元素数；它不依赖 TQue，当前示例采用的分配要独立计算。`BUFFER_NUM=2` 只能提示去找两块地址或槽位切换，不能证明存在两块物理 buffer。[文档 H15/H16；源码 A02/C01]

## 同步把数据生命周期连起来

核内 SetFlag 的含义是源流水前序操作完成后置位；WaitFlag 使目的流水等待该事件并消耗状态。事件方向和 ID 共同标识一对关系。PipeBarrier 保护同流水前后读写；“顺序发射”不意味着前一条已经完成。TQue/TPipe 与编译器可提供自动同步，是否需要手动事件取决于编程方式与 API 场景。[文档 H04]

一个复用单组 UB 的循环至少需要理解以下关系，具体由项目代码的机制承担：

```text
MTE2 写 X/Y[i] ──就绪──> V 读 X/Y[i]、写 Z[i] ──就绪──> MTE3 读 Z[i]
       ↑                       │                               │
       └─ 下一轮覆写 X/Y 前 ───┘                               │
                     下一轮覆写 Z 前 <─────────────────────────┘
```

该图解释数据依赖，不宣称所有阶段必须全局串行，也不证明已经并行。AIC/AIV 间的数据依赖另看双方角色、GM 中间区、cross-core flag 的 mode/ID 与发出方流水；本版 2201 文档的跨核等待语义不可用别的代际替换。[文档 H02 的核间同步章节]

可得结论是哪些读写要等待、哪些地址可以复用、算法哪些部分互相独立。即使有双物理 buffer、预取或跨流水事件，真实重叠率、耗时和资源瓶颈仍不由这些静态事实单独证明。

所有编号对应 [来源索引](source-index.md)，每条原始片段保留适用分区、源码路径、版本和 hash。
