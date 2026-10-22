## 一、结论与交接状态

两个子例均选择同一完整方案：

> **保持原分核、整通道缓存和数值分支，把每个输出片的八邻居索引压紧到实际执行跨度，一次 Gather 八个邻居平面，再按原来的两个四邻居组消费。**

登记一个注册 Action 实例即可：`action.batch_vector_api_calls`，目标是合并 `GridSampler3DWeighted<float>::Process` 中的两次 Gather。索引布局、八平面 value 区、容量参数及尾部处理是完成该合批所必需的配套，不另凑 Action。

- **子例 a**：保留 Vector Mul→Add 路径；减少 Gather 过量执行、索引初始化及一次 Gather 发射。
- **子例 b**：仍必须走整数软件 FMA；相同方案仅减少外围 Gather/准备工作，**不减少任何软件 FMA 调用**。因此相较 a，未改变的昂贵工作更多，净收益预测更弱，但不是安全或静态试验的否决理由。
- 不把 a/b 的输入分布写入 Host 派发条件，两者执行同一元数据分支、各自运行原 `GridNeedsFma32`。
- 本答复是**条件化 C2 计划和 C3 实施交接**，未修改、构建、运行或验证。目标实际可用 UB、当前启动接线及实现身份尚未闭合，不标记 C3 completed。

---

## 二、当前实际执行模型

### 2.1 实际对象不是原始 Scalar 版本

本题明确执行后续摘录中的 `GridSampler3DWeighted<float>`，不能用原始 `GridSampler3DOne<float>` 的逐输出坐标计算作为当前主要工作。

当前阶段链为：

```text
grid
  → GridGeometryRange：每个 (n,p) 计算一次八邻居 byte offset 和权重
  → GM geometry 表
  → Weighted：整通道 X 搬入 UB、检查数值分支
  → 搬入本输出片的索引/权重
  → 两次四平面 UB Gather
  → 按 k=0…7 原序加权累加
  → 连续有效输出写回
```

geometry 的具体 launch、workspace 分配者和阶段同步代码未给出；其预计算完成是题设前提，实际工程接线仍须核验。

### 2.2 数学与数值依赖

令 \(I=DHW=4096\)、\(S=256\)、\(P=NS=256\)。

对本题有限 grid，单轴反归一化为：

\[
u=((g+1)\cdot16-1)\cdot0.5
\]

`g∈[-0.8,0.8]` 对应约 `[1.1,13.9]`，八邻居均在输入内部。该事实用于解释本题实际读取，**不能据此删除通用边界处理**。

geometry 对每个点保存：

- `offset[k,p]`：相对于通道起点的 uint32 **字节偏移**；
- `weight[k,p]`：按源码先 `wx*wy`、再乘 `wz` 生成的 binary32 权重；
- 越界 offset 使用 `I*sizeof(float)=16384`，指向 UB cache 中显式设置的零哨兵。

累加必须分别保持两条实际路径：

- `software=false`：
  \[
  a_0=+0,\quad a_{k+1}=\operatorname{Add32}
  (a_k,\operatorname{Mul32}(v_k,w_k))
  \]
- `software=true`：
  \[
  a_0=+0,\quad a_{k+1}=\operatorname{GridFma32Bits}(v_k,w_k,a_k)
  \]

二者不能互换。软件 FMA 是正确 binary32 fused multiply-add 的整数算法，不是一次硬件 FMA。

### 2.3 当前 tile 与工作量

由 Weighted `Init:457–460`：

\[
cb=\frac{4096+64}{64}\cdot64\cdot4=16640\text{ B}
\]

\[
T_0=\left\lfloor
\frac{196352-8192-16640}{128\cdot84}
\right\rfloor\cdot128=1920
\]

显式 UB 分配：

| 区域 | 字节 |
|---|---:|
| cache | 16640 |
| index，8 平面 | 61440 |
| weight，8 平面 | 61440 |
| value，4 平面 | 30720 |
| acc | 7680 |
| **合计** | **177920** |

其中源码中的 `8192` 是预算扣除项，不能仅凭该常数认定存在某个具体 API 的 8KB scratch。

每轮 `count` 还被通道的剩余 `S-sp` 截断，所以本题所有有效片都有 `count≤256<1920`。但当前仍然：

