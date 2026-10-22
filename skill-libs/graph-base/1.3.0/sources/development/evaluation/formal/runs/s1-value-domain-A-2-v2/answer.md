## 结论与边界

本轮选择一个共同方案用于 a、b：**把一个输出空间片的八邻居一次 Gather 到 UB，再按原数值路径消费；同时把该 workload 的物理空间片跨度从 1920 收紧到 256。**

- **a**：八邻居乘权合为一次连续 `Mul`，随后仍按 `k=0…7` 做八次有序 `Add`。
- **b**：一次调用现有 `GridSoftwareWeighted(..., neighbors=8)`，仍逐输出执行八次正确的 `GridFma32Bits`。**不删除、不替换、不缩小软件 FMA 的触发域。**
- 两例使用同一元数据选择条件和同一候选；不能根据输入分布派发。
- 登记一个 `action.batch_vector_api_calls` 实例即可。八邻居值区扩展、tile 收紧和消费者接线是完成 Gather 合批所需的配套修改，不另凑 Action。

这是**有明确实现步骤的条件化纸面方案**，不是已经完成的 C3 候选。未使用工具，未生成 hash、未编译、未验证正确性或测量性能。目标可用 UB、完整 Host/启动接线与实际 SDK 重载仍须在实施前核验。

---

## 一、共同的当前执行模型

### 1. 实际路径，而不是原始 Scalar 路径

题目明确本次执行 `GridSampler3DWeighted<float>`，因此原始文件的 `GridSampler3DScalar<float>` 不能作为当前工作量基线。实际链是：

```text
grid[N,S,3]
  → GridGeometryRange
  → GM geometry：8组空间字节偏移 + 8组float权重
  → Weighted：整通道X搬入本核UB并检测数值路径
  → 分两组Gather，每组4邻居
  → 普通Mul/Add 或 整数实现的软件FMA
  → 连续有效输出写回
```

`GridGeometryRange:244–270` 已经按 `(n,p)` 生成几何，跨通道共享；**当前没有每输出重复生成八邻居几何的工作可再消除。**

外部地址：

\[
X[n,c,z,y,x]\mapsto (((nC+c)D+z)H+y)W+x
\]

\[
Y[n,c,p]\mapsto (nC+c)S+p
\]

geometry 中的索引是**通道内部字节偏移**，越界返回 `inputSpatial*sizeof(float)`，指向 UB cache 中显式写入的零哨兵。

### 2. 数学和数值依赖

本例 `alignCorners=false`，每轴：

\[
i=((g+1)\cdot16-1)\cdot0.5
\]

给定 grid 在 `[-0.8,0.8]`，归一化后约为 `[1.1,13.9]`，八邻居坐标均位于 `[1,14]`，所以本次八邻居全部有效；实现仍须保留一般越界哨兵机制。

权重严格保留源码的两次乘法：

\[
w_k=\operatorname{fl}(\operatorname{fl}(w_xw_y)w_z)
\]

之后有两种不同的外部契约路径：

- 普通路径：
  \[
  a_{k+1}=\operatorname{fl}(a_k+\operatorname{fl}(v_kw_k))
  \]
- 软件路径：
  \[
  a_{k+1}=\mathrm{binary32FMA}(v_k,w_k,a_k)
  \]

均从 `+0.0f` 开始，按 `k=0…7` 顺序递推。两者不能互换，不能改成树归约、先求部分和或普通硬件乘加。

### 3. 当前容量及有效工作

空间输入长度：

\[
I=16^3=4096,\quad NCS=2048
\]

由 `Weighted::Init:457–460`：

\[
cb=4\left(\left\lfloor\frac{4096+64}{64}\right\rfloor64\right)
  =16640\text{ B}
\]

当前 `tile_=1920`。FP32 显式 TBuf 分配：

| 区域 | 字节 |
|---|---:|
| cache | 16,640 |
| index，8×1920×4 | 61,440 |
| weight，8×1920×4 | 61,440 |
| values，4×1920×4 | 30,720 |
| acc，1920×4 | 7,680 |
| **合计** | **177,920** |

