## 结论与交接状态

本轮选择两个**有静态依据、但尚未实施和验证的完整方案**：

- **子例 a：保留现有双份配对 packed 输入；把几何生成移入采样 owner，并直接写最终 NCS 输出。**预计删除几何表 GM 写读、输出压紧 GM 写读，以及两个 launch；不改变邻域读取布局和加权计算。
- **子例 b：取消全输入打包；按需从 NCDHW 批量跨通道读取相邻两个 x 值，在本核完成几何、采样和紧凑写回。**小输出仍然读取整个输入并生成约 16 MiB packed 副本，准备成本与消费量明显不匹配，因此这里改变输入通路。

两者均可用已提供的注册意图 **`action.reduce_memory_traffic`** 表达；不为每个配套修改增加 Action。两个实例的目标、所有权和成本不同，分别绑定下文方案。

状态为 **conditional_plan / source_reviewed / not_measured**。没有运行 router、生成 hash、编译、修改源码或验证正确性；下文是纸面 C2/C3 交接，不是 `C3 completed`。实际可用 UB、完整当前 tiling ABI、host workspace/launch 接线和目标 SDK 仍须在实施前核验。**这些是具体实施缺项，不是以缺性能数据否决试验。**

---

## 一、当前实际计算与数据路径

### 1. 数学和数值依赖

记：

\[
I=DHW=32768,\qquad cp=\lceil C/16\rceil16=64,\qquad
sa=\lceil S/16\rceil16 .
\]

输出为 `Y[n,c,p]`，最终外部地址为：

\[
((nC+c)S+p)\cdot4 .
\]

几何记录仅依赖 `grid[n,p,3]`、尺寸、padding 和 alignCorners，不依赖通道：

\[
D[n,p]=\{\mathrm{offset}_k,\mathrm{weight}_k\}_{k=0}^{7}.
\]

当前 `GridGeometryRange:243–270`：

- 按原 `GridUnnormalize`、padding、floor 顺序生成坐标；
- 每点保存 8 个 uint32 字节偏移和 8 个 FP32 权重，共 **64 B**；
- 权重按 `xy=wx*wy; weight=xy*wz` 生成。

当前实际采样不是逐输出调用原始 `GridSampler3DOne`。它消费预生成权重，通常执行分离的 `Mul`、按 **k=0…7** 顺序 `Add`；若 `GridNeedsFma32` 在整个采样 tile 的 raw 值中发现阈值命中，则**整个 tile**进入 `GridFma32Bits` 软件路径。

本 workload 中 x 有限且在 `[-1,1]`，padding 通道为零，因此 ±\(2^{124}\) 检查不会命中；检查本身仍执行。不能由此删除通用路径，也不能把一般 NaN/Inf 语义改成有限值语义。

另一个必须保留的边界是：原始逐项 `x*wx*wy*wz` 与当前“预先形成权重后再乘 x”的舍入组织并非凭实数公式就逐位等价。本轮**不继续改变当前权重和累计组织**；也不声称输入已经证明父实现通过原 oracle。

### 2. 当前四阶段

```text
grid → GridGeometryRange → GM geometry
x(NCDHW) → GridPackChannels → GM paired-packed input
geometry + paired-packed → GridSampleChannels → GM padded NCS
padded NCS → GridCompactOutput(small=false) → 最终紧凑 NCS
```

- 打包布局为 `[n,I+1,2,cp]`。槽 0 保存当前位置所有通道，槽 1 保存下一 z 平面的同位置值；最后一平面和 sentinel 按源码填零。
- 对内部点，`GridSampleChannels:1161–1163` 每点用 **一次 API、两个 descriptor block**读完 8 个邻居，读取 `8cp×4=2048 B`。
- raw 的邻居物理槽为 `slot=2*(k&3)+(k>>2)`，计算时恢复 k 顺序。
- 输出先从 `[p,c]` 用 Gather 转为 `[c,p]`，写 padded NCS；compact 再搬到最终输出。

阶段间必须有实际 launch/stream 完成依赖。核内 `PIPE_ALL` 不替代跨 kernel 发布。下面不假定存在已测重叠。

### 3. 两子例的关键静态数量

由 `Init` 公式可得：

