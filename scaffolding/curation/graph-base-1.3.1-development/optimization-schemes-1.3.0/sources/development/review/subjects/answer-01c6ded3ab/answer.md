## 结论与状态

本轮选择形成一个**条件可实施的完整方案**：

> **保留现有输出分核、坐标变换和间接取数，将三线性插值的八项 FP32 乘法链及累加改为分块 Vector 计算；以连续有效输出块写回。nearest 保持原路径。**

正式意图用一个 `action.vectorize_scalar_loop` 实例表达，输出暂存、FP16 最终转换、FP32 批量写回、尾块和同步是其配套实现，不再按 API 或文件数量拆 Action。

这是**纸面选择，不是已实现候选**。资源、目标 SDK 和 Vector 数值行为的具体门禁列在后文；收益为待检验预测。另一个很重要的机会——**跨通道复用派生几何记录**——预计能消除更多坐标计算，但当前注册 Action 没有准确承载其独立意图，不能伪装成输入驻留或控制外提。

未调用工具、未修改工程、未编译、未运行正确性或硬件测试。下述计划身份仅为本回答中的纸面名称，未生成源码 hash、路由回执或机器契约产物。

---

## 1. 当前实际执行过程及关键源码事实

### 1.1 数学和数值契约

输入为连续布局的：

- `x[N,C,D,H,W]`
- `grid[N,Do,Ho,Wo,3]`，最后一维为 `(x,y,z)`
- 输出 `y[N,C,Do,Ho,Wo]`

坐标和插值使用 FP32。nearest 按 ties-to-even 取整；bilinear 实际为八邻域三线性插值。zeros、border、reflection 的实现分别对应邻点越界返回零、连续坐标裁剪、重复反射再裁剪。

依据：定义文档第 7–30 行；kernel 第 38–133 行。

特别注意：

- 八项贡献在源码中是 **`((value * wx) * wy) * wz` 后依次加到 `result`**，不是预先形成 `wx*wy*wz` 再乘输入。
- 无效邻点由 `GridRead` 返回 `0.0f`，然后仍进入乘法和累加。
- 有效邻点即使权重为零也不能跳过：例如 `Inf*0` 的 NaN 传播属于本题必须保留的行为。
- FP16 输入由 `GridToFloat` 手工展开位模式，包括次正规数和非有限值；实际 FP16 输出路径用 Vector `Cast(..., CAST_NONE, count)`，不是未被调用的逐元素 `GridFromFloat<half>`。

因此，删除零权重项、合并权重、使用 FMA 或改成 Cube 小矩阵乘法，都不是可默认等价的替换。

### 1.2 Host、分核和实际分支

Host：

1. 解析 shape、dtype 和三个属性；
2. 查询 `ACL_DEV_ATTR_VECTOR_CORE_NUM`；
3. 计算 tiling，分配独立的 x/grid/y/tiling GM；
4. H2D 后启动**一个 AIV kernel**；
5. stream 同步后 D2H 并写文件。

依据：host 第 45–74 行。`data_utils.h` 仅负责二进制读写，不涉及采样算法。

令：

\[
S=DoHoWo,\qquad M=NCS
\]

tiling 把展平输出分成连续区间：

\[
begin_b=b\,blockLength,\quad
end_b=\min(begin_b+blockLength,M)
\]

`blockLength` 向上对齐到 FP16 的 32 元素或 FP32 的 16 元素，即源码约定的 64B GM ownership 边界。有效区间互斥且覆盖 `[0,M)`；因向上取整，部分末核可能无工作，kernel 会自然跳过。

依据：tiling 第 36–45 行；kernel 第 143–148、163–178 行。

现有核数已经依据输出量和查询核数选取，不能从“大量 Scalar 循环”推导出“没有启动足够多核”。

### 1.3 每个输出实际做了什么

`GridSampler3DOne` 对每个展平输出执行：