不把源码中的 `196352` 当作已经核验的设备可用 UB。

每次循环还被通道边界限制到 `count≤256`，但 Gather 固定执行 `4*1920` 元素，且分两组。因此每个有效片：

- Gather：2 次，共 **15,360 个目的槽**；
- 有效邻居最多只有 `8*256=2048` 个；
- 因 `count!=tile_`，每片会初始化 `8*1920=15360` 个 index 槽。

这不是“尾部必然慢”的测量结论，但确实存在可量化的过大物理执行域。

### 4. 分核数量不能补猜

可见 Weighted 按 `[blockIdx*blockLength,end)` 独占连续输出；实际启动核数和新版 Host 未完整给出。

令：

- \(J\)：所有有效 block 区间与八个通道输出平面的非空交集数；
- \(q_j\)：第 \(j\) 个交集的有效输出数。

当前每个交集只需一次循环，满足：

\[
1\le q_j\le256,\qquad \sum_jq_j=2048,\qquad J\ge8
\]

本轮保留这些所有权和执行次序，不通过假定某个物理核数计算收益。

---

## 二、子例 a：普通加权路径

### 当前事实

所有通道输入在 `[-1,1]`，所以 `GridNeedsFma32` 的正、负阈值检测都不命中，执行 `GridApplyWeightedFour` 普通分支。

每片当前：

- 两次四邻居 Gather；
- 八次 `Mul(..., count=q_j)`；
- 八次顺序 `Add(..., count=q_j)`；
- 不执行 `GridFma32Bits`。

全输出有效算术为：

- 16,384 次乘权；
- 16,384 次累加；
- 权重生成已在 geometry 阶段完成。

这些是元素级逻辑次数，不是设备指令数或时间占比。

### 主方案

物理跨度取 \(T=256\)，将 values 改为八平面：

```text
values[k*T+p]，k∈[0,8)，p∈[0,T)
```

每片执行：

1. 一次 `Gather(values,cache,idx,0,8*T)`；
2. 一次 `Mul(values,values,coeff,8*T)`；
3. 依次执行八次 `Add(acc,acc,values[k*T],q_j)`；
4. 只写 `q_j*4` 有效输出字节。

短片的 index dummy 指向零哨兵；由于连续 Mul 将读取完整权重区，**短片必须显式定义 coeff dummy**。可先对整个 `8*T` 权重区置零再搬入有效权重，预算这笔覆盖写，不能假设 `isPad=false` 自动清零。

主要变化：

| 工作 | 当前 | 主方案 |
|---|---:|---:|
| Gather API | \(2J\) | \(J\) |
| Gather 目的槽 | \(15360J\) | \(2048J\) |
| Mul API | \(8J\) | \(J\) |
| Mul 元素数 | 16,384 | \(2048J\) |
| 有序 Add API | \(8J\) | \(8J\) |
| 有效 Add 元素数 | 16,384 | 16,384 |

新增的 dummy 乘法数为：

\[
8\sum_j(256-q_j)=2048J-16384
\]

因此，**API 减少不等于算术减少**。若每通道完整处理、\(J=8\)，无新增 dummy 乘法；若分核将通道切碎，dummy 工作和短片权重初始化都会增长。

### 最有竞争力的替代

**仍保留四邻居 values，但同样使用 T=256；每组四次 Mul 合为一次 `Mul(...,4*T)`。**

其每片：

- Gather 2 次、共 2048 槽；
- Mul 2 次、共 2048 元素；
- Add 8 次，顺序不变；
- 同样需要为快路径 dummy 权重初始化。

显式 UB：

\[
16640+84T=38144\text{ B}
\]

相比主方案少 4096 B；但每片多一次 Gather 和一次 Mul，并保留组间控制。它是实际有竞争力的替代，不是原版陪衬。