- Pack：`p_=224`，`pitch_=928 B`，共 **147 个输入 tile**。
- Sample：`batch_=48`，`gTile_=64`。
- Pack 显式 UB：**174080 B**。
- Sample 显式 UB：**163840 B**。
- Compact 显式 UB：**65536 B**。

这些是源码显式分配量，不是目标实际可用容量证明。

| 项目 | a：S=32768 | b：S=8 |
|---|---:|---:|
| 有效输出数 CS | 2,064,384 | 504 |
| 最终输出字节 \(B_Y=4CS\) | 8,257,536 | 2,016 |
| Sample tile 数 | 683，末 tile 32 点 | 1，8 点 |
| 几何表大小 \(64S\) | 2,097,152 B | 512 B |
| paired-packed 大小 \(8(I+1)cp\) | 16,777,728 B | 相同 |
| padded 输出容量 \(4Csa\) | 8,257,536 B | 4,032 B |
| 算法 workspace 合计 | 27,132,416 B | 16,782,272 B |
| Pack 有效输入读取 | 8,257,536 B | 相同 |
| Pack 输出写入 | 16,777,728 B | 相同 |
| Sample 邻域逻辑读取 | 67,108,864 B | 16,384 B |

表中不含框架保留区、段间额外对齐或未知隐式 scratch，且均非实测 HBM 字节。

---

# 二、子例 a：保留 paired pack，融合本地几何与最终写回

## 1. 主要方案 A

**方案身份：`GS3D-A-local-geometry-direct-output`，父本为本题当前四阶段路径。**

执行序列改为：

```text
GridPackChannels<float>
→ 新采样入口：
   本 owner 生成当前空间 tile 的几何
   → 原 paired-packed 邻域读取
   → 原保护检查及有序加权
   → 转成 [c,p]
   → 直接写用户 y
```

原先全域几何在 pack 之前，现在在采样时生成。二者仅共享只读输入，没有几何→pack 的依赖，因此这次重排不需要跨核新协议。

### 全部工作变化

**删除：**

1. geometry GM 写、读各 \(64S\)：
   \[
   128S=4,194,304\ \mathrm B.
   \]
2. padded 输出的中间写入、compact 读取：
   \[
   2B_Y=16,515,072\ \mathrm B.
   \]
3. geometry、compact 两个 launch。
4. compact 的 UB→UB 搬运和相应同步、循环控制。

合计删除的上述逻辑 GM 请求：

\[
4,194,304+16,515,072=20,709,376\ \mathrm B.
\]

**保留：**

- 几何生成仍为 **S 次**，不是再节省 C 倍。
- 全输入 pack 的全部读、写、Gather、填零和初始化。
- 每点一次 paired 读取：32768 次 API、65536 个 block，67,108,864 B。
- 原 sample tile 划分、权重展开、保护扫描、Mul/Add 顺序、transpose Gather。
- 最终输出仍写 \(B_Y\) 字节。

**新增/迁移成本：**

- 在每个 sample owner 内用 Scalar 向 UB 写当前 16 路几何记录，并建立 Scalar→Vector/搬运消费者的完成边。
- 原有几何 GM 载入由本地生成取代；没有增加几何次数，但寄存器活跃范围和编译结果可能变化。
- host/kernel 接口必须增加或显式绑定最终 `y`，不能继续把输出基址藏在 pack workspace 后。

### 为什么这里可以直接输出

a 中 `sa=S=32768`。因此原 sample 输出偏移：

\[
nCsa+point
\]

与最终输出偏移相同。当前 tile 起点为 48 的倍数，每通道起点和 tile 分界均为 64 B 对齐；末 tile 32 点也是整齐区间。直接重定向目的地址不需要新压紧算法或输出汇总区。

## 2. 最有竞争力替代 A′：单份 packed 布局，再做同样融合

不能忽略现有 paired pack 为“一次 API 读八邻居”付出的复制成本。

A′ 采用 `[n,I+1,cp]` 单份 packed，其余同 A：

- packed 容量及写入从 16,777,728 降至 **8,388,864 B**；
- 每次调用少写 **8,388,864 B**，输入读取仍为 8,257,536 B；
- 不再写 z 配对副本及其顶层零平面，打包局部转换仍需要。

消费者在单份布局中：

