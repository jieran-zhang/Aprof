## 结论与状态

本轮选择一个共同方案，分别为 a、b 绑定实例：

> **在指定元数据域内，把 Weighted 的局部加权和由“两组四邻居暂存”改为“一组八邻居暂存”，将物理 tile 收到 256；保持每个输出的 `k=0…7` 累加顺序、整 plane 的 `GridNeedsFma32` 判断，以及软/硬两条数值路径。**

- **a 的试验重点**：减少无效 Gather、整 tile 索引初始化，并在完整 256 点片段上合批八次独立乘法。
- **b 的试验重点**：上述物理工作减少仍成立；此外，把两次四项软件加权调用合成一次八项调用，减少软件累加状态的 UB 标量往返，**不减少、不替换软件 FMA**。
- 最有竞争力替代是：**同样采用 256 的物理 tile，但保留四邻居暂存和两组消费**。它容量更小、改动更保守，但保留两次 Gather 和两次软件累加状态往返。
- 本文完成纸面 C1/C2/C3 交接，**未修改、未编译、未运行**。实际可用 UB、完整 Weighted host/launch/ABI 未提供，故状态是 **conditional_plan / not_measured**，不是 C3 completed 或性能接纳。

两例不能按输入分布派发；候选必须在同一元数据域内保留运行时数值判断。

---

## 一、共同的当前实际路径、数学与数据依赖

### 1. 以 Weighted 摘录为实际父实现

题目明确本次执行 `GridSampler3DWeighted<float>`，因此原始文件中的 `GridSampler3DScalar<float>` 不是本次被优化的数据路径。两份摘录也不能拼成一个已经闭合的工程：原始 tiling 结构未包含 Weighted 使用的 `geometryLength`。以下按题目给定的 Weighted 路径分析；完整 host 接线仍是交接缺项。

记：

\[
I=DHW=4096,\quad G=NS=256,\quad O=NCS=2048,\quad K=8.
\]

外部数据量：

| 对象 | 有效字节 |
|---|---:|
| X，NCDHW FP32 | \(8\times4096\times4=131072\) |
| grid，[N,S,3] FP32 | \(256\times3\times4=3072\) |
| Y，NCDHW 对应展平输出 | \(2048\times4=8192\) |
| geometry：8 个 uint32 偏移＋8 个 float 权重/点 | \(256\times64=16384\) |

### 2. 几何已经跨通道预计算，不应再次记“消除八倍几何重算”

`GridGeometryRange`（244–270）生成：

\[
D[n,p]=\{offset_k[n,p],w_k[n,p]\}_{k=0}^{7}.
\]

它依赖 grid、空间尺寸、padding、alignCorners 和插值模式，不依赖通道。权重保持：

\[
w_k=\operatorname{round}_{32}
  \big(\operatorname{round}_{32}(w_xw_y)\,w_z\big).
\]

当前已经只生成 \(NS=256\) 份几何。候选不改变该表达式、生成次数、GM 表布局或发布关系，也不申请 `reuse_derived_results` 来重复认领已有收益。

对于本题有限 grid，反归一化坐标约在 `[1.1,13.9]`，八邻居位于内部。这个事实解释本次覆盖，但**不能据此删除候选的越界哨兵机制**。

### 3. Weighted 的真实计算是两种不同的浮点序列

每次新通道 plane 搬入 UB 后，当前代码扫描完整 4096 元素：

\[
software=\operatorname{any}
  (x_i\ge2^{124}\ \lor\ x_i\le-2^{124}).
\]

随后所有属于该 plane 的本核输出片段共用此结果（464–476）。

- `software=false`：

  \[
  a_0=+0,\quad
  t_k=\operatorname{round}_{32}(v_kw_k),\quad
  a_{k+1}=\operatorname{round}_{32}(a_k+t_k).
  \]

- `software=true`：

  \[
  a_0=+0,\quad
  a_{k+1}=\mathrm{GridFma32Bits}(v_k,w_k,a_k).
  \]