- 每片 `Duplicate(idx, sentinel, 8*1920)`；
- 两次 Gather 各处理 `4*1920=7680` 个 float；
- 合计 Gather 写出 **15360 个 value 元素/片**；
- 只有 `8*count` 个 value 最终参与数值计算。

令 \(F\) 为当前核分区与八个通道输出区间相交形成的非空片数。实际 `blockNum/blockLength` 未完整给出，不能假设固定核数。各片满足：

\[
\sum_{f=1}^{F}count_f=2048
\]

当前主要逻辑请求量为：

- X 整通道载入：本题每个非空通道片一次，约 `16384F B`；
- geometry 的索引和权重读：`2048×8×(4+4)=131072 B`；
- 输出写：`2048×4=8192 B`；
- geometry 有效存储：`256×8×(4+4)=16384 B`；
- Gather 执行元素：`15360F`。

这些是源码逻辑访问/执行量，不是 HBM 流量或耗时。

---

## 三、子例 a：实际路径、选择与替代

### 3.1 关键事实

每个通道所有 X 均在 `[-1,1]`，所以整通道的两个阈值检测均为 false：

```text
GridNeedsFma32(cache) == false
```

实际执行：

- 每次 cache 装入后，正、负两个方向各检查一次；
- 两组四邻居都执行 Vector Mul，然后顺序 Add；
- 全输出共有 `16384` 个有效乘法元素和 `16384` 个有效加法元素；
- 没有执行 `GridSoftwareWeighted`。

已有坐标/权重预计算和通道 cache 已经存在，不再把“消除每通道几何重算”“首次建立 X 缓存”计为新收益。

### 3.2 主方案

取本元数据域最大片容量 \(T=256\)。每片设置：

\[
R=\operatorname{AlignUp}(count,8)
\]

`R` 是 **float/uint32 元素单位的平面跨度**，使每平面占 `4R` 字节、满足 32B 对齐。

将八个索引平面搬成 `[8,R]`，一次：

```text
Gather(values8, cache, idx, 0, 8R)
```

随后仍按原顺序：

```text
原四邻居函数(values8[0],   coeff, acc, group=0, stride=R, count)
原四邻居函数(values8[4R], coeff, acc, group=4, stride=R, count)
```

不合并或重排八次累加。

工作变化：

| 项目 | 当前 | 主方案 |
|---|---:|---:|
| Gather 调用/片 | 2 | 1 |
| Gather 执行元素/片 | 15360 | `8R` |
| index 全 tile 预初始化/片 | 15360 uint32 元素 | 删除，DMA 定义所有被 Gather 读取的索引 |
| 有效 Mul/Add | 各 `8count` | 不变 |
| X 搬入、检测、geometry 有效读、输出写 | 原量 | 不变 |

一般上界：

\[
\sum 8R_f\le 16384+56F
\]

若实际沿用已给 tiling 的 16 元素分核边界，则本题各片 `count` 都为 16 的倍数，故 `R=count`，总 Gather 执行元素恰为 **16384**。是否沿用该 tiling 需查实际父实现，不能把旧摘录的 Host 公式无条件当作新版本事实。

### 3.3 最有竞争力替代：只压紧，不合并 Gather

同样取 `T=256` 和动态 `R`，但保留四平面 values 区和两次 `Gather(...,4R)`。

它同样做到：

- 删除大范围 index 初始化；
- 总 Gather 元素降到 `8R`；
- 所有有效计算、GM 请求和数值顺序不变。

与主方案相比：

- 多一次 Gather 发射和对应的 Gather 就绪点；
- 少分配 `4T*4=4096 B`；
- 更接近原分组结构。

**选择主方案的理由**：两次 Gather 的源 cache、索引及结果互不冲突，第二组取数可安全提前；八平面显式布局只增加 4KB，且总分配远小于父本。它检验的是“压紧后再合批是否值得这 4KB”，不是把全部收益归于调用数下降。

若新增 4KB 导致实际容量不合法，或实测一次大 Gather 不如两次小 Gather，应返回这条替代；不需要改数值算法。

---

## 四、子例 b：实际路径、选择与替代

### 4.1 与 a 不同的关键事实

每个通道末元素为 \(2^{125}\)，它满足：

\[
2^{125}\ge2^{124}
\]