- 每个 z 平面可用一次多块 copy 读取两条 y 行，每行包含相邻两个 x 位置；
- 两个 z 平面需要 **两次 API、四个 block**；
- 每点仍读取 2048 B，不减少必要邻域 payload。

相对 A，a 中增加 **32768 次采样 API 和65536个 block**，换取上述约 8 MiB 准备写入及对应 workspace 的减少。这里没有时间权重可把二者折算。

**本轮选 A 的理由：**先删除无需改变取数几何的约 20.7 MB 中间请求；同时保留已存在、一次处理 cp 通道的 paired 读取。S 大时，配对副本被大量邻域消费，保留它仍有明确的发射摊销机制。A′不是被排除：若 pack 时间/写流量显著，或新增采样发射成本较低，它可能更优。不能称 A 已被证明最快。

直接 NCDHW 按需读取也值得保留，但在 a 中每点需四次跨通道行组读取，共131072次 API、约825万 descriptor block，且局部 padding/Gather 增多；不作为本轮优先通路。

## 3. Action 实例 A

采用输入中的 **D v0007 `action.reduce_memory_traffic`**，任务内实例 `A-traffic`：

- **target**：geometry 和 padded NCS 两类内部物化；
- **stage**：Geometry→Sample，以及 Sample→Compact；
- **workload**：FP32、N=1/C=63/32³、bilinear/zeros/alignCorners=false、S=32768；
- **implementation**：本题当前实现，不绑定原始 scalar 入口；
- **traffic_reducible**：几何仅供该输出 tile 消费；padded 输出仅由 compact 消费，且 `sa=S`；
- **semantic_equivalence**：保持当前几何表达式、权重 FP32 边界、保护与累计序列；
- **capacity**：以下 C2 公式待实际预算确认，不伪填 true。

单个 Action 已覆盖目标。几何本来只生成一次，因此不登记“新增派生复用”；删除跨 kernel 物化也不冒充“已有单 kernel 内片上驻留”。

---

# 三、子例 b：取消全输入打包，按需跨通道读取

## 1. 主要方案 B

**方案身份：`GS3D-B-demand-NCDHW-local-chain`。**

一个 AIV owner 负责全部 `[C=63,S=8]` 输出；一次入口完成：

```text
局部几何生成
→ 按点从原 NCDHW 读取四组 yz 行，每组读相邻 x0/x1
→ Gather 成现有邻居顺序的 raw
→ 对整个8点 raw运行原保护与加权
→ 转成紧凑 [c,8]
→ 一次写2016 B最终输出
```

这里选择单 owner，是为了避免把仅 504 个输出切成很多短任务并引入输出边界协议；不是声称910C只有一个可用核，也不是证明单核最快。

### 按需输入搬运的准确映射

对一个内部点和固定 `(z,y)`，63 个通道中的源段是：

\[
x[cI+i_{zyx0}:cI+i_{zyx0}+2].
\]

一条 GM→UB 多块 DataCopyPad：

- `blockCount=63`；
- `blockLen=8 B`；
- `srcStride=(I-2)×4=131064 B`；
- `dstStride=0`，UB 每通道行占32 B。

四种 `(z0,y0)、(z0,y1)、(z1,y0)、(z1,y1)` 分别调用。不同空间点任意离散，**不把它们伪装为同一个规则 stride**。

每点四次 API、252 个 block，读取：

\[
4\times63\times2\times4=2016\ \mathrm B.
\]

8 点共 **32 次 API、2016 个 block、16128 B 有效源 payload**。raw 仍保留 cp=64，第64通道显式为零。

### 全部工作变化

**删除：**

- 全输入 pack 的147个 tile及全部工作，包括：
  - 8,257,536 B 原输入读；
  - 16,777,728 B packed 写；
  - 转置 Gather、索引准备和填零。
- geometry GM 写读，共1024 B。
- padded 输出中间写读，共4032 B。
- 四阶段改成一次入口，删除三个 launch。
- compact 的63个通道短段搬入/本地复制/搬出。

注意：原 sample 的16,384 B packed 读取被16,128 B原输入读取替换，**不是额外再节省完整输入量**。按这些对象合计，逻辑 GM 请求减少：

\[
25,035,264+1024+4032+(16384-16128)
=25,040,576\ \mathrm B.
\]

**新增/保留：**