**本轮选择主方案的理由**：八邻居全部同时驻留仍只有 42,240 B 显式分配；在不改变 owner、GM 有效流量和累加顺序的前提下，能进一步减少调用。若实际 SDK scratch 或短片初始化成本改变这一比较，应回选四邻居紧凑方案，而不是宣称八邻居必快。

---

## 三、子例 b：通道级软件 FMA 路径

### 当前事实与不可删依赖

每通道最后一个元素为 \(2^{125}\)，正阈值检测命中，因此：

- `GridNeedsFma32` 返回 true；
- `||` 短路，负向扫描不执行；
- 该通道的全部有效输出进入软件加权路径。

**该大值没有被任何采样邻居读取，并不能取消这个分支。** 当前分支依据整个通道 cache，而非当前邻居集合。即使实际邻居全在 `[-1,1]`，软件 FMA 与普通 Mul/Add 仍可能在舍入上不同。

当前全输出执行：

\[
2048\times8=16384
\]

次 `GridFma32Bits`。它们是整数软件实现调用，不能按一条硬件 FMA 的成本计数。

每片分两次软件调用，各处理四邻居；每次对每个输出读一次 acc、写一次 acc。

### 主方案

仍采用同一个八邻居 Gather、T=256 的布局，软件消费者改为：

```cpp
GridSoftwareWeighted(values, coeff, acc,
                     0, 8, T, count);
```

这直接使用已给函数的 `neighbors` 参数，不需要改写未展示的 `GridFma32Bits`。

等价性依据：旧路径在 k=3 后将 uint32 累加位模式写入 acc，再于第二组原样读回；新路径把相同位模式保留在局部 `sum`，继续 k=4…7。没有新增浮点转换、没有改变八次调用参数或顺序。

变化为：

| 工作 | 当前 | 主方案 |
|---|---:|---:|
| Gather API | \(2J\) | \(J\) |
| Gather 目的槽 | \(15360J\) | \(2048J\) |
| 软件加权函数调用 | \(2J\) | \(J\) |
| `GridFma32Bits` | 16,384 | **16,384，不变** |
| acc 标量 GetValue | 4,096 | 2,048 |
| acc 标量 SetValue | 4,096 | 2,048 |
| 软件函数内入口/出口 `PIPE_ALL` | \(4J\) | \(2J\) |

values 与 coeff 的有效标量读取次数不变：各 16,384 次。软件路径只消费 `count`，不需要为了软件计算初始化 coeff dummy。

### 最有竞争力的替代

仍是 **T=256 的四邻居紧凑方案**：

- Gather 总槽数同为 `2048J`；
- UB 为 38,144 B；
- 继续两次软件加权，保留组间 acc 读写和两组软件完成边；
- 软件 FMA 数量仍为 16,384。

主方案多用 4096 B，换取一次 Gather、一次软件函数边界，以及每输出一次 acc 读写的消除。它没有解决软件 FMA 本体成本，因此 **b 的净收益可能比 a 更受限制**，不能用 a 的 API 减少推导 b 的加速。

“把整数 FMA 本体 SIMD 化”可能更有上限，但当前输入没有整数实现正文和相应目标 API 等价链，无法证明特殊值、次正规数、舍入和进位行为。该方向登记为**具体能力缺口**，本轮不实施，也不借普通浮点 Vector 指令替代。

---

## 四、Action 实例与采用边界

### 实例 A1：`action.batch_vector_api_calls`

- **任务/父实现**：本题 Weighted<float> 摘录 `454–485`。
- **目标**：八邻居 Gather 调用及其 values 消费链。
- **阶段**：geometry 已完成后的 Weighted 计算阶段。
- **workload 域**：FP32，N=1、C=8、D=H=W=16、S=256，bilinear/zeros/alignCorners=false；输入内容不作为派发条件。
- **变换**：两次四邻居 Gather 合为一次八邻居 Gather；普通路径合批乘权；软件路径接到八邻居消费者。
- **保持**：通道级检测、geometry、k 顺序、两种数值路径、输出 owner、有效 GM 访问范围。

实施前条件：

