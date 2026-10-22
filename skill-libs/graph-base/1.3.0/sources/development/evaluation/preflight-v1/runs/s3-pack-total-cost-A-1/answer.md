## 结论与交接状态

本轮选择两个有不同数据通路的纸面方案，不把“小 S”和“大 S”机械地套成同一优化：

- **子例 a：保留现有成对 packed 输入；将几何生成下沉到采样 tile 内，并直接写最终 NCS 输出，取消 geometry 和 padded 输出的 GM 物化。**
- **子例 b：取消全输入 packing，按实际采样点从原 NCDHW 输入批量跨通道读取邻域；几何在本核生成，直接写最终输出。**

两者各用一个 `action.reduce_memory_traffic` 实例表达共同目标，所需布局、融合边界和 Host/Kernel 接线属于完整方案的配套步骤，不为文件数或 API 数另凑 Action。

这是 **conditional_plan 级纸面交接**：源码结构足以支持试验，收益未测并不构成否决；实际可用 UB、目标 SDK 重载及完整 Host 接线仍须在实施前闭合。本文没有执行 router、生成 hash、编译、修改源码或运行正确性测试，也不声称 C3 completed。

---

## 一、共同理解：实际执行路径、数学与依赖

### 1. 当前实际路径不是原始逐输出 Scalar 实现

按用户给定入口，实际经过：

```text
grid
  └─ GridGeometryRange → GM geometry：8 个空间字节偏移 + 8 个 FP32 权重/点

原 NCDHW x
  └─ GridPackChannels<float> → GM paired-packed 输入
                                  │
geometry ─────────────────────────┤
                                  └─ GridSampleChannels<float>
                                      → GM padded NCS
                                          └─ GridCompactOutput(small=false)
                                              → 最终紧凑 NCS
```

原始 `GridSampler3DOne` 是数学与边界定位依据，**不能将它的逐通道坐标重算量算成当前实际成本**。当前几何已经是每个 `(n,p)` 生成一次，通道消费时复用。

可见源码没有完整 Host launch 封装，因此以下确定的是四阶段及其 GM 交接；旧序列究竟对应几个独立 launch，需接线时核对，不能单由类数确认。候选则明确提出两次或一次 kernel 启动。

### 2. 数学与数值约束

本例 `alignCorners=false`，每轴保持原表达式：

\[
u=((g+1)\times32-1)\times0.5
\]

随后 `GridFloor` 得到低坐标，按源码形成八邻域。当前 `GridGeometryRange:258–268` 的权重为：

\[
w_k=\operatorname{FP32}\bigl(\operatorname{FP32}(w_xw_y)w_z\bigr)
\]

采样初始化 `+0`，严格按 `k=0…7` 消费：

- 普通路径保持当前独立 `Mul`、有序 `Add`；
- 软件路径保持 `GridFma32Bits` 的位级契约；
- 不改为树形求和、轴向分离插值或任意硬件 FMA。

原始逐输出表达式与当前“先形成权重、再乘输入”的浮点结合位置不同，不能仅凭实数公式相同，把原始 Scalar 函数当作候选的逐位等价替代。**本轮不改变当前权重生成及累加组织，最终仍须服从原 oracle。**

输入给定为有限 `[-1,1]`，本次执行不会满足 `GridNeedsFma32` 的大幅值比较条件；但这不是一般 shape 元数据。候选保留当前检测及软件路径，不把“本例有限”硬编码成所有输入的保证。

### 3. packed 布局和搬运事实

记：

- \(I=DHW=32768\)
- \(c_p=\lceil C/16\rceil16=64\)
- \(s=4\) 字节
- \(S_a=\lceil S/16\rceil16\)

成对 packed 的元素地址为：

\[
P[n,i,0,c]=X[n,c,i]
\]
\[
P[n,i,1,c]=
\begin{cases}
X[n,c,i+HW],&i+HW<I\\
0,&否则
\end{cases}
\]