`GridNeedsFma32` 检查的是**整个通道 cache**，不是采样命中的值。因此：

```text
GridNeedsFma32(cache) == true
```

正方向检测已为 true，`||` 短路，不必执行负方向检测。即使所有八邻居都不含该元素，仍须对该通道所有采样执行软件路径。

全输出仍有：

\[
2048\times8=16384
\]

次 `GridFma32Bits` 调用；不能因采样值都很小就改为 Vector Mul+Add，二者舍入本就可能不同。

### 4.2 主方案及成本变化

仍选择第三节的八平面紧凑 Gather 方案，**不是另一个按数据分布派发的实现**。

减少的 index 初始化、Gather lane 数及调用数与 a 相同；同时：

- 原整通道检测保留；
- `GridSoftwareWeighted` 的 `p` 循环、`k` 循环和整数 FMA 完整保留；
- 第一组结果仍作为第二组初始 acc；
- 不新增浮点转换、近似或硬件 fused 指令替代。

与 a 相比，这些外围工作减少面对的是 **16384 次未改变的整数软件 FMA**。因此主方案解决的占比可能更小；其实际时间占比未知，不宣称软件 FMA 已测为瓶颈。

### 4.3 最有竞争力替代

**直接可实施的最强替代仍是“压紧四平面、保留两次 Gather”**，其全部变化和 4KB 容量优势同上。b 的软件计算期间原值需保留，但主方案的八平面 value 都是只读输入，不引入新的破坏性别名。

另一个可能更大、但当前不能完整交付的方向是：

> 沿独立输出点 `p`，批量实现完全等价的整数 binary32 FMA。

它可由 `action.vectorize_scalar_loop` 表达意图，但本输入只承诺 `GridFma32Bits` 正确，未提供其整数实现正文，也没有可直接替换的 2201 等价 Vector 实现。无法逐项证明多字移位、进位、规格化、舍入及特殊值语义，故**不注册为本轮可实施成员**。这是真正的实现/精度能力缺口，不是“缺性能 profile”。

以下方案明确不采用：

- 只检测被采样的 X，以绕过软件路径；
- 因采样未命中大值而强制 `software=false`；
- 普通 Mul+Add 或未经证明的硬件 FMA 替换整数函数。

它们改变外部要求的数值路径。

---

## 五、Action 实例与知识正文的实际影响

### 5.1 本轮实例

**实例名：`A_Gather8Compact`**

- 注册 Action：`action.batch_vector_api_calls`，输入所给 v0006 正文。
- 父实现：本题 Weighted 摘录 `454–485` 及其检测/加权函数。
- target：两次 `Gather(values,cache,idx[group*tile_],0,4*tile_)`。
- stage：geometry 搬入完成后、两组加权消费之前。
- workload：FP32，N=1、C=8、D=H=W=16、S=256，bilinear、zeros、alignCorners=false；a/b 同实例。
- 合批映射：
  \[
  values8[kR+p]=cache[offset[k,p]/4],\quad k=0…7
  \]
- 不变量：有效输出覆盖及 owner 不变；原判定域、权重位模式、八邻居消费顺序及每条数值路径不变。

`vector_batch_compatibility` 的静态依据：

1. 两组 Gather 读同一个未被加权函数修改的 cache；
2. index 只读，无跨组依赖；
3. 新目的八平面物理独立；
4. 使用当前已有 Gather 重载，新最大 count 为 2048，小于父本单次 7680；
5. 不跨输出片、不跨核合批；
6. 第二组取数提前，但第二组累加不提前。

这支持纸面方案；实际 SDK 重载、容量及启动接线仍须在实施前确认。未提供或计算源码/template hash，不伪造精确 hash 和注册回执。

### 5.2 正文如何改变选择