1. 除模解码 `spatial/nc/channel/batch`；
2. 读取三个 grid 值；
3. 三轴反归一化、padding；
4. nearest：三轴 round-even，一次有界读取；
5. bilinear：三轴 floor、距离及补距离，八次有界读取；
6. 八项贡献依次累计。

几何计算只依赖 `(n,p)`，不依赖 `c`，但现在沿 NCDHW 输出顺序为每个通道重新执行。**这是真实的重复派生计算，不等于八邻域输入值跨通道相同。**

依据：kernel 第 101–132 行。

### 1.4 数据通路和已有策略

| 路径 | 实际行为 |
|---|---|
| FP32 | Scalar 从 GM 读 grid/x，Scalar 计算，逐元素 GM 写出 |
| FP16 | Scalar 从 GM 读 grid/x并手工扩位，Scalar 完成采样；每 1024 个结果用 `SetValue` 写 FP32 UB，再批量 Cast 为 half、DataCopyPad 写出 |
| FP16 显式 UB | `1024*4 + 1024*2 = 6144B`，不含框架或隐含资源 |
| 同步 | 每 FP16 tile 有三处 `PIPE_ALL`，分别隔开 Scalar 生产、Vector Cast、DMA 写出及下轮复用 |

依据：kernel 第 151–188 行。

所以：

- 已有 Vector Cast **不代表主插值循环已向量化**。
- 当前没有输入 MTE2 预取队列；不能把 Scalar 随机读取画成已经存在的 GM→UB DMA 流水。
- 没有 AIC、L1/L0、跨核 partial、归并或 GM 中间 tensor。
- 当前 FP16 已批量写回，不能再把它按“每输出一次 DMA”计收益。

### 1.5 会改变优先级的 workload 差异

- bilinear 共 14 个 case：1、2、4、6、7、9、10、11、13、14、16、17、19、20。
- nearest 共 6 个 case：3、5、8、12、15、18；没有八项插值算术，本方案不优化其主计算。
- case 6 有 `33,554,432` 个输出；case 17 有 `192,048,003` 个输出；case 20 有 `63,511,938` 个输出。插值逐元素工作规模很大。
- case 12 的输入宽度为 4001，输出空间远小于输入空间，不能假设输入/输出空间相等或使用相同 stride。
- 奇数空间平面覆盖 7、9–14、17、19、20 等域，必须保留精确尾长。
- 11 覆盖 half 最大有限值域；13、14 覆盖输入 Inf/NaN；15 的全零值域**不能用作运行时特判依据**。

矩阵与 `cases.py` 相互对应，但没有输入生成实现，不能从 value range 推断具体非有限值分布。

此外，定义称 NaN/Inf 遵循 IEEE 传播，但当前源码对**非有限 grid 坐标转整数**没有闭合处理。20 个 workload 的 grid 均有限；这项 API 边界是原实现的未证范围，不能宣称已经完整支持。

---

## 2. 方案比较：减少什么、保留什么、付出什么

### 2.1 所选方案：只向量化三线性贡献计算

对一个有效输出块，Scalar 阶段仍按原顺序生成：

- 八个 `GridRead` 的 FP32 结果；
- 六个轴因子：`wx0,dx,wy0,dy,wz0,dz`；
- FP32 初始累加值 `+0.0f`。

随后按原八邻点顺序，执行三次逐元素 Mul 和一次 Add。

**每个 bilinear 输出的变化：**

| 工作 | 原实现 | 候选 |
|---|---|---|
| 坐标/padding/floor/距离计算 | Scalar | 保留 |
| 八次有界间接读和 half 位展开 | Scalar | 保留 |
| 八项三乘链 | 24 次 Scalar 乘法 | 相同数学顺序的 Vector Mul |
| 八次累加 | Scalar | 相同顺序的 Vector Add |
| 结果输出 | FP32 逐元素；FP16 已分块 | 两 dtype 均按有效连续块写出 |
| 新增 | — | 邻点、因子暂存及 UB 读写、Vector 发射和完成边 |