物理布局为 `[N,I+1,2,cp]`；补通道及 sentinel 为零。

内部点的采样已经使用 `GridSampleChannels:1161–1163` 的快速搬运：

- **每点一次 DataCopyPad**；
- `blockCount=2`，每块 `4*cp*4=1024 B`；
- 共搬八邻域、所有 64 个通道，即 **2048 B/点**。

所以不能再提出“把每通道一次搬运合为 cp 通道”，并虚报减少 \(63\) 倍调用；源码已经完成这一层合批。

### 4. 可复算的当前参数与工作量

由实际 Init 公式：

- packing：`p_=224`，147 个输入空间 tile；
- sampling：`batch_=48`，`gTile_=64`；
- sampling 用户显式 UB：**163840 B**；
- packing 用户显式 UB：**174080 B**；
- compact：两个 8192-float buffer，共 **65536 B**。

这些是源码分配量，不是已确认的目标可用容量。

| 项目 | a：S=32768 | b：S=8 |
|---|---:|---:|
| 有效输出元素 \(CS\) | 2,064,384 | 504 |
| 有效输出字节 \(Y=4CS\) | 8,257,536 B | 2,016 B |
| sampling tile 数 | 683，末块32点 | 1，8点 |
| geometry 分配 \(64S\) | 2,097,152 B | 512 B |
| paired-packed 分配 | 16,777,728 B | 16,777,728 B |
| padded 输出分配 \(4CS_a\) | 8,257,536 B | 4,032 B |
| 上述三段 workspace 合计 | 27,132,416 B | 16,782,272 B |

packing 每次调用均读完整原输入 **8,257,536 B**，写 packed 区 **16,777,728 B**。没有跨调用摊销。

按代码有效请求计算，当前主要逻辑 GM 流量为：

\[
12S+128S+8{,}257{,}536+16{,}777{,}728+2048S+3Y
\]

其中 \(3Y\) 是采样写中间输出、compact 读和最终写；compact 并不读满 padded 空洞。

- a：**121,504,256 B**
- b：**25,058,816 B**

这是逻辑请求模型，**不是 HBM 流量或计时结果**。

---

## 二、子例 a：保留 paired packing，消除几何表和输出中转

### 1. 主方案及选择理由

候选序列：

```text
① 原 GridPackChannels<float>
② 新 GridSampleLocalGeometryDirectOutput<float>
   每48点：原式生成本地几何 → 原paired输入读取 → 原有序计算
          → 原本地转置 → 直接写最终NCS
```

在 a 中，\(S_a=S\)，中间输出本来就没有行 padding；compact 实际上是在复制整张结果。取消它不要求重新定义输出布局。

将 geometry 生成挪到采样 owner 内，也不增加几何生成次数：仍然是 **S 次**，并未从每点一次变成每通道一次。

#### 全部工作变化

| 类别 | 减少 | 新增或保留 |
|---|---|---|
| geometry | 删除 \(64S\) GM 写、\(64S\) GM 读；删除每 tile 两次 geometry DMA | 在本地 geometry 区执行16个记录写入/点；增加明确 Scalar→Vector 就绪边 |
| 输出 | 删除中间输出写与 compact 读，共 \(2Y\) | 最终 \(Y\) 写仍保留；原输出 Gather/转置仍保留 |
| 输入 | 无变化 | 完整 packing、paired 复制、每点一次2048 B采样搬运均保留 |
| 数值 | 无算法工作减少 | 原权重表达式、检测、软件分支、8次有序消费全部保留 |
| 启动 | 可删除相应独立阶段启动 | 旧 launch 数须核对；候选明确两次启动 |

净删除逻辑 GM 请求：

\[
128S+2Y=20{,}709{,}376\ \text{B}
\]

候选主要请求量约 **100,794,880 B**；workspace 用户数据仅保留 packed 区 **16,777,728 B**，另计框架保留段。

