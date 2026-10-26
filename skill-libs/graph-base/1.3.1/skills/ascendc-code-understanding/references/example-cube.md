# 完整例子：基本 Cube 矩阵乘的算法、布局和执行

使用 devkit `examples/01_simd_cpp_api/00_introduction/02_matrix/matmul_basic_api`。完整实现、README 的相关说明、CMake 和输入/参考值脚本见 [C01–C04](source-index.md#c01)。这是独立的入门基本 API 样例，不使用高性能或融合激活评测样例。

## 先确认工程范围和实际架构分支

单个 `.asc` 同时包含 host `main` 和 `__global__ __cube__` kernel `mmad_custom`。CMake 默认 `CMAKE_ASC_ARCHITECTURES="dav-2201"`，也允许显式配置其他架构；kernel 中存在 2201 和 3510 的 LoadData 分支。本例只解释 2201 分支。README 明确列出 Atlas A3、A2 的 CANN >=9.0.0 支持；这提供样例适用声明，不代表这里已完成 910C 编译或实测。[源码 C01/C03；说明 C02]

## 数学问题与数值语义

输入 A 是 half 的 `[256,64]`，B 是 half 的 `[64,256]`，输出 C 是 half 的 `[256,256]`，GM 均为 ND。数学目标为 `C[m,n]=Σ(k=0..63) A[m,k]*B[k,n]`。kernel 在 L0C 使用 float tensor 承接 Mmad 结果，Fixpipe 的 `F322F16` 把它转换到 half 输出。参考脚本也先把输入转 float32 做 matmul，再转 float16；这个参考表达了数值意图，不证明所有浮点实现逐位相同。[源码 C01/C04；说明 C02]

算法没有 bias、激活和 K 方向多段累加。`MmadParams{baseM,baseN,baseK,0,false,true}` 在这个样例中一次完成每核矩阵块。不要因常见高性能矩阵乘有 K 循环，就为这里补出一个不存在的循环。[源码 C01]

## Host 常量怎样决定多核分解

main 传入的模板参数为 `M=256,K=64,N=256,singleCoreM=128,baseM=128,baseK=64,baseN=256`，launch 使用 `numBlocks=2`。它没有独立的 TilingContext 计算；这些编译期常量就是该工程的切分来源。[源码 C01]

kernel 的关键偏移如下：[源码 C01，省略类型转换后的等价摘写]

```text
mIterIdx = GetBlockIdx() % (M / singleCoreM)
aGM 起点 = A + mIterIdx * singleCoreM * K
bGM 起点 = B
cGM 起点 = C + mIterIdx * singleCoreM * N
```

launch 的 block 0/1 分别得到 mIterIdx 0/1。block 0 处理 C 的第 0–127 行，block 1 处理第 128–255 行；N/K 不切。两核读取不同行的 A，但都读取完整 B，写回不同的 C 行块，因此无需核间合并输出。这里 2 是算法所用 block 数，不是 910C 核数。[源码 C01；推导]

模运算本身不保证任意 launch 数都合理：如果错误地增加到超过 M/singleCoreM 的 block 数，mIterIdx 会重复。理解要把 launch、模板常量和地址公式当作一个闭合上下文，不能孤立地给偏移公式贴“均匀多核”标签。[源码 C01；推导]

## 从矩阵行块到实际数据路径

以下图只表达当前代码的数据与依赖方向：[源码 C01；文档 H03/H04/H09]

```text
A 的 128×64 行块：GM ND ─MTE2/ND→NZ─> L1 A1 NZ ─MTE1─> L0A A2 ZZ ┐
                                                                 ├─M/Mmad─> L0C CO1 NZ(float)
完整 B 64×256：  GM ND ─MTE2/ND→NZ─> L1 B1 NZ ─MTE1─> L0B B2 ZN ┘
                                                                    │
                                                     FIX / NZ→ND / F322F16
                                                                    ↓
                                                   GM C 的 128×256 行块 half
```

DataCopy 的 `Nd2NzParams` 分别使用原始矩阵行跨度 K/N，所以它们读的是输入矩阵正确的行块，而不是把 tile 大小当作所有 GM 行的跨度。A1/B1 使用同一个 L1 allocator 依申请顺序分配；逻辑标签不代表两套独立 L1。[源码 C01；API H03/H15/H16]

2201 的 A 路径用 `baseM/16=8` 次 LoadData，每次读取 K 方向 `baseK/16=4` 个分形，源分形间隔 `baseM/16=8`；目的写入对应的 ZZ 行块。B 路径用 `baseK/16=4` 次 LoadData，每次读取 N 方向 `baseN/16=16` 个分形，源分形间隔 `baseK/16=4`，并设置 `ifTranspose=true` 转换每个分形的排布以得到 ZN。[源码 C01；布局 H09；推导]

这里 B 的局部分形转置服务于物理布局，数学上的 B 仍是 `[K,N]`，没有把算法变成 `A×Bᵀ`。同文件 3510 分支的 A 布局与 LoadData2DParamsV2 路径不属于本例，也不能仅凭相同 Mmad 名字替换到 A3。[源码 C01 的分支；H01/H09]

## 占用体现当前策略的尺度

由五次 `Alloc` 和数据类型得到每个 AIC 的用户数据分配：[源码 C01；元素单位 H15；推导]

| 对象 | 元素数及类型 | 字节数 | 生命周期 |
| --- | --- | --- | --- |
| a1Local (L1) | 128×64 half | 16384 | GM 搬入后供 A 的 LoadData 读取 |
| b1Local (L1) | 64×256 half | 32768 | GM 搬入后供 B 的 LoadData 读取 |
| a2Local (L0A) | 128×64 half | 16384 | LoadData 后供 Mmad 读取 |
| b2Local (L0B) | 64×256 half | 32768 | LoadData 后供 Mmad 读取 |
| cLocal (L0C) | 128×256 float | 131072 | Mmad 写入后供 Fixpipe 读取 |

总量不能相加成“UB 使用量”：L1 的两份合计 49152B，L0A、L0B、L0C 分别独立计。cLocal 的 131072B 恰为 H02 所列 L0C 128KiB 的标称容量；它说明此数据区的规模，不证明完整编译产物的资源检查已经通过。

策略上这是每核一次装入、一次矩阵计算、一次写回。代码没有 TQue 双 buffer、不同 K tile 之间的 ping-pong，也没有跨迭代资源复用。LoadData 内部的小循环用于格式搬运，不应误读成矩阵算法的 K 分块累加循环。[源码 C01；推导]

## 同步怎样约束这些阶段

DataCopy 完成后，`MTE2_MTE1` 事件保证 LoadData 读取已就绪的 L1；LoadData 后，`MTE1_M` 保证 Mmad 的 L0A/B 操作数就绪；Mmad 后，`M_FIX` 保证 Fixpipe 读取已产生的 L0C 结果。最后 `PipeBarrier<PIPE_ALL>()` 结束核内相关流水；host `aclrtSynchronizeStream` 之后才把结果拷回 host。这几层顺序关系各自保护不同范围。[源码 C01；文档 H04]

`FixpipeParamsV220{baseN,baseM,baseM,N,false,F322F16,...}` 明确关闭此参数中的 ReLU，配置输出类型转换，并以 N 为 GM 目标行跨度。把 Fixpipe 简写成“拷贝输出”会遗漏其承担的 dtype/layout 转换；把它放在 MTE3 上则与 A3 的 L0C 输出路径不符。[源码 C01；文档 H04；说明 C02]

事件证明依赖得到显式表达，不能证明三段时间已经有效覆盖。两个 block 的独立输出也只是并行工作的条件，不是并行加速比的测量。

## 算法工作量与实测仍然不同

采用一次乘加计 2 FLOPs 的计算约定，逻辑运算量为 `2*M*N*K=8388608` FLOPs。按可见源码的有效传输计算，两核共读 A 32768B、各自完整 B 合计 65536B、写 C 131072B，合计 229376B。重复读取 B 是代码请求层面的事实；实际从外部内存读取几次受 cache 等影响，不能等同该数。[源码 C01；本文推导与计数约定]

本阶段可交接的结论是：固定 shape 的 half GEMM 沿 M 轴分给 2 个 block，每核以 float L0C 结果经 Fixpipe 转回 half，使用 2201 的 NZ→ZZ/ZN 输入布局转换和三条显式核内依赖链；没有额外 K 切分或融合 epilogue。源码、版本与架构适用条件明确，但没有得到性能测量、瓶颈裁定或优化选项。

## 遇到真实工程的变体时怎样继续读

若项目把 K 分段，就追踪每段输入范围、L0C 的初始化/累加条件和最后输出的位置；若出现 AIC/AIV 协作，就把中间数据在哪、谁发布就绪、谁最后消费补进同一算法图；若封装成高级 Matmul，就从 Host tiling、类型/布局配置和调用方式向下解释实际路径。这里只说明应理解什么，不为目标工程预选这些实现方案。[方法 M01；硬件 H02/H04]