- 输入读取从原 sample 的8次 API、16个 block，变成32次 API、2016个 block。
- 每点四组32 B对齐通道行暂存，再 Gather 为8邻居×64通道。
- staging 分配8192 B，一次初始化；有效源值覆盖后，只有两个有效 lane 被 Gather，不要求反复清零无用 lane。
- 几何仍为8次；当前第64通道的 dummy 算术仍保留。
- **整个8点 raw仍统一检查后再决定软件路径**，不按点独立切换。否则一般大值输入下会改变原来“任一点触发、全 tile软件累计”的覆盖。
- 保持8邻居 k 顺序、权重组织及最终 FP32 输出。

## 2. 最有竞争力替代 B′：保留 packed 输入，只融合短链

B′采用与 A 相同的 geometry/sample/output融合，S=8时由一个owner把 `[63,8]` 紧凑写出：

- 同样可省 geometry、compact 的中间请求和相关 launch；
- 邻域采样仍仅8次 API、16个 block，raw payload16,384 B；
- 仍必须在本调用从源输入生成完整 paired pack，承担 **25,035,264 B** 的 pack 读写和147个pack tile；
- 无跨调用复用，也没有预先 packed 副本可以摊销。

**选择 B 的理由：**为了少24次采样 API，B′仍准备整个32³输入及双份通道布局，而实际只消费8点。B新增的2016个短 descriptor block和本地Gather确实可能昂贵，但不再与a一样被32768点消费摊销；取消全域准备的静态理由更强。因此本轮优先 B，而不是仅缩小 sample batch。

另一个低容量替代是直接Scalar读取4032个有效邻居值并累计；它省去padding/Gather，但保留逐值GM访问和Scalar算术。可以后续比较，不能直接改用原始 `GridSampler3DOne`——其权重乘法组织与当前路径不同。

## 3. Action 实例 B

采用同一注册 Action，任务内实例 `B-traffic`：

- **target**：paired-packed输入、geometry、padded NCS内部物化；
- **stage**：Pack→Sample及Geometry→Sample→Compact；
- **workload**：同固定元数据，S=8；
- **implementation**：本题四阶段父本；
- **traffic_reducible**：packed没有外部消费者，原输入直接地址可以生成相同有效邻居值；其他内部物化由本owner接管；
- **semantic_equivalence**：同值位模式搬运、同8点保护粒度、同权重与k顺序；
- **capacity/API**：按下面预算和所选无mode DataCopyPad范围核验。

此实例允许的配套修改包含输入通路、任务owner和融合边界，但它们**必须由新的共同C2计划明确批准**；不能只凭Action名称越过旧计划。

---

## 四、共同 C2：所有权、布局、容量与同步

### 1. 两个新计划，不声明 P_KEEP

输入未提供覆盖这些变换的完整父计划身份。先提取当前计划，然后建立以下新计划；按材料要求编码为 **P_CHANGE**：

| 项目 | A | B |
|---|---|---|
| 输出owner | 沿用每个48点空间tile，拥有全部63通道 | 单owner拥有全部63×8 |
| 原输入 | NCDHW，只读 | NCDHW，只读 |
| 内部输入布局 | 原paired `[I+1,2,64]` | staging `[4,64,8]` float槽；每行32 B |
| raw | 沿用现有槽映射 | Gather形成相同槽映射 |
| 输出 | 直接NCS，S=32768 | UB压紧为`[63,8]`后写NCS |
| 跨核归约 | 无 | 无 |
| 算法GM workspace | 16,777,728 B packed | 0 B |
| 阶段依赖 | pack完成→采样读取 | 全部本核完成边 |

B若输入/输出可能别名，必须先证明不会覆盖后续读取；本计划不能无证据接受任意别名。A也必须确认用户y不与仍使用的packed/input区冲突。

### 2. UB容量

A：

- pack保持174080 B显式分配；
- 新sample保持163840 B，将原几何读入区改为本地几何区，不另外增加一份。
- 两个kernel不同时拥有同一个UB实例，因此不是把两者相加：
  \[
  U_A=\max(174080+T_{\rm pack},163840+T_{\rm sample})\le U_{\rm available}.
  \]

B取 `batch=8, cp=64, gTile=64`，单槽独立TBuf：

