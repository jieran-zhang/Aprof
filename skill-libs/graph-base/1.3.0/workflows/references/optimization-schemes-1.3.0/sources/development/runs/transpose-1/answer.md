## 结论与本轮状态

**建议采用一个条件化完整方案：按连续轴组织输出独占的矩形/条带任务，批量搬入、片上按位重排、按有效长度批量写回；连续子域不做片上转置。**

它优先改变当前逐元素 GM 访问和逐元素坐标解码，而不是只缓存几个 tiling 字段。用一个 `action.reorder_contiguous_access` 实例即可表达主意图，搬运、局部重排、尾块、Host/Kernel 接线属于配套实现。

本次只完成纸面分析与交接，状态为 **`conditional_plan / not_measured`**：

- 未修改、编译或运行工程，未执行 router、校验器或硬件测试。
- 已给材料足以确定映射、任务分解、DMA 参数公式和资源合法域。
- **尚不能把 C3 标成 implementation-ready**：实际 SDK 的原始整数搬运类型支持，以及 Scalar 访问 UB 后交给 DMA 的准确完成/可见性契约，仍须补齐。
- 未提供可直接采用的 Vector 转置 API 叶正文，因此不编造 `Transpose/TransDataTo5HD/Gather` 的原型、scratch 或支持范围。
- 以下方案名是本答复的纸面身份，不是已生成的文件、hash 或机器验收记录。

---

# 1. 当前实际执行过程及改变选择的源码事实

## 1.1 数学与数值契约

这是 **out-of-place、逐位保持的布局置换**：

\[
O[d]=S[P[d]],\qquad
source=\sum_d o_d\,inputStride[P[d]]
\]

输出必须复制对应输入的全部原始位，包括 NaN payload、Inf、符号零和整数高位，不能通过浮点运算实现“等价转置”。

依据：

- `transpose_definition.md:3–10` 明确位保持语义和 rank 2–5、七种 dtype。
- `verify_result.py:6,9–19` 将浮点也映射成无符号整数，比较完整输出的原始位，不是浮点容差比较。
- `cases.py` 的值域只是测试输入线索。不能利用 case16 全零、case15 NaN 等值域省略读取或生成常量输出。

## 1.2 Host 到 Kernel 的真实路径

`op_host/transpose.asc:39–59`：

1. 解析 shape、perm、dtype，dtype 只转成 `itemBytes`。
2. 查询 `ACL_DEV_ATTR_VECTOR_CORE_NUM`，交给 tiling。
3. 分配完整输入、输出和 tiling 的 Host/GM 存储。
4. H2D 输入及 tiling。
5. **只启动一次** `transpose_kernel`。
6. stream 同步后 D2H、写文件。

因此文件 I/O、分配、H2D/D2H、设备初始化是程序端到端成本，但不能直接当作 kernel 的优化收益。

`ComputeTransposeTiling` 当前计算：

\[
B=\max(1,\min(\max(1,cores),\lceil N/4096\rceil))
\]
\[
L=\lceil N/B\rceil
\]

block \(b\) 负责输出半开区间：

\[
[bL,\min((b+1)L,N))
\]

这里 `4096` 是**选核工作量目标**，不是 UB tile 长度，也不是已证明的最优粒度。

## 1.3 核内真正做了什么

`transpose_kernel.asc:7–22` 对每个输出元素：

1. 从输出线性下标开始。
2. 从最后一维到第一维执行 `% outputShape[d]`、`/ outputShape[d]`。
3. 累加该坐标对应的输入 stride。
4. 执行一次原始整数 GM 读取、一次 GM 写入。

按源码表达，每元素进行 \(r\) 次轴解码，整体约为：

- \(N r\) 次取模和 \(N r\) 次整数除法；
- \(N r\) 次 stride 项累加；
- \(N\) 次元素读取、\(N\) 次元素写入。

这些是**逻辑源码工作量**，不等于编译后独立指令数；编译器是否合并除模、缓存字段，当前未知。

入口虽然标为 `aiv`，但源码没有 Vector 计算、DataCopy、UB 分配、TQue 或核内事件。不能把它描述成“已有 MTE2→Vector→MTE3 转置流水”。实际是 AIV 上的 Scalar 地址计算和原始 GM 元素访问。

## 1.4 所有权及已有策略

- 输出按线性区间独占，区间覆盖完整且互不重叠。
- 合法 perm 下，映射是双射：每个输入元素逻辑上也只读取一次。
- 没有中间 GM tensor、归并、原子操作或核间通信。
- Host 分别分配 `devX/devY`，当前调用不存在原地别名。
- `devTiling` 在 stream 同步后才释放，读取生命周期闭合。