- **`action.batch_vector_api_calls` / O `vector-api.batch`**：要求明确可合批映射和读写依赖；因此只合并 Gather，**不把八次依赖 acc 的 Add 合并成归约**。
- **P `planning.indexing.coordinate_neighborhood`**：用于绑定坐标、边界、八邻居和数值消费槽位；它是条件骨架，不是上游 GridSampler 移植证明。本轮保持 geometry 预计算和原 owner，不重新生成几何。
- **O `memory-transfer.strided-pad`**：使 GM stride、UB 平面跨度和有效长度分别计算；由显式 index padding 定义 Gather 的完整读取域，避免继续清整个 1920 tile。
- **O `buffer-lifetime.reuse`**：这里保留的是更多同时存活的 Gather 结果，不是不同值共享地址；因此老四平面和新八平面不能同时各算一份，也不能把需要的八平面取 `max` 凑容量。
- **O `precision-boundaries.numeric/bounds`**：要求保留软件 fused 路径、逐 k 顺序和零哨兵；阻止 b 按命中值缩小检测域。
- **P `elementwise.continuous`**：只参考连续输出 owner 原则，不完整套用其“同下标输入”算法，因为源访问是间接寻址。

没有运行内部 router，不声称获得机器路由命中。以上是仅依据已提供正文作出的人工采用记录。

---

## 六、统一 C2：所有权、布局、同步与容量

### 6.1 所有权和覆盖

- 原核区间 `[blockIdx*blockLength,end)` 不变。
- 每片仍在通道边界截断，不跨通道缓存身份。
- 输出 `[nc*S+sp,nc*S+sp+count)` 唯一归原核。
- 无 partial、原子、跨核归并或新增跨核同步。
- X/cache、geometry 只读；输入输出别名合同沿用父本，不能新增未经证明的 in-place 支持。

### 6.2 新 UB 布局

固定最大容量 \(T=256\)，每片实际平面跨度 \(R=\lceil count/8\rceil8\)。

| 物理分配 | 最大字节 |
|---|---:|
| cache，保持原式及哨兵 | 16640 |
| index `[8,T]` | 8192 |
| coeff `[8,T]` | 8192 |
| values `[8,T]` | 8192 |
| acc `[T]` | 1024 |
| **显式合计** | **42240** |

一般公式：

\[
U_{\rm explicit}=cb+100T
\]

还须满足：

\[
42240+B_{\rm API/框架/其他预留}\le U_{\rm available}
\]

不能把源码常数 `196352` 当作已探测可用容量。

特别审计 `GridNeedsFma32` 的借用：

- 检查 `count=4096` 时 firstMask 需要 128 个 uint32，即 512B；
- temp 会使用到 `temp[64]` 所在区，保守保留 128 个 uint32，即 512B；
- 新 index 8192B、新 acc 1024B 足够该可见访问；
- 检测发生在 geometry 搬入和 acc 初始化之前，仍是死区租约，不破坏活索引或累加值。

### 6.3 geometry/workspace

- geometry 布局不变：前 `8P` 个 uint32 offset，后 `8P` 个 float weight。
- 本题有效 geometry 为 16384B，框架保留区未知。
- 无新增 GM workspace，也不缩减未知框架段。
- 保留 geometry 生产完成→Weighted 消费的原阶段依赖；不能用核内 barrier 代替跨 kernel/跨核完成。

### 6.4 同步闭环

必须保持：

1. cache 初始化和 DMA 完成后才能检测或 Gather；
2. 检测对 index/acc scratch 的使用完成后，才能覆盖为本片数据；
3. index/coeff 搬入完成后才能 Gather/加权；
4. 单次八平面 Gather 完成后，才能进行标量读取或 Vector Mul；
5. 第一组 acc 更新完成后才能进入第二组；
6. 输出完成后才能 MTE3 写回；
7. MTE3 读完 acc 后才能下一片初始化 acc；
8. 所有 values 读者结束后才能下一片 Gather 覆写。

初次候选保留父本保守完成边，不顺便做软件流水或全面收窄 barrier。合并两次 Gather 自然消失一个 Gather 专属就绪点，但原保护其他对象的完成边不能随之删除。

### 6.5 派发与 KEEP

只允许按实际元数据选择上述资源域，a/b 不分流。未列 shape、dtype、模式保持原通用 fallback；不新增以数据值或 case 名为条件的 key。

当前没有覆盖本变换的完整父计划及其自由度，因此**不宣称 P_KEEP**：

- 提取原所有权、geometry 通路属于“恢复已有计划”；
- 新 UB 布局、有效跨度和八平面消费安排是本次真实计划变化；
- C3 对当前实际 key/entry 的接线须补齐，不能从旧 Scalar 入口猜测。

---

## 七、C3 准确实施步骤

