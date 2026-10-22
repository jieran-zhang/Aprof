# case-01 / 重复1 / B

本页仅本地化原答案中的链接，评分使用[原文](./r24-4b9c1aef.txt)。题面及源码见[固定输入](../sources/inputs/case-01.txt)。

---

# Exp 实现代码理解说明

以下以源码事实为主；数值与覆盖范围标为推导，硬件解释采用题给 A3/2201 API 资料，未假定已有编译或实测结果。路径简称：host=`source/op_host/exp.asc`，tiling=`source/op_kernel/exp_tiling.h`，kernel=`source/op_kernel/exp_kernel.asc`。

## 1. 输入输出与数值语义

这是独立逐元素算子：输入、输出均为一维连续 ND，元素数和 dtype 相同，没有广播、归约或核间结果合并。

`ComputeExpTiling` 将参数转换为两个 float 标量（tiling:18–29）：
\[
L=\begin{cases}\log(base),&base>0\\1,&其他\end{cases},\quad
m=scale\cdot L,\quad s=shift\cdot L.
\]
kernel 随后按 **乘标量→加标量→自然指数** 的顺序计算：
\[
y_i=\operatorname{Exp}(m x_i+s).
\]
因此数学上，正底数时是 \(base^{scale\,x_i+shift}\)；非正底数走自然指数语义，并不是计算负底数幂或直接报错（kernel:45–64）。

本次 `base=2, scale=0.5, shift=-1`，故 \(m\approx0.34657359\)、\(s\approx-0.69314718\)，目标为 \(2^{0.5x-1}\)。代表值：

| 输入 | 数学指数 \(0.5x-1\) | 理想输出 |
|---|---:|---:|
| -2 | -2 | 0.25 |
| 0 | -1 | 0.5 |
| 2 | 0 | 1 |

**实际精度路径**（host:20–24；kernel:50–64、85–93）：
- `float32`：直接在 float 输入/输出 UB tensor 上执行 `Muls→Adds→Exp`。
- `float16`、`bfloat16`：先 Cast 到 float，以上三步均在 float 临时区计算，再 Cast 回原 dtype；不是用低精度执行中间指数计算。
- BF16 回写采用 `CAST_RINT`；FP16 回写采用 `CAST_NONE`，升精度也指定 `CAST_NONE`。不应把两种回写模式混称为同一显式舍入规则。

host 的 `log`、两个 float 参数及各步浮点运算会引入舍入，`Exp` 还有实现精度边界；数学等价式不保证与直接幂函数逐位一致。上述理想输出可由 BF16 表示，但材料不足以承诺设备输出逐位精确。源码未做有限值校验、指数溢出保护或显式截断。

## 2. 从 host 参数到实际分派

host 解析 `n=25019`、`dtype=EXP_BFLOAT16(2)`，单元素 2B，输入和输出各分配 **50038B**（host:38–43、51–55）。设备默认编号为 0；按题设查询到的 Vector core 数为 3，而不是据此断言整颗 910C 只有 3 个物理核。

tiling 推导（tiling:21–28）：
- `useful=max(1,ceil(25019/4096))=7`；
- `blockNum=max(1,min(3,7))=3`；
- `blockLength=ceil(25019/3)=8340`，单位为**元素**；
- `tileElements=4096`，固定，不随 dtype 改变；
- 写入上述 dtype、multiplier 和变换后的 shift。

host 读取原始二进制输入，复制输入及 tiling 到 GM，再以 `<<<3,nullptr,stream>>>` 启动 `exp_kernel`（host:56–60）。文件读取要求成功获得所需字节，未转换输入格式；`data_utils.h:6–8` 也没有核验文件是否恰好只有这些字节。

入口读取 GM tiling，根据 dtype 选择 `KernelExp<bfloat16_t>`；模板内再用 `if constexpr` 选择低精度转 float 的计算路径。这不是按架构宏进行 dtype 分派。host 和 kernel 没有项目自定义的 `NPU_ARCH` 分支。

## 3. 三个 block、九次 tile 与尾块覆盖

`KernelExp::Init` 用 `GetBlockIdx()*blockLength` 得到元素起点，以总长度裁剪本 block 的有效长度；`Process` 每轮增加 4096 元素，并以剩余长度裁剪 `count`（kernel:9–33）。

下表所有区间均为**元素半开区间**，字节起点相对输入或输出 GM 基址：

| block | GM 字节起点 | 有效元素区间 | 各轮全局元素起点 | 各轮 count |
|---|---:|---|---|---|
| 0 | 0 | [0,8340) | 0、4096、8192 | 4096、4096、148 |
| 1 | 16680 | [8340,16680) | 8340、12436、16532 | 4096、4096、148 |
| 2 | 33360 | [16680,25019) | 16680、20776、24872 | 4096、4096、147 |