第二条是正确 binary32 fused multiply-add 的整数实现，不是普通 `Mul+Add`，更不是“一条硬件 FMA”。两种序列通常不逐位相同。

### 4. 当前分核与核内生命周期

每核拥有连续区间：

\[
[b\,blockLength,\min((b+1)blockLength,O)).
\]

循环再按通道边界裁剪，所以每片 `count≤256`。同一通道跨核时，各核仍独立全载、扫描其完整输入 plane；没有跨核 UB 共享。

数据流为：

```text
grid → geometry GM 表
                    ↓ 阶段完成后只读
X GM → cache UB → Gather 四邻居 → 加权/累计 → acc UB → Y GM
                         再 Gather 后四邻居
```

`cache/index/weight/value/acc` 都属于 UB；VECIN、VECCALC、VECOUT 不是三个独立容量池。现有屏障同时保护 DMA 就绪、Scalar/Vector 访问以及 buffer 覆盖，本轮不把它们机械删除。

---

## 二、可复算的共同成本基线

令：

- \(R\)：所有有效“核 × 通道 plane”交集数；
- \(M\)：实际输出片段数。

本题当前 `tile>S`，每个上述交集至多产生一个片段，因此 **\(M=R\)**；确切值取决于未提供的实际 `blockLength/blockNum`，不能写死为物理核数。

### 当前 tile 与容量

由 Weighted 457–460：

\[
cb=\lfloor(4096+64)/64\rfloor\times64\times4=16640\text{ B},
\]

\[
T_{\rm old}=1920.
\]

显式静态 UB 分配为：

\[
U_{\rm old}=16640+(32+32+16+4)\times1920
           =177920\text{ B}.
\]

源码另减去的 8192 B 是预算保留项，不能据此证明真实可用 UB。

### 当前每片工作

即使有效 `count` 只有几十或几百：

- 两次 Gather 合计处理  
  \[
  2\times4T_{\rm old}=15360
  \]
  个物理 lane；
- 因 `count≤256≠1920`，每片初始化  
  \[
  8T_{\rm old}=15360
  \]
  个 uint32 索引为哨兵；
- 几何有效读保持 `64×count` B；
- 输出有效写保持 `4×count` B；
- 每次 plane 全载有效 X 为 16384 B，合计 `16384R` B；
- 八邻居的有效消费总量始终是  
  \[
  KO=16384
  \]
  项。

这里的 lane、API 调用数、逻辑 GM 字节分别计量，均不是 HBM 实测流量或时间。

---

## 三、子例 a：有限小值，当前走分离乘加

### 1. 关键事实与实际覆盖

所有 X 位于 `[-1,1]`，所以正、负阈值检查均为 false：

- 每次 plane 装入执行两次 `GridAnyCompare32`；
- 当前全部 2048 个输出走 Vector `Mul` 后顺序 `Add`；
- 软件 FMA 调用数为零。

因此，不能把软件整数循环当作 a 的当前热点；也不能因 a 不触发而删除该路径。

### 2. 主方案 A：八邻居一次暂存，T=256

只在本题指定元数据域使用该物理安排，其他元数据走原 fallback。

每片：

1. 保留原 plane cache、完整扫描和 `software`。
2. 八行索引、权重仍采用原 SoA 逻辑布局，UB 行跨度改为 256。
3. 一次 `Gather` 取八行，共 `8×256=2048` 个物理 lane。
4. 快路：
   - `count==256`：八行全有效，用一次连续 `Mul(values,values,coeff,2048)`，替代八次独立的 `Mul(...,count)`；
   - `count<256`：保留八次有效 `count` 乘法，不计算未定义的权重 padding。
5. 仍按 `k=0…7` 分别 Add 到同一个 acc，保持原舍入点和依赖。

八次乘法之间没有数据依赖；把它们提前合批，不改变每项乘积或八次累加顺序。不采用 FMA、不改变累加树。