一个 tile 是 24 个 Mul 调用、8 个 Add 调用，而不是每输出 32 次 Vector 调用。该方案不减少输入 x 的必要逻辑读取，也不减少跨通道几何重算。

选择理由：它直接作用于大型 bilinear 路径的实际数据算术，注册意图明确；不依赖尚未提供的 GM gather API、不要求重新分核或假设输入局部性，且可逐元素保持原乘法与累加顺序。代价也不小：**Scalar 暂存和 UB 流量可能抵消算术收益**，必须将其作为整体试验，而非认定 Vector 必快。

### 2.2 最有潜力的竞争方案：通道块×空间块复用几何

按 `Ct×St` 输出矩形，先生成 `St` 个几何记录，再消费多个通道。

几何构造次数可由：

\[
NCS \rightarrow NS\lceil C/Ct\rceil
\]

源 x 读取上界仍为 `8NCS`，不是除以 Ct。

支持：

- `GridSampler3DOne` 明确证明几何不依赖通道；
- C 最大达 256，重复规模大；
- P 的 `coordinate_neighborhood.md` 正文明确给出了该骨架与成本公式。

新增代价：

- 几何记录长存活、表读取、通道跳跃访问；
- task 数和输出物理边界可能改变；
- 若存完整八邻坐标/标记/权重，片上状态明显扩大；
- 若预乘权重，还可能改变当前浮点顺序。

**本轮未选的决定性原因不是收益未测，而是注册意图缺口。**保存 `G/B/H` 的派生结果不是保留原 grid/X；也不能把插值几何计算都叫“控制不变量”。`coordinate_neighborhood.md` 和 `buffer-lifetime/reuse.md` 正文都明确警告这一点。此方向应保留独立提案，不能夹带进本轮 Action。

### 2.3 最强的现成低成本替代：地址分段外提＋FP32 批量输出

沿当前 owner 区间按通道平面分段，只在段首解码 batch/channel，内层递增空间索引；缓存必要 stride。FP32 暂存后批量输出。

它能减少每输出的整数除模和重复地址前缀，但保留全部坐标和插值算术。相比所选方案，它的 UB 压力及暂存量更低，因而是很有竞争力的可实施替代。

本轮仍优先选择插值向量化：其减少的是每输出 24 乘＋8 累加的 Scalar 数据处理，而非仅若干解码；同时不增加新分派域。**如果编译结果表明 Scalar 乘加本已高效，或候选的暂存/Vector 发射成为主成本，应转向这个替代。**

### 2.4 其他主要机会的判断

- **源输入窗口/规则跨行 DMA：暂缓。**输出连续不代表随机 grid 对应的源邻域连续。`noncontiguous_access` 和 `strided-pad.md` 正文不支持把任意 gather 表达成一组固定 stride；全窗口搬入可能多读大量无用元素。
- **完整坐标向量化：暂缓。**反射、floor/round-even、整数寻址和裁剪条件都要重建。Compare/Select 在 A3 有 256B Compare 执行粒度及 Select 8KB 临时区，不能仅按有效 count 或用 Max/Min 名称替换源码比较。
- **只缩同步/加双缓冲：不是本轮主方案。**FP16 三处全流水屏障确实限制独立阶段，但前面仍是逐元素 Scalar 采样。增加槽只能尝试重叠尾端 Cast/写出，不能消除主循环；本轮先不引入复杂事件和预取。
- **cache hint/L2 重排：无当前策略失配证据。**x/grid 通过裸 GM 指针读取，不能借另一 GlobalTensor 的默认策略证明本访问的 L2 配置。grid 跨通道有复用，也不支持统一 bypass。
- **Cast 消除：不适用。**当前 bilinear 的输入扩位和最终缩位承担数值边界，不是冗余往返。
- **核数/尾均衡/新 dispatch：暂不采用。**现有任务数充足且按输出量查询分核，没有证据证明主要问题来自欠并行或集中尾部。nearest/bilinear 已有语义分支，无须按 case 增加 Key。
- **Cube、CV 融合、归约、workspace 缩减：当前结构不适用。**八邻点求和不是当前需要跨核分解的归约；工程只有一个 AIV launch，也没有待消除的 GM 中间往返。Mmad/Fixpipe 正文中的布局、特殊值和数值限制反而增加重构成本。
- **bank/spill/争用：保持未知，不绑定为已确认机制。**源码没有实际 UB 地址、编译 spill 报告或并发冲突观测；不能由变量多、屏障多直接认定。