有效 payload 下界已经是：

\[
N s\text{ 字节读}+N s\text{ 字节写}=2Ns
\]

其中 \(s=itemBytes\)。**新的分块方案不应宣称减少这部分必要逻辑字节。** 它可能改变事务效率、访问发射和解码成本，但 HBM 字节仍需实测。

## 1.5 会改变方案选择的 workload 分域

| 实际结构 | case | 对选择的影响 |
|---|---|---|
| 输入最后连续轴仍是输出最后轴 | 1、14 | 存在长度 128、127 的连续原值片段，可以直接批量搬运，不需要元素转置 |
| 纯二维交换 | 2、3、4、5、7、8、9、11、17、18、19 | 适合规则矩形；包括 1/2/4/8B 和大量奇数边界 |
| 可合法合轴为批量矩阵交换 | 6、10、12、13 | 合轴显著减少地址描述复杂度，但仍必须保留批次和 stride |
| 多个非相邻轴移动 | 15、16、20 | 需要一般矩形映射或通用回退，不能硬套一个二维 reshape |

可直接推导的合轴例子：

- case6：`[2,9,65536] → [2,65536,9]`。
- case10：`[133221,373] → [373,133221]`。
- case12：`[3,91,4001] → [3,4001,91]`。
- case13：14 个独立 `256×256` 转置。

case1 输入为 **256 MiB**，却仍逐元素做 rank4 解码；case4、5 输入也各为256 MiB。case10 有49,691,433个元素。这使“仅缓存字段”不足以成为本轮优先方向。

接口边界也须保留：源码校验允许 rank1–8，而定义声明 rank2–5；源码未显式检查零维及形状乘积溢出。当前20 case均为正尺寸且规模可表示，但不能据此宣称更广输入域已验证。

---

# 2. 所选方案、最强替代及工作量比较

## 2.1 所选方案 S1：连续轴矩形化，片上按位重排

共同目标是：

> 将每元素“完整坐标解码＋GM小粒度读写”改为每任务/每矩形解码，以连续行 DMA 搬运；只在片上完成必要的元素置换。

不依赖 case ID，按真实 shape、perm、stride 决定路径。

### 连续子域

若输入最后轴仍位于输出最后轴，保持该连续片段边界。规则相邻行可用多块 `DataCopyPad` 表达；不得把源行间空洞当作连续数据。

例如：

- case1 的有效连续片段为128元素、256B；
- case14 为127元素、508B，UB每行需512B，GM仍只写508B。

### 一般矩形子域

不合轴时，令：

- \(a=r-1\)：输入最后连续轴；
- \(b=P[r-1]\)：输出最后连续轴；
- \(a\ne b\)。

固定其他轴坐标，取：

- 输入矩形：沿 \(b\) 有 \(v_b\) 行，每行沿 \(a\) 有 \(v_a\) 个连续元素；
- 输出矩形：沿 \(a\) 有 \(v_a\) 行，每行沿 \(b\) 有 \(v_b\) 个连续元素。

局部映射：

\[
outLocal[i,j]=inLocal[j,i]
\]

元素内部的字节或整数 lane 顺序保持原样。其他轴只影响矩形基址，不在每个元素重新解码。

优先用已证明合法的合轴简化该描述；多个移动轴的 case15/16/20 仍能用“固定其余轴”的一般矩形覆盖。

## 2.2 原工作、减少项和新增项

设矩形任务数为 \(K\)。

| 项目 | 当前实现 | S1 |
|---|---|---|
| 完整坐标解码 | 每元素，约 \(Nr\) 次轴处理 | 每任务/矩形，约 \(Kr\)；内部采用有界递增 |
| GM访问 | 每元素原始读写 | 每矩形通常一条多块搬入、一条多块搬出 |
| 必要有效GM字节 | \(2Ns\) | 仍为 \(2Ns\) |
| 片上数据工作 | 无显式UB | 搬入/搬出UB；一般矩形增加一次局部置换 |
| 同步与资源 | 无显式UB阶段 | 新增UB、完成边、尾行pitch及字段检查 |
| 代码与测试 | 单一路径 | 连续条带、一般矩形及显式通用回退 |