### 3. 工作变化与新增代价

新显式 UB：

\[
U_A=16640+(32+32+32+4)\times256
   =42240\text{ B}.
\]

其中 value 从四行扩大为八行；但 tile 从 1920 收到 256，整体分配下降。

| 项目 | 当前 | 主方案 |
|---|---:|---:|
| Gather 调用/片 | 2 | 1 |
| Gather 物理 lane/片 | 15360 | 2048 |
| 索引初始化/短片 | 15360 uint32 | 2048 uint32 |
| 完整 256 点片索引初始化 | 15360 uint32 | 0，DMA 覆盖全部索引 |
| 快路 Mul 调用/完整片 | 8 | 1 |
| 快路 Mul 调用/短片 | 8 | 8 |
| Add 调用/片 | 8 | 8 |
| 有效几何读、X 全载、Y 写 | 保留 | 保留 |
| 整 plane 数值扫描 | 保留 | 保留 |

完整片的合批收益可能为零覆盖：如果原 owner 都只拥有短片，便没有 `count==256`。不过 Gather 和索引初始化减少仍覆盖全部有效片段。

新增代价是一次保留八邻居值、更多值同时存活，以及完整/短片局部分支。没有新增 GM 表、layout 打包、额外 launch 或跨核同步。

### 4. 最有竞争力替代 A4：T=256，保留四邻居

其显式 UB 为：

\[
U_{A4}=16640+84\times256=38144\text{ B},
\]

比主方案少 4096 B。

它同样把总 Gather lane 收到每片 2048，也同样缩小索引初始化，但：

- 仍需两次 Gather；
- 若完整片分别合批四行乘法，需两次 Mul，而主方案一次；
- 短片均保留八次有效乘法；
- Add 和全部必要字节不变。

**选择理由**：主方案用额外 4096 B 换一次 Gather 发射，并在完整片上再少一次四行乘法发射；容量需求本身有界，且不新增全局准备阶段。若实际 UB 预算不足，或八行暂存的编译/执行代价超过这部分节省，A4 是直接替代，不应硬维持八行。

---

## 四、子例 b：未采到的大值仍使整个 plane 走软件 FMA

### 1. 关键事实与实际覆盖

每通道最后一个元素是 \(2^{125}\)，满足正阈值：

- 每次 plane 装入的正向检查返回 true；
- `||` 短路，负向检查不执行；
- 即使所有八邻居均未采到最后元素，**2048 个输出仍全部走软件加权**；
- 正确计数为  
  \[
  2048\times8=16384
  \]
  次 `GridFma32Bits`，不是“8 个大值各触发若干项”。

这条触发粒度是 b 与 a 成本差异的核心。

### 2. 主方案 B：同一物理方案，软件八项一次消费

T=256、八行 Gather 与 A 相同，但软件分支直接调用现有可参数化 helper：

```text
GridSoftwareWeighted(values, coeff, acc,
                     group=0, neighbors=8, stride=256, count)
```

`GridSoftwareWeighted`（225–227）本就按 `neighbors` 遍历。每个 p 的 `sum` 从 acc 读入后连续执行 k=0…7，最后写回一次。

原实现是前四项后把 acc 写回，再由后四项读回。两组之间没有额外 Cast；uint32 位模式原样往返，因此保持 `sum` 在同一标量变量中不会删除任何浮点舍入。每一步仍调用原 `GridFma32Bits`。

### 3. 工作变化与新增代价

共同的 Gather、索引初始化和容量变化与 A 相同。b 的特有变化：

| 项目 | 当前 | 主方案 B |
|---|---:|---:|
| 软件 helper 调用/片 | 2 | 1 |
| acc `GetValue`/输出 | 2 | 1 |
| acc `SetValue`/输出 | 2 | 1 |
| `GridFma32Bits`/输出 | 8 | 8 |
| 全调用软件 FMA 次数 | 16384 | 16384 |
| value/weight 有效逐项读取 | 保留 | 保留 |