这些判断使用给定 Problem 正文区分了机制，而不是使用其历史名称或旧 profile 前提替代事实。Action 门禁以下以用户给出的**当前注册目录**为准，不把 Problem 正文中的旧前提列表混装进来。

---

## 3. Action 实例与必要依赖

### 方案 `S1-trilinear-vector-evaluation`

| 项目 | 绑定 |
|---|---|
| Action 实例 | `A1 = action.vectorize_scalar_loop` |
| target | `GridSampler3DOne` 第 125–132 行的八项贡献计算 |
| stage | AIV 核内 bilinear Compute，并配套结果输出 |
| workload | 两 dtype、全部 padding/align 组合；20-case 中上述 14 个 bilinear case |
| implementation | 当前输入 kernel 第 97–188 行为分析父本；未计算 hash |
| 结构事实 | `symptom.source.scalar_element_loop=true`：第 146–147、170–171 行实际逐元素调用 |
| semantic equivalence | 条件化：保持邻点值、三乘顺序、八项累加顺序、FP32 及最终 Cast；须补目标 Vector 特殊值行为核验 |
| capacity | 条件化：下述完整字节公式须不超过目标实际可用 UB |
| 状态 | `conditional_plan`，不是 ready/completed/accepted |

**只登记这一个实例。**无需另外登记：

- `batch_vector_api_calls`：原实现并没有这 32 组碎片化 Vector 算术；
- `coalesce_cast`：没有删除数值转换；
- `batch_writeback`：这里是 Vector 结果的配套落地，不是另一个独立目标；
- `keep_intermediate_onchip`：原先没有需要消除的 GM 中间往返。

必要依赖由方案自身兑现：

1. Scalar producer 完成八邻值、六因子和累加初值的写入；
2. 每个 Vector consumer 只消费本 tile 的有效 n 个元素；
3. 八轮计算顺序固定；
4. Cast/写出前等待结果完成；
5. DMA 最后读取结束后才能覆盖对应输出槽；
6. nearest 不进入新暂存或 Vector 插值路径。

---

## 4. C2 共同计划、边界、资源与 KEEP 判断

### 4.1 共同计划 `P1-output-owned-scalar-gather-vector-eval`

完整采用 P 的 `indexing/templates/coordinate_neighborhood.md` 中：

> **输出连续空间块，独立生成几何**骨架。

语义槽位绑定为：

- G：第 106–109 行的 grid 读取与 `GridUnnormalize`；
- B：`GridApplyPadding`；
- H：floor、八邻点和六轴因子；
- F：八项按源码顺序的三乘链及累加；
- 越界读：原 `GridRead`，**先判界再读取**。

不采用该模板的跨通道几何复用和源窗口分支。`gather_output_owned.md` 只采用“输出独占、Scalar 间接取数、批量输出”的原则，**不采用其 GatherElements 完整语义**。

### 4.2 分核和布局

- 原 `blockNum/blockLength` 公式、64B owner 边界不变。
- 每核仍拥有原连续展平输出区间。
- bilinear 内部按 tile 处理，tile 可以跨通道或 batch 边界；每元素仍用原解码公式，不错误地将同一 xBase/gridBase 用到跨界元素。
- x/grid/y 不别名由当前 Host 独立分配支持；不因此向未提供的外部调用 ABI 扩张无别名声明。
- 无跨核归并、原子、GM workspace 或第二 launch。