**选择依据：**不破坏当前已经形成的八邻域合批输入路径，也不缩小 sampling tile；直接针对已知完整写读的两个中间对象。缺少计时只影响净收益预测，不影响这两段 GM 物化确实可以在新所有权下消除。

### 2. 最有竞争力替代：原 NCDHW 按需读取，不做全量 packing

这就是后文 b 的数据通路，扩展到 a：

- 每点按四个 `(z,y)` 组合，各用一个跨通道描述符读取连续 `x0,x1`；
- 每次 `blockCount=63`、`blockLen=8 B`；
- 每点四次 API，代替当前一次；
- 不读取补通道，输入有效请求为 \(32CS\)。

完整候选逻辑 GM 请求约：

\[
12S+32CS+Y=74{,}711{,}040\ \text{B}
\]

比主方案再少 **26,083,840 B**。但不能只按字节判胜：

- 输入 DMA 调用：**32768 → 131072**；
- 描述符内短行数：当前 \(2S\) 个1024 B块，变为 \(4CS\) 个8 B块；
- GM→UB 每个8 B短行按32 B组织，本地行跨度累计显著增大；
- 需要新增邻域重排 Gather；
- 按后文保守 `St=8` 布局，采样批次从 **683 → 4096**，相应循环、权重准备、输出调用更多。

**本轮选主方案而不选此替代：**a 的采样消费足够多，现有全量转换能够被大量采样消费摊销；按需方案虽然少搬 GM 字节，却显著增加短行和发射工作。这里是有依据的取舍，不是已测得 packing 胜出。

另一条可行但暂缓的路线是去掉 packed 的 z 配对：可减少约8 MiB packed 存储及写入，但失去当前一次搬八邻域的表示，通常需更多输入描述符；本轮先不同时改变这条输入通路。

### 3. Action 实例

**A-a / `action.reduce_memory_traffic`，输入正文 v0006**

- parent：本题给定当前四阶段实现快照；
- target：`geometry` 与 `Ypad` 两条内部 GM 交接边；
- stage：几何生产—采样消费、采样结果—compact 消费；
- workload：FP32、N=1/C=63/D=H=W=32、S=32768、bilinear/zeros/alignCorners=false；
- effect：在新采样 owner 内生成本地几何，直接写最终输出；
- `traffic_reducible`：由上述地址与唯一消费者链支持；
- 精度、owner、生命周期要求见 C2；
- capacity：条件化，未把源码中的188160 B预算当作平台查询结果。

无需附加 `reuse_input_tiles`：这里保留的是派生几何，不是删除同一原输入的重复载入；也不套 `hoist_invariant_control` 承载几何数值计算。

正式 template/source hash 尚未生成，不伪造注册完成回执。

### 4. C2 共同计划

**P_CHANGE**，不是 P_KEEP。既包含对旧计划的提取，也确实改变了几何 owner、融合边界和 workspace。

- **任务与 owner**：保持当前每个 `(n,p0:p0+count)` sampling tile 拥有全部有效通道；tile 号仍按 block-stride 分配。
- **输出**：最终地址 `n*C*S+c*S+p`。a 的每个主 tile 为48 float=192 B，起点及长度均为64 B倍数；末块32 float=128 B。通道平面跨度也是64 B倍数，保持清晰的独占写边界。
- **本地几何布局**：保留原 `geometry_` 的两半：
  - `[0,8*gTile)`：FP32 权重；
  - `[8*gTile,16*gTile)`：uint32 空间字节偏移。
- **workspace**：仅保留 `[N,I+1,2,cp]` packed 段；旧 geometry、Ypad 段不再访问。Host 和 Kernel 偏移同时改，不能只缩分配。
- **同步**：
  1. packing 全部完成后，采样才能读 packed；以流顺序/明确阶段依赖保证；
  2. 本地 Scalar 几何写完后，才广播权重及读取偏移；
  3. 原采样 DMA→检测/计算、最终 Add→Gather、Gather→MTE3、MTE3结束→下轮覆盖关系保留；
  4. 不以核内 barrier 代替 packing 的跨核完成。