全调用少 2048 次 acc 标量读取、2048 次 acc 标量写入，以及对应组间 helper 边界；不能把它描述成消除了 16384 次软件算术。

新增代价仍是八行值同时存活。软件整数实现的寄存器、栈和取指成本未给出；本轮不改其内部，也不声称已发生 spill。

### 4. 最有竞争力替代 B4：T=256，仍分四项

B4 同样减少无效物理 lane，UB 为 38144 B，但保留：

- 两次 Gather；
- 两次 helper 调用；
- 每输出两次 acc 读写。

**选择理由**：B 的数值改动小，直接复用已有 helper 的 `neighbors` 参数；额外 4096 B 换掉确定存在的状态往返和一次 Gather 发射，值得形成试验。它的收益上限受到仍然存在的 16384 次软件 FMA 限制，故预期不能沿用 a 的“批量乘法”解释。

更激进的“只检查被采到的值”不是本轮替代：它会把 b 从 fused 序列改成分离乘加，违反外部契约。把整数 FMA 向量化理论上可讨论，但输入没有提供其完整整数实现与对应 Vector 位运算、移位、特殊值和舍入实现资格；这是另一方案的具体能力缺口，不能用普通 Mul/Add 冒充。

---

## 五、Action 实例与选择边界

采用现有注册意图 **`action.restructure_reduction`**，不新增 Action：

| 绑定项 | a 实例 | b 实例 |
|---|---|---|
| 任务内实例名 | A-eight-neighbor | B-eight-neighbor |
| target | Weighted 的 K=8 局部加权和 | 同左 |
| stage | 473–476 邻居 Gather/消费 | 同左，重点为 225–227 |
| implementation | 输入中的 Weighted<float> 摘录父本 | 同一父本 |
| workload | 指定 FP32/shape/mode/layout 元数据域 | 同一元数据域 |
| 变换 | 四项分组→八项暂存与顺序消费 | 同左 |
| 数值不变量 | 分离乘加，k 顺序不变 | 每项原软件 fused FMA，k 顺序不变 |

这是局部归约的**暂存与分组组织调整**，不是重结合。`numeric` 正文明示小 K 局部加权和也要审查累加组织；不因 K=8 就排除该 Action。

实施条件：

- `reduction_semantics`：初值、八项顺序、每步舍入、输出 dtype、plane 级软路判断保持，可由上述序列核对。
- `semantic_equivalence`：候选不得改变几何、特殊值、越界哨兵和软/硬路径。
- `capacity`：42240 B 显式 UB，加 API/框架/编译配置实际需求后须合法；**尚未闭合**。
- `reduction_strategy_mismatch` 仅绑定当前四项暂存与大物理 tile 的结构事实，不代表已测瓶颈。

本文不伪造 template/source hash、router 回执或正式注册产物。正式接入需对输入正文和实际父源码绑定身份。

---

## 六、统一 C2 计划

### 1. 所有权与布局

- **保持原输出分区、blockDim、blockLength**，不把通道重新分给核，不新增 partial 或 merge。
- 每输出唯一写者不变。
- X、grid、Y 外部布局不变。
- geometry GM 布局不变：八行 byte offset，随后八行 FP32 权重。
- UB 的 index/coeff/value 行跨度统一为 256；所有调用必须使用同一跨度。
- 非法邻居仍指向 cache 中 `input_` 位置的零哨兵，不先越界读再 mask。

这不是直接适用同形 elementwise 模板。P 主路由采用 **`planning.indexing.coordinate_neighborhood`**：把 G/B/H/F 绑定到现有几何、padding、偏移和上述顺序加权函数；输出连续分区仅引用其所有权原则。

### 2. Workspace 与阶段发布

- 算子显式 geometry workspace 仍为  
  \[
  64NS=16384\text{ B}.
  \]