### 4.3 资源账

采用分离物理区，不做生命周期 alias：

- 8 个 FP32 邻点数组；
- 6 个 FP32 轴因子数组；
- 1 个 FP32 临时乘积数组；
- 1 个 FP32 累加/结果数组；
- FP16 路径另有 half 输出区。

设 `A(B)=AlignUp(B,32)`，tile 容量 T：

\[
U_{\rm FP32}=16A(4T)+U_{\rm framework/API}
\]

\[
U_{\rm FP16}=16A(4T)+A(2T)+U_{\rm framework/API}
\]

纸面首选 **T=256 元素**，不是测得最优值：

- FP32 显式数据区：16,384B；
- FP16 显式数据区：16,896B。

完整容量还必须计入实际框架/API预留。Scalar 局部值、寄存器及 spill 单独核验，不加进 UB 也不假定免费。

C2 许可在 **T∈{256,512,1024}** 中进行容量合法的局部参数选择；改变 T 必须同步重算分配、循环、尾长及调用数。这是有限探索范围，不是新增 shape 阈值。

### 4.4 同步和自由度

采用单槽、保守完成边：

```text
Scalar 写 staging/acc
    → PIPE_ALL
八邻点 Vector 三乘链及逐项累加
    → 必要 PIPE_V 依赖
结果完成
    → Cast（仅 half）
    → 输出发布、DMA
    → 等 DMA 完成后复用
```

本轮不授权：

- 双缓冲、预取和手工缩窄跨引擎事件；
- 几何跨通道驻留；
- 新 owner、源窗口或全局几何表；
- 更改累加树、FMA、低精度计算；
- cache 策略变更或新 workload 阈值。

### 4.5 dispatch 与 KEEP

保留直接启动的 `grid_sampler_3d_kernel`，使用现有 `interpolation/dtype` 分支，不引入 `TILING_KEY_IS`。`dispatch.md` 正文明确该宏不应直接套在 kernel 直调工程上。

纸面 dispatch 身份可按现有 interpolation 值零扩展为 uint64 表示：

| 判据 | 身份值 | 实际 entry/路径 |
|---|---:|---|
| bilinear、合法 dtype | 0 | 同一 entry 内的新分块计算 |
| nearest、合法 dtype | 1 | 同一 entry 内原路径 |
| 非法属性/shape | — | Host 原校验/错误路径，不静默返回 |

这不是新增 ABI Key 字段，后续须核实真实启动和分支身份。

**不记 P_KEEP。**没有已绑定的完整父计划可引用；本次建立共同计划，其中分核是“提取并保持已有策略”，不能统计为并行优化。A1 也不是 O_KEEP；它要求实际改变插值执行方法。因此方案不是 NOOP。nearest 保持原源码路径并不等于整个方案 KEEP。

---

## 5. C3 实现交接：步骤、API 和数值约束

以下是后续获准实施时的具体要求，**本轮未执行**。

### 5.1 修改范围

1. 在隔离候选中保留原 `GridSampler3DOne` 作为对照/回退。
2. 新建 bilinear 分块类，初始化一次 TPipe 和所列物理区，禁止热循环 `InitBuffer`。
3. 使用独立 VECCALC staging；结果搬出采用目标文档支持的 VECOUT 队列/视图，不能仅凭原代码的 VECCALC 输出用法推断所有新搬运重载合法。
4. kernel 的 nearest 继续调用原实现；bilinear 进入新类。
5. Host/tiling 数学分核和 ABI 不变。容量/SDK 检查不能通过时保留原路径，不承诺该静态配置可编译。

### 5.2 Scalar 准备阶段

每个有效 i：