1. **合批兼容性**：同一 cache、相同 dtype、八平面 index 连续；`8*T=2048` 的现有 Gather count 重载须核验。
2. **语义等价**：普通 Add 顺序不变；软件调用的八次整数 FMA 参数和顺序不变。
3. **容量合法**：满足下节完整预算，不把显式 TBuf 总和当全部资源。
4. **依赖合法**：新增八平面值的最后读者完成后才能复用。

材料未提供可计算的模板/源码 hash，故这里只能用给定版本和行定位绑定，**不能声称正式注册校验已完成**。

---

## 五、统一 C2 共同计划

### 所有权、布局与 workspace

保留当前线性输出分核和通道边界截断，不新增任务、不合并跨核结果、无原子和跨核归约。

- X/Y：外部 NCDHW 不变。
- geometry：GM 中八平面 index、八平面 weight 不变。
- UB：index、coeff、values 均使用 `k*T+p`，T=256。
- cache：完整 4096 个输入值，加合法零哨兵和原对齐空间。
- acc：256 个 float。
- geometry 有效 workspace：
  \[
  16NS\times4=16384\text{ B}
  \]
  不含未知框架保留区；本轮不删减其分配。
- geometry 的生产完成必须先于 Weighted 消费；现有跨阶段接线未展示，不能以核内 barrier 代替。

### 共同容量

新显式分配：

\[
U_{\rm explicit}=16640+(32+32+32+4)T
\]

T=256 时：

\[
U_{\rm explicit}=42240\text{ B}
\]

比当前显式分配少 135,680 B。完整门禁仍为：

\[
42240+B_{\rm API}+B_{\rm compiler/framework}\le U_{\rm available}
\]

不新增双缓冲，不手排 bank 地址，不把 VECIN/VECCALC/VECOUT 当不同容量池。

检测阶段继续借用尚未存活的 index 和 acc：

- 4096 输入对应 128 个 mask word；
- 新 index 有 2048 个 uint32 槽；
- 新 acc 有 256 个 uint32 槽，覆盖 helper 对 temp 前 128 word 的使用；
- 检测结束后才能覆盖成真实 index/acc。

### 同步与生命周期

保留保守完成关系：

1. cache 初始化与输入 DMA 完成 → 数值检测和 Gather；
2. 检测 scratch 最后使用完成 → index/acc 重建；
3. index/coeff 搬入完成 → Gather/乘权/软件读；
4. Gather 完成 → values 消费；
5. 普通 Mul 完成 → 八次有序 Add；每次 Add 保留递推依赖；
6. 软件入口/出口保留原完成机制；
7. acc 就绪 → MTE3；MTE3 读完 → 下片复用。

本轮不是同步收窄方案；少掉的是被合并调用原有的组间边界，不夹带全局删 barrier。

### KEEP 与派发依据

不能冒充已有完整计划的 `P_KEEP`：当前未给正式父计划，且 values 布局、物理 tile 和消费窗口均改变。记录为 **P_CHANGE：提取原所有权，并实际修改核内布局/执行片跨度**；不是并行度优化。

不新增性能分组 Key。优先在当前 Weighted 调用路径内按上述元数据条件选择候选 helper，其他元数据保持原 fallback。a、b 必须命中同一实现。实际 Host、entry、key 身份缺失，C3 接线前必须补齐；不能用原始 Scalar entry 冒充 Weighted 的实际入口。

---

## 六、C3 准确实施步骤及正文影响

以下是交接步骤，不表示已经修改：

1. 固定实际 Weighted 父源码、tiling ABI、Host 调用和目标 SDK；保留原实现作 fallback。
2. 在既定元数据域内设 T=256，按 T 重算 index/weight/values/acc 分配；values 分配为 `8*T*4`。
3. 保留整通道输入搬运、零哨兵和 `GridNeedsFma32` 的位置、count 与短路语义。
4. 将 geometry 的 UB 行跨度和搬运参数全部改为 T：
   - `blockCount=8`；
   - `blockLen=count*4` 字节；
   - GM `srcStride=(geometryLength-count)*4` 字节；
   - UB `dstStride=(T*4-AlignUp(count*4,32))/32`。