| buffer | 字节 |
|---|---:|
| raw：8邻居×8点×64通道 | 16384 |
| values：2×8×64 FP32 | 4096 |
| weights：8×(8×8) FP32 | 2048 |
| acc：8×64 FP32 | 2048 |
| geometry：16×64×4 | 4096 |
| 输出transpose索引 | 2048 |
| 四组跨通道staging | 8192 |
| staging→raw Gather索引 | 2048 |
| **显式合计** | **40960** |

必要条件：

\[
40960+T_{\rm API}+B_{\rm reserved}\le U_{\rm available}.
\]

这里不使用Select，因此不能机械加上Compare/Select配方的8KB Select scratch；实际其他API隐式资源仍须核验。也不把Scalar局部变量当成免费资源：编译后寄存器/栈未知。

### 3. 生命周期与同步

两者都先采用保守单槽完成关系，不夹带新的双缓冲：

1. 几何UB写完，才读取索引/展开权重。
2. 邻域MTE2完成，才进行保护检查和计算。
3. 权重展开结束且邻域搬运不再读取geoIndex后，原geometry区才能被保护检查用作mask scratch。
4. 每次有序Add完成后才能执行下一项；不重结合。
5. 最后Add完成，才把已死的value槽0用于输出Gather。
6. MTE3读完输出UB后，才复用该区或退出。
7. B的staging→raw Gather完成后，下一点才能覆盖staging。

保留原 `GridNeedsFma32` 所需mask清零、尾位屏蔽和int32 EQ压缩，不换成不合法的int32大小比较。A的末32点和B的8点均保持有效count，不能把gTile=64当有效点数。

### 4. 分派域

只允许真实元数据分派：

- 固定N/C/D/H/W、FP32、bilinear、zeros、alignCorners=false，S=32768对应A，S=8对应B；
- 其他未列元数据保留当前通用fallback；
- 不依据case名、x范围或“grid内部”选择host分支。候选仍保留逐邻居合法判界/零贡献路径，当前内部输入只决定本次成本。

可在新dispatch计划中使用独立uint64 key，例如A=`1`、B=`2`、fallback=`0`，但须先核对当前工程无冲突并绑定真实entry。这里是拟议编号，不声称已有接线。输入缺少当前完整host和扩展tiling结构，不能拿只含原始字段的旧header直接序列化新entry。

---

## 五、C3准确实施顺序及正文的实际影响

### A的实施步骤

1. 保持 `GridPackChannels<float>` 不变。
2. 新采样入口显式接收grid、packed和最终y。
3. 对当前owner的`point/count`，把`GridGeometryRange`中同样的坐标、floor和权重表达式写到原geometry UB布局。
4. 删除geometry GM copy；保留权重Brcb及后继计算。
5. 保留原paired读取、全tile保护、软件路径和有序Mul/Add。
6. 保留输出transpose Gather；目标GlobalTensor直接绑定用户y。
7. host不启动全域geometry和compact，workspace删除两段。
8. 审查末tile、软件路径scratch别名、输出地址及pack完成依赖。

### B的实施步骤

1. 新entry按8点、单owner初始化上表buffer，未工作的核不发DMA、不等待不存在的事件。
2. 一次初始化staging的dummy通道和两个索引表。
3. 本地生成8点几何，保持当前表达式及FP32物化边界。
4. 每点先判邻域合法性；内部点执行四条`63×8 B`跨通道copy。
5. staging Gather索引按`k`和现有slot映射生成：
   - yz组为`k>>1`；
   - 每通道行跨度32 B；
   - x lane偏移为`4*(k&1)`。
6. Gather位模式到raw，cp第64通道为零；完成后才覆盖staging。
7. 全8点邻域就绪后，执行原范围检查和同粒度软件/普通路径。
8. 从point-major acc转为`[64,8]`，只写前`63×8`个有效float，一条2016 B最终写回。
9. host跳过全部准备/compact入口，不申请这些算法workspace。

### 哪些P/O正文真正改变了决定