因此本次共有 **3 个 block、每 block 3 轮、共 6 个满 tile 和 3 个尾 tile**。三段不重叠、无遗漏，合计覆盖全部 25019 元素。元素 \(i\) 的 GM 字节地址为 `base+2*i`；block 起点不要求按完整 tile 或 32B 边界切分。

每轮固定调用 `CopyIn→Compute→CopyOut`。搬运参数均为：
- `blockCount=1`；
- `blockLen=count*sizeof(T)`，单位为**字节**；
- 两侧 stride 均为 0，无跨行或布局变换。

故本次满 tile 有效搬运 8192B，三个尾 tile 分别为 296B、296B、294B，每个方向相同（kernel:37–42、69–73）。

按题给 A3 `DataCopyPad` 契约，GM→UB 的普通路径在 local 侧按 32B 补齐，因此这些尾块各需容纳 320B。`isPad=false` **不表示补零**；但计算仅使用前 `count` 个元素，补齐部分不参与有效结果。UB→GM 仅写指定有效字节，不把 local 补齐区写出。逻辑有效流量为读 50038B、写 50038B，共 **100076B**；这不是实测 HBM 事务流量。

## 4. 存储组织与生命周期

每 block 初始化的用户 buffer 容量如下（kernel:16–23、76–82）：

| 对象 | 本次 BF16 容量 | 作用 |
|---|---:|---|
| `inQ_`，1 个物理块 | 8192B | 接收 GM 输入 |
| `outQ_`，1 个物理块 | 8192B | 保存 BF16 输出，供搬出 |
| `fpIn_` | 16384B | 输入转换成 float |
| `fpOut_` | 16384B | float 乘、加、指数及回转换源 |

合计 **49152B，即 48KiB/执行 block**，末轮仍保留完整容量。FP16 相同；FP32 不分配两个 float 临时区，但输入、输出队列各为 16384B，合计 32768B。上述只统计显式数据分配，不含框架、编译器临时空间或预留。

根据 A3 位置映射，`VECIN`、`VECOUT`、`VECCALC` **都属于 UB**，不是三个物理存储层（题给硬件资料 H03）。输入队列从 Alloc、搬入、EnQue，到 Compute 中 DeQue、消费、Free；输出队列从 Alloc、计算、EnQue，到 CopyOut 中 DeQue、搬出、Free。两个 `TBuf` 在循环中反复复用。

队列模板 depth 为 1，且 `InitBuffer` 的物理块数也确实为 1；这里没有双物理 buffer 或显式 ping-pong 地址。三步循环组织也没有展示预取下一 tile 的软件流水。

## 5. 910C 执行与同步边界

对题设 `__NPU_ARCH__=2201`，按 A3 资料解释的主要路径为：

```text
GM 输入 ─MTE2→ UB 输入
                └─V：Cast→Muls→Adds→Exp→Cast→ UB 输出 ─MTE3→ GM 输出
```

Scalar 承担控制、地址与指令发射；运算属于 Vector/AIV 路径，没有 Cube、L1/L0、FIX 或跨 AIC/AIV 协作。底层搬运采用 2201 对应的 `dav_c220` 路径，不能套用 3510 的 Compact 等行为（题给 H01–H06、H11、H14）。

必须满足的核内依赖包括：
1. MTE2 写完输入，V 才能读取；
2. V 读完旧输入，下一轮才能覆写该输入槽；
3. V 写完输出，MTE3 才能读取；
4. MTE3 读完旧输出，下一轮 V 才能覆写输出槽；
5. float 临时区及原位 `Adds/Exp` 的前后读写也必须有序。

源码未手写 flag/barrier，使用 `TQue/TPipe` 生命周期及 Ascend C 编译/API 同步机制表达这些依赖；不能据此说“没有同步”。具体生成哪些事件、屏障或向量重复指令，材料没有给出。不同流水可异步，但单槽复用约束客观存在，实际重叠程度未测量。

各 block 写独立结果，无需核间同步。host 在 `aclrtSynchronizeStream` 后才 D2H，并将 50038B 输出写入文件（host:61–63）；这是调用完成层面的同步，不替代核内依赖。

## 6. 适用范围与未确认项

本 workload 的地址覆盖、尾长和显式 buffer 容量均可静态闭合；源码也一般性地裁剪 block 和 tile 尾部，但这不等于所有参数均已验证。host 拒绝三类以外的 dtype，device 的最后分支则把其他 dtype 值一律当 BF16；本次正常 host 路径不会触发非法值。极端长度的整数溢出、零长度分配等边界没有专门处理。

没有设备编译、反汇编或 profiling，故不能确认完整资源占用、生成的同步细节、并发驻留、真实吞吐和瓶颈；3 个启动 block 也不证明它们在某一时刻全部并发执行。以上为现有实现及其静态执行含义，不作性能归因或方案选择。