5. 短片按原哨兵规则定义 index；普通路径额外定义 coeff dummy，并计入初始化工作。不得扩大 GM 读长。
6. 一次 Gather 八平面。
7. 普通路径：一次完整八平面 Mul，随后 k=0…7、每次有效 count 的 Add。
8. 软件路径：一次现有八邻居软件调用，保留 `GridFma32Bits` 实现和全部特殊值行为。
9. 仅写有效 `count*4` 字节，保留最终完成和 buffer 复用依赖。
10. 后续获执行授权后，先审查和完整正确性，再比较包含 geometry 的完整调用链；不得只测缩短后的局部 Gather。

实际采用知识及其影响：

- **P `planning.indexing.coordinate_neighborhood`**：绑定现有 G/B/H/F；强调几何与 X 的依赖轴不同，故不重复“优化”已经共享的 geometry。
- **O `implementation.vector-api.batch`**：决定只合并独立 Gather/乘权，不能合并八次有递推依赖的 Add；显式计入 dummy lane。
- **O `implementation.memory-transfer.strided-pad`、`tiling-tail.valid-length`**：落实 GM 字节 stride、UB 32B block stride和有效 count/物理跨度分离。
- **O `implementation.buffer-lifetime.reuse`**：保留检测 scratch 的分时租约；八平面 values 与检测/输出生命周期分别核算。
- **O `implementation.precision-boundaries.numeric`**：禁止因邻居值较小取消软件 FMA，也禁止普通和 fused 数值路径互换。
- **O `compare_select_tail`**：用于核对既有检测的完整 256B 比较执行域、int32 EQ 压缩和尾位清除；本轮不新增 Select，因此不无依据增加其 8KB 临时区。

这些是正文对方案的实际约束，不是已运行 router 或通过机器契约校验的声明。

---

## 七、后继可复用摘要与待验证项

### 当前状态

- 保留实现：题目给定 Weighted<float>，未修改。
- 探索方案：A1 八邻居合批、T=256，**paper / conditional_plan / not_measured**。
- a：普通 Mul/Add；b：通道级软件 FMA，二者同元数据派发。
- 无正确性通过、硬件收益或正式晋升结论。

### 已分析路线

| 路线 | 静态可确认变化 | 限制 |
|---|---|---|
| 八邻居主方案 | Gather 2→1；巨大 dummy Gather 域收紧；a 的 Mul 8→1；b 的软件组边界2→1 | b 的16,384次整数FMA完全保留 |
| 四邻居紧凑替代 | 同样消除过大的 Gather padding；少用4096 B UB | 多一次 Gather；b保留组间acc反馈 |
| 软件FMA本体向量化 | 潜在覆盖主要软件工作 | 缺实现正文和精确目标API等价证明，未实施 |
| 改检测为只看采样邻居 | 可能绕开b软件分支 | **违反当前数值路径契约，不采用** |

### 最重要的待验证事项

1. **实施门禁**：实际 SDK Gather/Mul 重载、隐含 scratch、可用 UB、完整 Host/entry/geometry 完成协议及输入输出别名合同。
2. **数值验证**：逐位核对两种路径；包含 ±0、次正规数、NaN/Inf、阈值 `±2^124` 两侧、抵消和舍入中点，不能只测 a/b 的普通随机值。
3. **边界验证**：完整通道、通道被 block 切碎、短 count、空 block、哨兵索引和检测 scratch 覆盖。
4. **性能判别**：记录实际 \(J\)、dummy 初始化、编译后的调用/控制、软件 FMA 占用和完整 Task 时间。
5. 若短片多使 a 的 dummy 乘法/初始化抵消调用节省，重开四邻居紧凑替代；若 b 时间几乎全由整数 FMA 决定，说明本轮优化覆盖有限，**不据此放宽数值契约**。