**首版局部置换采用原始整数 Scalar UB 重排的条件方案，而不假造 Vector 转置 API。** 它能先消除逐元素 GM 访问和完整解码，但仍保留 \(O(N)\) 次局部元素处理。对 int64 若使用两个32位 lane，局部操作数还会增加，必须计入。

预测是访问与解码粒度改善；不保证局部 Scalar 重排、DMA发射和同步的新增成本一定小于节省。

## 2.3 最有竞争力的可落地替代 S2：输出顺序计数器

保留当前核数、输出区间和逐元素 GM 原始复制：

1. 每核只对 `begin` 解码一次。
2. 用混合进位坐标更新 source。
3. 热字段按最小作用域缓存。

它覆盖全部置换、没有显式UB，也不需要新转置API。大部分元素可只执行低维增量更新，避免每元素完整除模。

**S2 的优势**：合法性缺项少、实现和验证成本低。  
**S2 的残余**：仍然逐元素 GM 读写，二维交换的源访问仍跨 stride。

选择 S1 而不是 S2，是因为当前主要工作不仅是元数据读取，还包含全域的逐元素 GM 数据处理；S1 正面处理两者。**若补证发现 UB Scalar 重排的完成协议昂贵，或主要 case 的局部处理成本抵消 DMA 收益，应返回 C1 改选 S2，而不是继续加大 tile。**

另一个潜力更高的替代是合法的 Vector 片上转置。但材料没有相应准确 API 叶正文，不能把它写成已就绪方法；它是 S1 后续可替换的局部实现，不是本轮虚构的能力。

## 2.4 其他主要机会为什么不选

- **输入驻留/减少必要流量**：置换双射，每个原输入逻辑上只消费一次。`problem.insufficient_input_reuse` 和 `input-tile-residency.md` 的同原值多消费者前提不成立。
- **缓存 bypass**：`problem.cache_policy_mismatch` 明确一次性读取、低命中本身不证明策略错误。当前还是裸 GM 指针访问，不能直接套 GlobalTensor hint 解释收益。先改访问几何，保留缓存策略。
- **独立尾优化**：当前没有“高效主体＋低效尾分支”，整个主体都是 Scalar；`problem.tail_slow_path` 不应被泛化为全域优化理由。
- **核数/尾分配**：当前已经按 N 和查询核数分配，缺少欠并行或尾集中证据。新矩形任务分配是 S1 必要配套，不另注册一个“增加并行度”目标。
- **双缓冲、缩同步、bank padding**：当前无相应UB流水。不能将尚未建立的候选路径问题当作当前事实。
- **Cast、归约、Cube、融合、workspace缩减**：当前没有对应计算链、partial或中间区。Cube/Fixpipe 的数值计算和特殊值边界也不适合承担任意位模式复制。

---

# 3. 注册 Action 实例与依赖

## A1：`action.reorder_contiguous_access`

| 绑定项 | 本轮实例 |
|---|---|
| 实例名 | `A1.transpose.contiguous_rectangles` |
| target | 输入 `x`、输出 `y` 的置换访问几何 |
| stage | `transpose_kernel` 的地址生成、搬入、局部布局转换、写回 |
| workload | 定义声明域；当前20 case用于定位结构，不作为分派条件 |
| implementation | 当前给定的三个Host/Kernel/tiling文件；hash未计算 |
| 方案 | S1 |
| 预期效果 | 连续行批量表达、按矩形摊薄解码和GM元素访问；收益未测 |

按**用户提供的注册 Action 目录**审查，而不把 Problem 正文中的旧 profile 前提重新混入：

- `symptom.source.noncontiguous_access=true`：二维及移动内轴域可由 source stride 直接证明；连续子域明确单列。
- `constraint.layout_semantics=true`：上述输出→输入映射与矩形映射等价。
- `constraint.semantic_equivalence`：按原始位搬运、无算术转换时可证明；具体API类型和局部访问方法仍须核验。
- `constraint.capacity`：**条件成立**，须满足下节字节公式和实际可用UB，不预填true。

不变量：

1. 完整语义与逐位相等不变。
2. 每个有效输出恰好一个 owner、一次写回。
3. 所有GM地址在原分配范围内。
4. UB容量、alias和完成边合法。

只登记一个实例。连续搬运、局部地址递增、尾块和同步都服务于同一访问重组目标，不重复登记并重复计算收益。

必要实施依赖是：

```text
Host建立合法矩形及有效域
    → DMA定义输入有效区
    → 输入完成后局部按位置换
    → 局部输出完成并可被DMA读取
    → 精确有效写回
    → 最后DMA读完后才复用UB
```