- 按原公式解码并生成坐标；
- 调用原 padding/floor 和 `GridRead<T>`；
- 八邻点按原顺序保存；
- 保存六个 FP32 因子；
- 结果槽设为 `+0.0f`。

保持手工 `GridToFloat<half>`，**本轮不替换为批量 half→float Cast**，避免再混入输入转换数值路径和额外 Action 意图。代价是 half 位展开仍然是残余 Scalar 工作。

### 5.3 Vector 计算

对每个邻点 k，按对应的三个轴因子执行：

```text
tmp = value[k] * factorX[k]
tmp = tmp      * factorY[k]
tmp = tmp      * factorZ[k]
acc = acc     + tmp
```

使用公开的：

- `AscendC::Mul(dst, src0, src1, n)`
- `AscendC::Add(dst, src0, src1, n)`
- 相邻相关指令之间的 `PipeBarrier<PIPE_V>()`

普通 FP32 full repeat 是 64 元素，但本方案优先使用 **count 重载，count 单位为有效元素**；不手工把 n 塞进 mask/repeat。T=256 时每个数组为 1024B，所有首址按分配器至少 32B 对齐。

精确原地 `tmp`/`acc` 更新须按目标 SDK 对该重载的 alias 规则核验；给定 Vector 链正文支持此类表达，但不授权任意部分重叠。如果目标重载不允许所用精确 alias，必须增加独立临时区并重算共同容量，不能强行执行。

不得：

- 预计算三轴权重乘积；
- 跳过权重为零的贡献；
- 把八项改成树形求和；
- 把 Mul＋Add 改成融合乘加；
- 让 padding/dummy 进入有效 n。

### 5.4 输出和尾块

每核长度 L、tile T：

\[
Q=L/T+(L\bmod T\ne0),\quad n_i=\min(T,L-iT)
\]

L=0 不发调用。非空 tile 的 DataCopyPad 参数：

```cpp
AscendC::DataCopyExtParams cp{
    1, n * static_cast<uint32_t>(sizeof(OutputT)), 0, 0, 0
};
AscendC::DataCopyPad(yGm[offset], outputLocal, cp);
```

约束：

- `blockLen` 是有效字节，不向上扩大 GM 写入；
- A3 无 mode 重载，单块长度须 `<2^21`；
- UB 源首址和完整物理跨度合法；
- 所有偏移/乘加先按宽整数验证后再窄化；
- 不混合相邻 owner 的 Scalar 与 DMA 输出；
- 输出 DMA 完成前不能覆盖输出槽。

FP16 继续：

```cpp
AscendC::Cast(raw, acc, AscendC::RoundMode::CAST_NONE, n);
```

`cast.md`/`numeric.md` 明确指出 CAST_NONE 在有精度损失时不是“无舍入”，这里保持原实际路径；不得随意换 TRUNC/FLOOR，也不能删除最终 half 舍入。

### 5.5 P/O 正文如何实际改变选择

| 正文 | 对本方案的具体影响 |
|---|---|
| P `coordinate_neighborhood.md` | 选择输出独占空间块；绑定 G/B/H/F；不把源地址连续或几何复用当作免费条件 |
| P `gather_output_owned.md` | 保留 Scalar 间接读取＋批量输出原则；拒绝未经成本核算的转置/源窗口 |
| O `vector-api/batch.md` | 使用连续 count；不从 Add 的尾行为推断 Compare 合法性 |
| O `vector-api/cast.md`、`precision-boundaries/numeric.md` | 保留最终 Cast、乘法括号和累加顺序，特别保留 `0*Inf` 等特殊值路径 |
| O `memory-transfer/coalesce.md`、`tiling-tail/valid-length.md` | FP32 输出暂存后按有效连续块写出；分开有效字节与物理容量 |
| O `buffer-lifetime/reuse.md`、`bounds.md` | 计算全部独立分配；本轮不做假定 alias，不用词法生存期扣除容量 |
| O `pipeline-sync/pipeline.md` | 单槽保守完成边；不把增加物理槽、队列或历史 sigmoid 收益当作已重叠证据 |
| O `compare-select-tail.md` | 完整坐标向量化不作为本轮附带步骤；其 256B Compare 域和 Select 8KB 临时区必须另计 |
| O `scalar-control/*` | 地址外提保留为竞争替代；当前已经是 GM tiling 指针直读，没有整结构复制可直接删除 |
| Cube/CV、bank-layout 及其 fallback 正文 | 没有相应计算/实际地址条件，明确不采用；不迁入 3510 能力或历史倍率 |