- **容量**：采样仍为163840 B，packing仍为174080 B，两个 kernel 不相加为同时 UB 峰值；额外 SDK scratch/保留另计。合法条件为各自完整需求不超过目标可用 UB。
- **自由度**：本轮不改48点批量、不新增双缓冲、不收窄原同步、不修改输入布局或累加次序。
- **回退**：不满足候选元数据或能力条件时，完整走原四阶段路径，不在部分写出后改走回退。

### 5. C3 准确实施步骤

1. 新增接受 `grid/xPacked/y` 的采样入口，冻结以上任务布局。
2. 将 `GridGeometryRange:249–268` 抽成“原式计算一个记录”的公共实现，GM 版本保持原样，本地版本写入现有 `geoWeight/geoIndex`。
3. 删除新入口的 `geometryIndex_/geometryWeight_` GM 绑定及 `1159` 的两次搬入；生成当前 `count` 的几何后建立完成边。
4. 继续使用当前 Brcb、内部/边界搬运、`GridNeedsFma32`、Apply 和软件路径。
5. `y_` 改绑最终 y，输出跨度使用 S。a 中它与旧 `sa` 数值相同，不改变转置索引。
6. Host 在候选域只启动 packing 和新采样入口，删除该路径的 geometry/compact 阶段及对应 workspace 段。
7. 静态审查完成后，未来另行执行目标 SDK 构建、完整 oracle 和全链计时；当前不执行这些步骤。

---

## 三、子例 b：取消全输入转换，按需跨通道读取

### 1. 为什么不能沿用 a 的输入选择

b 仅需8点、504个有效输出，当前却仍完整读取8.26 MB原输入、写16.78 MB packed 数据。

采样有效输入需求上界仅：

\[
8\times8\times63\times4=16{,}128\ \text{B}
\]

空间地址之间是否重复未知，不假设任何跨点输入局部性，也不据此再虚报复用收益。

本例优先消除全输入转换，价值依据比“再省512 B几何表”更强。

### 2. 主方案：单 owner、四次跨通道短行搬运/点

候选一个 AIV kernel，拥有全部8点和63通道：

1. 按原式在本地生成8点几何和权重；
2. 对内部点的四个 `(zbit,ybit)`，分别读取所有有效通道的两个相邻 x 值；
3. UB Gather 重排成 `[k,p,c]`；
4. 保持当前幅值检测、数值路径及 k 顺序；
5. 转为 `[c,p]`，直接写最终2016 B。

#### 具体输入描述符

NCDHW 中相邻通道平面相差 I 个 float。每个固定 `(p,zbit,ybit)`：

```text
blockCount = 63
blockLen   = 2*sizeof(float) = 8 B
srcStride  = (I-2)*sizeof(float) = 131064 B
dstStride  = 0
```

每个 UB 行占32 B，即8个 float；前两个有效，其余 dummy 不参与计算。

共 **4S=32 次输入 API**。不是每个通道单独调用，也不是一次描述符能表达所有不规则空间点。

### 3. 全部工作变化与代价

| 项目 | 当前 | 候选 |
|---|---:|---:|
| 原输入 packing 读 | 8,257,536 B | 删除 |
| packed 写 | 16,777,728 B | 删除 |
| 采样输入有效读 | 16,384 B，含补通道 | 16,128 B |
| geometry GM 写读 | 1,024 B | 删除 |
| 输出中间写读 | 4,032 B | 删除 |
| 最终输出写 | 2,016 B | 保留 |
| 输入 API | 8次paired快路径，另有packing | 32次跨通道描述符 |
| 新本地工作 | — | 邻域 Gather、固定布局偏移表、短行padding空间 |

候选主要逻辑 GM 请求为：

\[
96+16{,}128+2{,}016=18{,}240\ \text{B}
\]