本轮没有注册意图缺口；存在的是**具体方法/API证据缺口**。

---

# 4. C2共同计划、边界、资源与KEEP判断

## 4.1 计划身份与路由状态

纸面计划：`PP.transpose.rect_raw.v1`，阶段为 `algorithm_parallel`。

- 已知目标：用户指定910C/dav-2201，不冒充设备探测。
- 实际核数、SDK版本、用户可用UB、事件额度：未知。
- 人工依据：`layout/templates/transpose.md` 与 `layout/fallback.md` 正文。
- 未执行P router；不能声称已有 RouteDecision、条目hash或schema校验通过。

先提取的旧计划是“输出线性区间独占＋Scalar坐标解码”；S1 则是真正改变任务及通路，故 **P_CHANGE**，不是仅补写旧计划。

## 4.2 任务与所有权

新任务以规范化后的矩形或条带编号：

- 每任务独占一个输出矩形。
- 所有任务矩形并集恰为完整输出。
- 每核领取一个连续任务ID区间，静态分配，无原子任务队列。
- 启动数不超过查询得到的AIV核数和有效任务数。
- 无归约、无核间合并、无GM数据workspace。

规则满矩形任务数由各轴分块数及固定外轴组合数计算。高rank域必须保留完整外轴映射，不能只传两个尺寸便丢失其他置换。

## 4.3 初始参数与合法域

一般矩形首个待验证参数为：

\[
T_a=T_b=64
\]

这是便于审查的初值，不是性能最优阈值。尾部：

\[
v_a=\min(T_a,A-a_0),\quad
v_b=\min(T_b,B-b_0)
\]

输入/输出UB行pitch分别固定为：

\[
L_x=AlignUp(T_a s,32),\qquad
L_y=AlignUp(T_b s,32)
\]

单物理输入区、单物理输出区的显式数据分配：

\[
U_{data}=T_bL_x+T_aL_y
\]

64×64时：

| 元素宽度 | 显式输入＋输出UB |
|---:|---:|
| 1B | 8192B |
| 2B | 16384B |
| 4B | 32768B |
| 8B | 65536B |

完整条件：

\[
U_{data}+U_{API}+U_{其他实际分配}\le U_{available}
\]

不能漏算API临时区、框架预留；也不能用材料中的物理192KiB代替实际用户可用容量。

连续条带可使用单个合法搬运区，其容量为：

\[
R_t\,AlignUp(E s,32)
\]

其中 \(E\) 是连续片段长度，\(R_t\) 是本组行数。一般置换的双区不能因“输入最终会释放”就取max：局部重排期间输入、输出同时存活。

## 4.4 分派与回退

纸面冻结三个互斥模式，均由同一直接启动入口处理：

| 稳定uint64模式标识 | 条件 | 实际入口 |
|---:|---|---|
| 0 | 未被快速路径支持的合法元数据 | `transpose_kernel` 内通用Scalar路径 |
| 1 | 规范化后存在可直接复制的连续条带，API/容量条件满足 | 同入口的连续条带实现 |
| 2 | 规则矩形映射及API/容量条件满足 | 同入口的一般矩形实现 |

这是直调工程的运行时模式，**不是擅自使用 `TILING_KEY_IS`**；`tiling-tail/recipes/dispatch.md` 明确该宏暂不用于kernel直调工程。

选择不使用case编号、文件名或值域。未知模式不能裸else静默返回。

回退保留原始Scalar按位映射。当前基线只是源码可解释，未实测验证，不能称为“已通过oracle的fallback”。

## 4.5 同步与自由度

首版只批准**单槽、逐tile完成的浅路径**，不批准预取：

- 搬入完成后才能读输入UB。
- 局部重排结束后才能搬出。
- 搬出最后读取结束后才能重写输出区。

C3可在容量和API范围内缩小矩形、拆分行组，并保持同一映射和owner。以下变化必须返回C2：

- 添加GM中转workspace；
- 改用另一核消费或改变owner；
- 引入多槽预取/新的同步拓扑；
- 改输入/输出数值表示；
- 扩展分派域。

**KEEP判断**：P_CHANGE；A1对应O_CHANGE。没有当前完整有效计划可供P_KEEP，也不因具体API缺项而记O_KEEP或NOOP。

---

# 5. C3具体实现步骤、API约束与知识正文的实际作用

## 5.1 Host与tiling

在未来获准实施时：