材料中的 exp/tile、sigmoid、预取、UB accumulator 历史记录只支持“调用减少、增槽、减少反馈未必产生有效收益及归因”的判断，不作为本算子的性能证据。

### 5.6 实施前缺项与以后验证

| 缺项 | 影响及处理 |
|---|---|
| 当前工程构建目标、SDK 版本和可用 UB | 决定 API/资源合法性；实施前补齐，不能用标称 192KiB 直接授权 |
| 所选 Mul/Add/Cast 的特殊值、次正规数及精确 alias 行为 | 决定数值合法性；按目标 API 与后续测试闭合 |
| 编译器当前 Scalar 指令、CSE、FMA、spill | 影响方案价值和资源；不声称当前已存在 spill |
| 实际输入数据和完整 oracle 运行 | 源码分析不能替代正确性 |
| Task 时间、UB/Scalar/MTE timeline | 检验收益及额外暂存是否抵消；本轮均未测 |

后续完整验证至少覆盖全部 20 case，以及 n 为 1、63/64/65、T±1、跨平面/批次 tile、末核空区间、S=1 reflection、round-even 中点、区间外重复 reflection、NaN/±Inf 输入、最大 half 和次正规数。

原 verifier 的特殊值 mask、MERE/MARE 和误差 floor 保持不变。其通过条件是 `special_ok`、MERE 小于 dtype threshold、MARE 小于十倍 threshold，不能只看平均误差。

Host 目前输出的 `kernel_us` 是 launch＋stream synchronize 的主机墙钟范围，**不是设备 Task Duration**；以后不能拿它直接声称 Vector 或 MTE 阶段加速。

---

## 6. 下一轮可复用的三部分简短摘要

### 当前状态

用户授权一轮、仅纸面方案与 C2/C3 交接；禁止修改、编译、工具及硬件。本轮未产生候选源码或测试结果，原实现仍是唯一实际工程。目标为用户指定的 910C/dav-2201，设备核数、SDK、可用 UB 未探测。采用本回答的当前实现理解与 `P1-output-owned-scalar-gather-vector-eval` 条件计划；性能 `not_measured`，正式接纳 `not_evaluated`。

### 已尝试路线

仅完成 `S1-trilinear-vector-evaluation` 的静态比较和交接：以一个 `action.vectorize_scalar_loop` 实例向量化八项三乘链及累加；保持坐标、间接取数、owner 和 nearest。未实施、未通过正确性、未计时。主要新增成本是约 16 个 FP32 tile 数组、Scalar staging 和 Vector UB 访问；无单项或整体收益结论。

### 剩余机会

1. **跨通道几何复用**：重复关系已由源码支持，但缺准确注册意图；保留独立提案，不冒充原输入驻留。
2. **地址分段外提＋FP32 批量输出**：是所选方案暂存代价过高时的强替代。
3. **nearest 主循环**：本方案保持原样，尤其 case 5 的大规模采样未解决。
4. **完整坐标向量化、源窗口、同步流水、缓存策略**：各自需要具体 API、地址局部性或阶段证据后再比较，不是强制下一轮清单。

**未测限制：**当前判断只能证明源码结构、工作量模型和条件计划的可解释性，不能证明目标 SDK 可构建、完整数值正确、实际消除了相同比例的指令，更不能证明加速。