相对当前模型删除 **25,040,576 B**。但短行每行8 B、本地按32 B排布，因此32个描述符的有效63行对应 **64512 B 的 UB 行跨度**；不能把16 KB有效读当作全部本地成本。

算术仍按补到64通道的4096个邻域值处理，最后只输出63通道。没有删除插值乘加，也不宣称一次 kernel 必然比多核更快。

### 4. 最有竞争力替代：Scalar 精确取数，保留同一 Vector 计算后半段

替代不做全量 packing，也生成本地几何，但：

- 对4032个有效邻域值直接 Scalar GM读取并 `SetValue` 到 `[k,p,c]`；
- 显式填64个补通道邻域值；
- 后续检测、权重、Vector计算、最终写出与主方案一致。

其有效 GM 请求同为 **18240 B**，也可单次启动，无大 workspace。

优势：

- 删除64 KiB短行 raw 区及16 KiB Gather索引；
- 不支付短行 padding 和新增输入 Gather；
- 代码通路相对直接。

代价：

- **4032次 Scalar GM取值及对应本地写入**，而主方案是32次规则多块 DMA；
- Scalar发射、访存延迟与DMA短行成本谁更大尚未测；
- 不应直接调用原始 `GridSampler3DOne`，否则会重新引入不同的浮点乘法结合方式。

本轮选 DMA 主方案，是基于规则跨通道地址能够合法批量表达、可避免数千次逐值 Scalar 取数；**这个选择仍需与上述替代做全链实测判别**，不是先验认定 DMA 一定胜出。

沿用 a 的“保留packing、只融合几何与输出”虽可减少约5 KB请求，但仍留下25 MB级转换，因而在 b 中竞争力较弱。

### 5. Action 实例

**A-b / `action.reduce_memory_traffic`，输入正文 v0006**

- parent：同一当前四阶段实现；
- target：全量 packed 输入、geometry、Ypad 三条内部物化边；
- stage：输入转换—采样—输出压紧；
- workload：同 a，唯 S=8；
- effect：用原布局按需读取替代全量转换，在采样 owner 内完成几何和最终写回；
- `traffic_reducible`：指出具体被删除的全域转换及中间写读，不以“带宽饱和”作为事实；
- semantic/layout：原输入地址映射和数值路径须按下面计划兑现；
- capacity/API：条件化。

这里同样没有输入驻留 Action：并没有证明不同采样点读取同一输入地址。主方案的本地 Gather 是按需通路的配套布局实现，不另拆成独立优化意图。

### 6. C2 共同计划

**P_CHANGE**。取消旧空间块—全通道 packed 消费计划，重新批准输入通路及单 owner 输出。

#### 所有权与布局

- 一个有效 owner 拥有 `[c=0:63,p=0:8]`；不沿 k 拆分，不产生 partial，无归并。
- raw 按 `[p,4个yz组合,cp,8个float的行]` 排列。
- 设 `r=p*4+2*zbit+ybit`，读取值位于：
  \[
  raw[r\cdot cp\cdot8+c\cdot8+xbit]
  \]
- Gather 目标为：
  \[
  values[k\cdot(S\,cp)+p\cdot cp+c]
  \]
  其中 `k=xbit+2*ybit+4*zbit`。
- 第63号补通道只需初始化 Gather 真正读取的两个位置，不把整块 raw 清零。
- 输出转成 `[c,p]` 后，一次63行、每行32 B的写回即可覆盖2016 B；全由同一 owner 写，末端不扩写到用户分配之外。

#### 容量快照

使用独立物理分配，不依赖未证明的别名：

| UB 区 | 字节 |
|---|---:|
| raw：\(4S\,cp\,32\) | 65536 |
| 八邻域 values | 16384 |
| Gather索引 | 16384 |
| acc | 2048 |
| 权重展开 | 2048 |
| geometry，保留gTile=64的保守布局 | 4096 |
| 输出转置索引 | 2048 |
| 检测临时区 | 512 |
| **显式合计** | **109056 B** |