1. 保留当前输入/输出语义与原oracle。
2. 对总元素、字节数、stride、对齐和偏移乘加做宽整数溢出检查。
3. 仅合并两端均保持次序与连续stride的轴。
4. 生成规范化矩形尺寸、输入/输出stride、任务数、模式及容量参数。
5. Host/Kernel同时更新tiling ABI；旧Scalar所需字段仍保留。
6. 输入、输出继续分别分配，无新增GM数据workspace。
7. 分别记录分析父源码身份和实际候选源码身份；本轮不能代填hash。

## 5.2 一般矩形的准确DMA公式

设当前矩形输入、输出基址分别为 `xBase/yBase`，均以元素计。

- \(X_b\)：输入沿轴 \(b\) 的行起点跨度，元素。
- \(Y_a\)：输出沿轴 \(a\) 的行起点跨度，元素。

### GM→UB

```text
blockCount = vb
blockLen   = va * s                         // 有效字节
srcStride  = (Xb - va) * s                  // GM字节间隙
dstStride  = (Lx - AlignUp(va*s,32)) / 32    // UB额外32B块数
```

### UB→GM

```text
blockCount = va
blockLen   = vb * s                         // 有效字节
srcStride  = (Ly - AlignUp(vb*s,32)) / 32    // UB额外32B块数
dstStride  = (Ya - vb) * s                  // GM字节间隙
```

采用A2/A3 **无 `PaddingMode` 模板参数**的 `DataCopyPad`：

```cpp
AscendC::DataCopyPad(local, gm[offset], cp, pad); // GM→UB
AscendC::DataCopyPad(gm[offset], local, cp);      // UB→GM，无pad参数
```

依据 `memory-transfer/recipes/strided-pad.md`：

- `blockCount` 取正且不超过4095。
- `blockLen < 2^21`，并为所用类型大小的倍数。
- GM stride按字节，UB stride按32B块。
- GM→UB的源GM首址按该文档可1B对齐，但类型视图仍须合法。
- UB首址32B对齐。
- stride先用64位计算、检查字段范围，再窄化。
- `isPad=false` 不保证dummy为零。

本方案只重排有效元素，因此无需为“安全”清零整tile。尾部使用固定UB pitch，不把 `va/vb` 偷换成物理行跨度。

## 5.3 局部按位重排与明确缺项

局部地址关系按字节为：

\[
src=jL_x+i s+\ell
\]
\[
dst=iL_y+j s+\ell,\qquad 0\le\ell<s
\]

也可用已支持的无符号整数lane复制；int64必须保留两个32位lane或全部8字节的原顺序。**禁止使用数值Cast、乘加或浮点“转回”实现位复制。**

实施前必须补齐：

1. **实际SDK中 `DataCopyPad` 对所选原始整数类型、方向和位置的支持表。**  
   不能由正文中的float示例自动推出uint8/uint16/uint32全部组合合法。
2. **LocalTensor原始整数Scalar读写的支持及准确同步契约。**  
   尤其要确认 MTE2→Scalar读取、Scalar写UB→MTE3读取，以及区间复用的完成边。
3. **实际用户可用UB与API额外资源。**

材料证明 `PipeBarrier<PIPE_ALL>()` 能等待本核先前提交接口完成，可用于保守DMA完成点；但这**不能代替尚未给出的Scalar写UB可见性契约**。C3不得仅插一个barrier便宣布该缺项消失。

如果补到合法Vector转置叶，可在不改变映射、owner和资源额度的前提下咨询替换局部方法；若带来新scratch、布局或通路，则重新核算并按C2边界处理。

## 5.4 输出边界与生命周期

首版必须统一使用DMA写候选域，不混入Scalar GM尾写。

`strided-pad.md` 明确UB→GM会丢弃dummy，不能声称所有非32B尾写都必然覆盖邻接块；反过来也不能只凭逻辑元素不重叠便忽略实际API的并发约束。对短行、相邻任务及不同核边界，需核验目标SDK实际写入契约。若要求按共同物理块统一owner，返回C2调整，不在C3临时改变分核。

输入区与输出区保持独立，不使用原地UB转置；这样避免额外alias证明。待最后DMA读取完成后才复用输出区。

## 5.5 P/O正文怎样真正影响了选择