以下交接步骤尚未执行。

1. **冻结父本与身份。** 补齐当前 tiling 定义、Weighted 启动点、geometry 分配/完成链；记录实际源码及模板身份。若与摘录不同，先回 C2 更新。
2. **增加互斥元数据域。** 在当前 Weighted 选择路径内接入本计划，保持其余元数据走原实现；无需仅为本方案创造新 key。
3. **初始化新分配。** `T=256`，value 区分配八平面；cache 和软件检测函数保持原逻辑。
4. **形成有效片。** 原 `begin/end/nc/sp/gp/count` 不变；计算 `R=AlignUp(count,8)`。
5. **搬入紧凑 geometry。** 八块 copy：
   - `blockLen=count*4`，有效字节；
   - GM `srcStride=(geometryLength-count)*4`，字节间隔；
   - UB `dstStride=0`，每行自动对齐到 `R*4`；
   - index 显式右补 `R-count` 个 sentinel，最多 7 个元素。
   
   因 Gather 恰读八行各 R 项，删除原 `Duplicate(idx,...,8*1920)`。
6. **权重只消费有效域。** coeff 使用相同 R 跨度；其 dummy 不参与加权，不能假定 `isPad=false` 补零，也不为合批额外对 dummy 做乘法。
7. **一次八平面 Gather。** 执行 `8R` 元素并等待就绪。
8. **调用原两组加权。**
   - 第一组 values 起点 0；
   - 第二组 values 起点 `4R`；
   - coeff group 分别为 0、4；
   - stride 均为 R，count 为原有效量；
   - `software` 原值不变。
9. **原有效输出写回与复用。** 只写 `count*4` 字节，完成后再复用 acc/values。
10. **实施后检查。** 核对最大地址、scratch 租约、实际静态分配、SDK API 和源到 binary 接线。源码改变后，不能沿用旧正确性记录。

本轮不包含权重重算、geometry 融合、输入转置、缓存 hint、整数 FMA 改写或累加重结合。

---

## 八、后继可复用摘要与待验证事项

### 当前状态

- 授权范围：一轮纸面优化与 C2/C3 交接，无工具、无修改、无编译、无硬件。
- 保留父本：题给 Weighted 实现；候选尚未实现。
- a：实际为整通道检测 false 后的 Vector Mul→Add。
- b：整通道末元素触发软件 fused 路径，采样不命中不能取消该路径。
- 选定路线：`A_Gather8Compact`，两个子例共用；性能、完整正确性均 `not_measured`。

### 已分析路线

| 路线 | 静态预测 | 代价与限制 |
|---|---|---|
| 八平面紧凑合批，主选 | Gather `15360F → 8ΣR`；调用 `2F → F`；删除大范围 index 初始化 | 显式 UB 42240B；保留全部有效算术和 GM 请求 |
| 四平面紧凑 Gather，最强直接替代 | 同样降低 Gather lane 和初始化量 | 显式 UB 38144B；仍有两次 Gather/片 |
| 批量整数软件 FMA，暂缓 | 可能减少 b 的逐输出 Scalar 工作 | 缺整数实现及目标等价路径，不能证明完整数值语义 |

### 实施前必须补齐

1. 目标实际可用 UB、隐含预留及 Gather 重载支持；
2. 新版实际 `blockLength`、启动 entry/key、geometry 生命周期与 workspace ABI；
3. 输入输出别名和外部可见性合同；
4. 当前源码、模板和后续候选的精确身份，不能伪造 hash。

### 后续验证预测，而非安全前提

- 是否确实生成一次八平面 Gather，实际局部访存和指令是否减少；
- a/b 分别比较完整阶段链时长，不能只计 Weighted 而遗漏 geometry；
- b 的软件 FMA 是否压倒外围节省，主方案与四平面替代谁更合算；
- 覆盖阈值 `±2^124` 邻近、采样命中/不命中大值、±0、次正规数及原合同特殊值；核对软件分支、权重位模式与逐 k 中间 acc；
- 覆盖片长 1、7、8、9、255、256 的局部边界、空核、通道切换和多次重复，并验证通用 fallback 未受影响。

**可确认的是方案改变了哪些静态工作；不能确认正确性已通过、目标瓶颈已成立或存在确定加速。**