另计目标 SDK 所需 scratch/预留。条件为：

\[
109056+B_{\rm SDK}\le U_{\rm available}
\]

不是因为低于源码188160 B就宣布已通过容量核验。用户数据 GM workspace 为0；系统保留区仍由真实工程契约决定。

#### 生命周期与同步

1. Scalar几何和布局索引写入完成，才能供搬运地址构造或Vector读取。
2. 所有邻域 DMA完成后，Gather才读 raw。
3. Gather完成后才运行检测和计算。
4. 检测 scratch **不能覆盖仍活跃的 values**。原代码中 `values` 在检测时是死区，本候选中已装入真实邻域，故新增独立512 B检测临时区。
5. 权重展开、偏移消费结束后，geometry 才可租给检测 mask。
6. 最后有序 Add完成后，才允许用 values 第一个槽接最终转置结果；MTE3读完前不可覆盖。
7. 无跨核事件、无全局barrier，也不引入双缓冲。

#### 非内部点及数值域

“grid严格内部”不是 Host shape 可判断的谓词，不能据此让整个 S=8入口无条件越界读取。

候选必须保留每点合法性判断：

- 完整内部点走上述四描述符路径；
- 边界点用合法逐邻域取数，先判界，再读有效源；无效贡献按原契约处理；
- 全部值仍进入与当前 batch 相同的检测和有序计算，不能擅自变更软件路径选择范围；
- 非有限值不自行 clamp、过滤或改写。

本题两子例都只执行内部快路径，但完整候选不能只对这组数据安全。

### 7. C3 准确实施步骤

1. 增加 `GridSampleNcdhwDemand<float>` 入口，参数直接接原 x/grid/y；不伪造已有 packed 副本。
2. 复用 a 的原式几何 helper，构造本地记录。
3. 初始化上述固定 Gather/转置偏移表，绑定其字节单位；按32 B对齐划分所有UB区。
4. 内部点发四个63行×8 B描述符；边界点走已声明的安全读取分支。
5. Gather成完整 `[k,p,c]` 邻域区，补通道已定义；仅检测这块完整有效执行域，不检测 raw 中未定义的dummy。
6. 用独立检测临时区保留 `GridNeedsFma32`；复用当前 Apply时按邻域组传入对应值视图，保持k顺序及独立Mul/Add。
7. 最终Gather到已退休的value槽，再按63行×32 B直接写最终y。
8. Host在候选域仅启动此入口，不分配或初始化旧 packed/geometry/Ypad；其他元数据完整走原 fallback。
9. 若要求新增并行owner、跨点输入窗口、改变批量检测域或使用别名压缩容量，返回C2，不能在C3局部夹带。

---

## 四、P/O 正文具体怎样影响了本轮方案

这里只列实际改变判断的正文，不把“读过路径”当作采用证明。

| 正文 | 对本方案的实际影响 |
|---|---|
| `planning.indexing.coordinate_neighborhood` | 绑定 G/B/H/F为当前坐标、padding、八邻域与有序累加；明确几何不依赖c、输入值仍依赖c。促成 a 的本地几何，但禁止凭几何相同宣称输入复用。 |
| `planning.layout.transpose` | 要求比较整个通路而非只比较Gather与Scalar；因此将全量packing读写、z配对复制、局部转置、输出压紧全部纳入。 |
| `planning.elementwise.continuous` | 只参考其输出唯一owner和边界原则，不把GridSampler冒充同下标逐元素算子。a保留64 B边界；b采用单owner避免短输出跨owner审计。 |
| `implementation.memory-transfer.strided-pad` | 直接决定 b 的63行×8 B描述符及`srcStride=131064 B`，并按每行32 B计算raw；禁止跨不规则点使用一个仿射stride。 |
| `implementation.buffer-lifetime.reuse` | 区分死区租约与活值：识别 b 中原检测对values的租用已不合法，增加独立scratch；最终转置只能在最后Add后覆盖value槽。 |
| `implementation.precision-boundaries.numeric/bounds` | 保留权重舍入位置、k顺序、软件FMA路径；禁止先越界读取再mask，以及为对齐扩大最终输出。 |
| `implementation.tiling-tail.dispatch` | 候选条件只能来自真实元数据；不按case名、x范围或“grid内部”作Host派发；plan父本与最终实现身份分开。 |
| `implementation.pipeline-sync.pipeline` | 本轮不因源码有PIPE_ALL就删同步，也不因增加buffer就宣称重叠。a多tile流水可留作后继机会；b单批次不强行制造流水。 |