- 不缩减框架系统 workspace，不假定 host 没有其他消费者。
- 保留几何生产完成→Weighted 只读消费的原合法阶段依赖。
- kernel 内 `PIPE_ALL` 不能替代该跨核/跨阶段发布；实际 launch 序列未给出，接线时必须核实。

### 3. 容量与存活

候选显式分配：

| UB 对象 | 字节 |
|---|---:|
| cache，含零哨兵及原 padding | 16640 |
| index，8×256 uint32 | 8192 |
| coeff，8×256 float | 8192 |
| values，8×256 float | 8192 |
| acc，256 float | 1024 |
| **合计** | **42240** |

扫描期间仍可使用 index 和 acc 的死区租约：

- 4096 元素比较需要 128 个实际 mask word，压齐后仍为 128；
- index 的 2048 个 uint32 足够；
- temp 会访问到第二个 64-word 区域，acc 的 256 个 uint32 足够。

扫描结束并完成同步后，才可让 DMA 覆写 index、初始化 acc。values 与 coeff 同时存活，**不能取 max 或物理别名来继续扣容量**。

必要门禁：

\[
42240+U_{\rm API}+U_{\rm other}\le U_{\rm available}.
\]

若工程仍需额外 8192 B 保留，应明确计入为至少 50432 B，而不是把它默认为免费空间。

### 4. 同步与 KEEP 判定

保留：

1. cache 初始化/搬入完成→完整 plane 比较；
2. 比较的 Scalar 返回完成→index/acc 租约交接；
3. index/coeff DMA 完成→Gather/计算；
4. Gather 完成→加权消费；
5. 八次 acc 更新之间的 V 依赖；
6. 软件 Scalar UB 访问前后原完成边；
7. acc 产生→MTE3、MTE3 最后读→下片覆盖。

本轮不加入双缓冲，不声明 overlap。

**不记 P_KEEP**：没有输入可引用的完整冻结父计划，且本轮确实改变物理邻居暂存和局部分组。C2 建立后继计划，区分“提取原 owner/阶段关系”和“实际改变局部布局”。两实例均不是 O_KEEP。

### 5. 派发范围

只允许根据真实元数据选择本题域：

`float, N=1,C=8,D=H=W=16,S=256,bilinear,zeros,alignCorners=false,NCDHW`。

a/b 共用同一候选；输入值不进入 host 派发谓词。其他元数据完整保留原通用 fallback。实际工程若不需要新 Key，可在既有入口内实现该互斥元数据条件，不以增加 Key 为目标。

---

## 七、C3 准确实施步骤与正文的实际影响

以下是交给实施者的步骤，不表示已执行：

1. **绑定工程身份**  
   补齐真实 Weighted tiling 结构、入口、geometry 生产/消费 launch、workspace ABI 和父源码身份；不得拿原始 Scalar 入口作为 Weighted 接线证明。

2. **限定元数据域**  
   在 C2 冻结域内设置 `tile_=256`；域外沿用原实现。保持核数和输出区间公式。

3. **重算分配**  
   index/weight 各八行，value 八行，acc 一行；按上表核验静态分配和实际 UB 预算。

4. **保持 plane 装载与判断**  
   原 `GridNeedsFma32(cache,…,4096)` 原样保留。其 scratch 只在死租约窗口使用。

5. **修改几何搬入参数**  
   保持八个 GM block、每 block 有效 `count*4` B；GM 间隙为  
   \[
   (geometryLength-count)\times4\text{ B},
   \]
   UB 额外间隙为  
   \[
   \frac{256\times4-\operatorname{AlignUp}(count\times4,32)}{32}
   \]
   个 DataBlock。短片索引填哨兵，完整片由 DMA 全覆盖。

6. **一次 Gather 八行**  
   `Gather(values,cache,idx,0U,8*256)`，等待完成。