- **P `planning.indexing.coordinate_neighborhood`**：明确几何不依赖c、输入值却依赖c；因此不重复申报“省去C倍几何”。它也禁止由输出连续推断源局部窗口，故本轮不尝试halo驻留。
- **P `planning.layout.transpose`**：要求比较完整转换通路。由此a保留paired与单份packed竞争，b把全输入准备读写计入，而不只比较sample API数。
- **O `memory-transfer.strided-pad`**：直接决定B的63块、8 B、131064 B间隙及32 B UB行跨度；四组yz不可合成任意索引DMA。
- **O `fusion-composition.vector_chain_residency`**：要求先统一owner与全部消费者，才删除中间物化；并明确不把融合等同于流水重叠。
- **O `precision-boundaries.numeric`**：禁止把8项改成pairwise/FMA或搬动舍入。由此保持全tile软件保护，未采用原始scalar函数作为无条件替代。
- **O `buffer-lifetime.reuse`及bounds**：geo scratch、value槽复用均以最后消费者为界；实际静态分配按独立TBuf累计，不用活跃下界冒充申请量。
- **O `tiling-tail.dispatch`**：只接C2冻结谓词，不按本次数据范围新增隐含分派。

正式P/O router、条目版本/hash及实现身份绑定尚未执行，不能声称“已命中且完成交接”。

---

## 六、其他主要机会为何本轮暂缓

- **派生结果复用**：当前全域geometry已每点生成一次，继续登记相同对象没有新增生成节省。本轮改变的是物化位置。
- **原始输入驻留**：grid严格内部不证明不同点邻域重叠，更不证明落在小窗口；不能虚构重复地址数量。
- **软件流水**：a显式buffer已较大；增加槽可能迫使缩tile，需重新计算调用/尾部成本。b只有一个短tile，无稳态跨tile窗口。
- **cache hint、bank padding**：没有对应真实地址/缓存轨迹或冲突依据；尤其不能以NORMAL保证packed命中。
- **几何向量化**：a的32768次Scalar几何仍是残余机会，但floor、异常值和舍入需独立证明；本轮不混入。
- **多核拆b**：可沿通道拆分，但会增加短写、几何/控制重复及启动活跃核成本。这里先取消全域准备，不以核利用率为目标增加任务。
- **仅缩workspace**：本轮删除的是实际执行的读写与准备，不只是减少未访问预留；不据16 MiB容量本身断言时延瓶颈。

---

## 七、后继可复用摘要与待验证事项

### 当前状态

- 原四阶段源码保持未改，所有正确性和性能状态均未验证。
- A：两kernel，保留paired输入，删除geometry/输出中间物化。
- B：单kernel，取消全域pack，按需NCDHW跨通道读取。
- 无跨调用workspace复用，无确定加速比，无正式性能晋升。

### 已完成的纸面比较

| 方案 | 静态收益预测 | 主要风险/敏感条件 |
|---|---|---|
| A | 删除20,709,376 B指定GM请求及两个launch | 本地几何写入/编译活跃状态；paired pack准备成本仍在 |
| A′ | 在A基础上再少写8,388,864 B packed数据 | 多32768次采样API、65536个block |
| B | 删除约25.04 MB指定GM请求和三个launch | 短descriptor增至2016个、本地padding/Gather、单owner时延 |
| B′ | 保留最少采样发射 | 8点仍承担全域pack，准备不可免费摊销 |

### 实施前必须补齐

1. 当前完整tiling ABI、host launch/stream依赖、workspace框架保留区、真实entry/key接线。
2. 实际可用UB及目标SDK隐式资源，满足上述完整分配公式。
3. DataCopyPad/Gather等具体重载、位置、字段范围；输入输出别名合同。
4. 保持当前浮点组织的编译约束，不能新增权重FMA融合或累计重排。
5. 为候选、Action模板、计划基础与实际实现生成真实身份/hash；不能沿用本文符号名冒充不可变产物。

### 后续正确性与性能判别

- 正确性覆盖两子例全部输出，以及fallback、边界/越界坐标、±0、次正规数、NaN/Inf、阈值附近大值和“一个元素触发整个tile软件路径”。
- 核对A末32点、B全部8点、第64 dummy通道、sentinel、最后有效写入和重复调用。
- 只有完整候选正确性与存储检查通过，才比较**完整调用序列**端到端时间。
- 若A收益有限且pack占比显著，重开A′；若B的descriptor/Gather成为主要成本，比较直接Scalar按需读取或适度通道拆分。
- 实测只能评价实际整体方案；没有消融时，不把整体收益拆分归因给geometry融合、输出直写或取消pack。