`vector_chain_residency` 仅用于审查本地交接及数值边界原则，不将其逐元素链模板冒充完整GridSampler实现。`input-tile-residency` 明确不适用本轮派生几何，也没有足够重复地址证据用于输入驻留。

正式 P/O 条目版本/hash与真实 router 结果，需要未来有工具权限时冻结；当前没有伪造命中记录。

---

## 五、分派、KEEP与实施门禁

### 分派范围

本轮不推测 S 的通用最优阈值。可以使用一个 Host 选择表、两个候选入口：

- a候选：精确给定元数据、S=32768；
- b候选：精确给定元数据、S=8；
- 其他形状、dtype、模式：原通用路径。

这只是有明确成本差异的**有界试验域**，不是生产最优边界。`outD/outH/outW`只要乘积S相同，按原展平p映射处理，不按具体case编号分派。新 uint64 key 的实际取值须在完整工程中核对现有命名空间后冻结，本文不凭空指定会冲突的号码。

### KEEP依据

- 两子例均 **P_CHANGE**：owner/融合边界/workspace或输入通路确有变化。
- 两子例均需实际 O_CHANGE。
- 未改的 packing、权重算术或软件FMA函数属于局部保留，不等于整个方案P_KEEP/O_KEEP。
- 缺Host、hash或router结果不能转换为KEEP，更不是NOOP。

### 实施前硬门禁

1. 目标 SDK 对所用 DataCopyPad、Gather、Apply及同步重载的支持；
2. 实际可用UB与API scratch完整字节账；
3. 完整Host的workspace保留区、启动依赖与唯一分派接线；
4. 原oracle和 `GridFma32Bits` 编译/数值契约未被表达式抽取改变；
5. 候选全部边界路径的地址、有效长度与最后消费者证明。

这些是安全/结构条件。HBM命中、setup占比、端到端收益和编译后Scalar指令量属于待验证预测，不统一充当实施阻塞项。

---

## 六、后继可复用摘要与待验证事项

### 当前状态

- 授权仅一轮纸面分析及C2/C3交接；无代码改动、构建、正确性通过或性能晋升。
- 当前保留实现仍为原四阶段路径。
- a探索计划：paired输入不变，几何本地生成、最终输出直写。
- b探索计划：原NCDHW按需读取，单owner本地计算与直写。
- 两者性能均为 **not_measured**。

### 已比较路线

| 域 | 选定路线 | 静态预测 | 最强替代及重开条件 |
|---|---|---|---|
| a | 保留packing，删除geometry/Ypad物化 | 删除20,709,376 B逻辑GM请求，不增加采样DMA数、不缩tile | 按需NCDHW还可少搬约26 MB，但短行/API/批次增多；若packing实测占主链明显、短行成本可接受，应重开 |
| b | 按需strided DMA，取消全量转换 | 主要逻辑请求25,058,816→18,240 B，新增32次短行DMA及Gather | Scalar精确取数同字节、更小UB；若短行DMA和Gather准备超过约4千次Scalar取值成本，则选替代 |
| 未选 | 仅字段缓存、cache hint、盲目双缓冲 | 未解释当前主要全量转换及中间物化 | 需有新的编译或timeline证据，不能因易实现优先 |

### 后继判别清单

- **结构兑现**：实际入口是否走选定路径；旧workspace是否真正不再分配/访问；没有仅