7. **实现两条消费路径**
   - 快路完整片：一次 2048 元素 Mul，随后八次顺序 Add。
   - 快路短片：八次有效 count Mul，随后八次顺序 Add；不读未定义权重 padding。
   - 软件路：一次 `neighbors=8` 的原 helper；不改 `GridFma32Bits`。

8. **保持有效写回与收尾**  
   只写 `count*4` B，等待最后 MTE3 读完才复用 acc。空核不发 DMA、不等未产生事件。

9. **后续授权验证顺序**  
   代码审查→目标 SDK 构建→原 oracle 完整正确性→完整 kernel 序列计时。任何数值修复若扩大软件覆盖或新增扫描，须重新比较成本。

采用正文的具体影响：

- **P `coordinate_neighborhood`**：禁止把几何复用等同于 X 值复用；因此保留每通道 cache 和扫描，不重组 owner。
- **O `vector-api.batch`**：只对完整有效的八行合批；短片不为了少调用而计算未定义 padding。
- **O `precision-boundaries.numeric`**：保留 fused/分离运算区别及 k 顺序，拒绝改成树归约或按被采样值缩小保护。
- **O `strided-pad`、`valid-length`、`bounds`**：分别使用 GM 有效字节、UB 行跨度和 32B stride 单位，不能把 tile=256 当所有片段有效长度。
- **O `buffer-lifetime.reuse`**：扫描 scratch 的租约按最后消费者交接；value/coeff 并存仍分别计容量。没有实施新的存储别名。
- **O `pipeline-sync`**：保留完成边；较少 Gather/helper 调用不等于已经流水化。

---

## 八、后继可复用摘要与待验证事项

### 当前状态

- 原 Weighted 父本保留。
- A/B 八邻居方案及四邻居替代均仅纸面分析。
- 构建、正确性、API 实际接线、时延和收益：**未测**。
- 只完成用户授权的一轮纸面优化与交接，不自动扩展轮次。

### 已分析路线

| 路线 | 静态结论 | 限制 |
|---|---|---|
| T=256、八邻居一次暂存 | 每片 Gather 物理 lane 从15360降至2048；显式 UB 为42240 B | 实际 UB/API预算待闭合 |
| a 完整片乘法合批 | 完整片8次 Mul→1次，Add顺序不变 | 完整片数量取决于真实owner划分 |
| b 软件八项一次消费 | FMA仍16384次；每输出少一次acc读和一次写 | 不能据此认定整数算术成本已解决 |
| T=256、四邻居替代 | 同样减少padding，少占4096 B | 保留2次Gather及两组软件状态往返 |

### 会改变后继选择的具体检查

1. **实际 blockLength 与片段分布**：确定 \(R\)、完整 256 点片数量；若全是短片，a 的合批乘法收益机制不覆盖，但 Gather/初始化机制仍覆盖。
2. **真实 UB 预算与编译分配**：若42240 B加全部额外需求不合法，优先回到四邻居替代，不降低数值精度。
3. **候选实际指令/API序列**：核对一次八行 Gather、完整片一次 Mul、b 一次八项 helper是否真实落地；编译器已有合并会削弱相应收益预测。
4. **严格数值检查**：除 a/b 外，同元数据下覆盖阈值两侧、负大值、NaN/Inf、±0、次正规数、抵消和越界邻居；逐项保持原路径选择与输出契约。
5. **端到端比较范围**：计入 geometry 生成和全部 launch，不能只计加权段。若 b 的软件整数算术占据主要时间，新方案可能仅有有限收益。
6. **八行与四行替代的判别**：若八行方案减少发射却总时长不优，检查额外值存活、编译资源和同步，再决定采用四行；不把单个指标改善当作整体加速。

**最终判断**：两个子例都存在无需删除数值保护的、有界且可解释的试验方向；b 的软件 FMA 覆盖已确定为全输出，必须明确保留。当前缺项阻止宣称完成实施和收益，但不否定上述静态方案的试验价值。