| 正文 | 本轮采用的判断或约束 |
|---|---|
| P：`layout/templates/transpose.md` | 采用输出唯一owner、双端stride、合法合轴和三种分解比较；拒绝将小C的`TransDataTo5HD+Gather`当通用转置 |
| P：同文“整个数据通路比较” | 固定必要流量为\(2Ns\)，不新增GM中转；同时比较输入、输出行段，不只追求输入行更长 |
| O：`memory-transfer/coalesce.md`、`strided-pad.md` | 连续区间才能直接合并；带洞行使用多块参数，形成上述双端单位及UB pitch公式 |
| O：`tiling-tail/valid-length.md`、`precision-boundaries/bounds.md` | 有效长度、物理长度、API字段分别计数；先宽整数检查，不向上扩大GM读写 |
| O：`buffer-lifetime/reuse.md`及fallback | 输入/输出同时活跃时保留独立区；不把理想live下界冒充实际分配，不先做buffer复用 |
| O：`pipeline-sync/pipeline.md`及fallback | 首版单槽浅路径；不将两槽、队列depth或历史流水收益当成当前重叠证据 |
| O：`scalar-control/hot-loop-address.md`、`tilingdata-access.md` | 构成S2的具体方法与竞争成本；当前已是GM tiling指针直读，不存在可证明的整结构栈拷贝可删 |
| O：`precision-boundaries/numeric.md`、Cast/Cube相关正文 | 原始位复制不引入Cast；拒绝以Mmad/Fixpipe数值路径替代任意位模式转置 |
| O：`vector-api/batch.md`、Compare/Select正文 | 普通Vector count、mask和类型支持不能外推为通用转置能力；当前没有条件选择语义，不采用该组合 |

历史exp tile、sigmoid流水、UB accumulator等材料只用于提醒“发射减少、配置增加不等于Task收益”，没有迁入其中的倍率、阈值或资源常量。

此外，提供的Problem正文有些保留旧硬前提；本轮Action实施条件以明确给出的注册目录为准，不把未知性能观测伪填true。

## 5.6 未来验证请求及改变选择的条件

| 检查 | 范围 | 结果怎样影响选择 |
|---|---|---|
| 原始整数DMA及UB Scalar访问契约 | 所有itemBytes，尤其int8/int64 | 不支持或需要昂贵交接时，重选局部方法或转向S2 |
| 编译后的地址解码、局部读写与spill | 满矩形、窄矩形、高rank | 若局部Scalar操作及spill取代原成本，缩参数或重选方案 |
| 完整位级oracle | 全20 case及对应边界 | 任一位错误先修复，不放宽verifier |
| 边界与owner | 1、31/32/33B附近、63/64/65元素、单/多tile、非零起点、最后核 | 检查固定pitch、字段、短写及任务覆盖 |
| 特殊位模式 | NaN不同payload、±0、Inf、次正规数、整数高位 | 排除浮点路径或lane处理破坏原始位 |
| 同源Task及必要timeline | 各结构组 | Task无收益时检查局部置换、发射与同步；不能只看MTE比例 |

这些是下一次执行授权的请求，不是本轮已经完成的验证。

---

# 6. 下一轮可复用的三部分简短摘要

## 当前状态

- 授权：仅一轮纸面分析，不修改、不编译、不调用工具、不测硬件；重试及后续执行未授权。
- 保留实现：当前输入源码；无已构建或已通过正确性的候选。
- 目标：用户指定910C/dav-2201；实际SDK、核数、可用UB未探测。
- 已理解：单次AIV kernel、输出线性独占、每元素rank次解码、原始整数GM复制，必要有效流量\(2Ns\)。
- 纸面选择：S1连续轴矩形化，`PP.transpose.rect_raw.v1`，状态`conditional_plan / not_measured`。

## 已尝试路线

- **仅分析、未实施**：S1以一个`action.reorder_contiguous_access`实例组织连续条带和一般矩形。
- 预测：每矩形摊薄解码和GM访问发射；新增UB局部按位置换、DMA和同步。
- 最强可落地替代：S2输出顺序混合进位计数器，保留逐元素GM访问，无显式UB。
- 无patch、binary、正确性结果或加速比；不能记录为accepted/rejected。

## 剩余机会

- 首要补项：原始整数DataCopyPad支持、Scalar UB访问与DMA交接契约、实际UB预算。
- 合法Vector转置API若有适用正文，可替代局部Scalar重排；目前未就绪。
- 若局部重排或同步成本不可接受，回到C1比较S2，而非默认加buffer或按case隔离。
- 流水、缓存及bank布局属于后续有针对性的机会，不是本轮强制待办，也未获得硬件收益支持。

**本轮完成的是可审查、可补证后落地的方案和C2/C3纸面交接，不是候选实施成功或性能验证。**