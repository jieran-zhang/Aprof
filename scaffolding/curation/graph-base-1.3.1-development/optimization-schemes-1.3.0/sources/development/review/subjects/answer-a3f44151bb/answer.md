# 结论与本轮状态

**本轮选择保留当前“单 AIV block、三行全载、一次 `Sum`、一次整块写回”的实现，不新增优化候选。** 这不是认定它已最优，也不是因为“没有 profile 就不能优化”：当前源码已把全部输入、输出分别合成一次搬运，没有分段、重复读取、跨核归并或逐元素 Scalar 热循环。最有竞争力的改变是降低高阶 `Sum` 的执行开销，但给定材料尚不足以证明某个基础归约替换既能保持输出布局，又能减少联合工作；直接按行增核则明确会增加短搬运及独立初始化。

以下完成源码理解、机会比较和 C2/C3 **纸面交接**。未调用工具，未修改或编译工程，未验证正确性，未测量性能。baseline 保持 **assumed / not_measured**；没有生成实际 hash、路由回执或机器校验结果。

---

## 1. 当前实际执行过程及改变选择的关键事实

### 1.1 数学和物理输出契约

实际计算是行求和，不是类名 `KernelMeanSum` 所暗示的 mean：

\[
y_r=\sum_{j=0}^{31}x_{r,j},\quad r=0,1,2
\]

- 输入：连续 ND、FP32、物理形状 `[3,32]`，共 **96 元素、384B**。
- 输出：物理 **8 个 FP32、32B**；前 3 个是行和，后 5 个由 golden 定义为零。
- golden 使用相邻元素递归二分求和，计算中间值仍是 FP32。  
  来源：`scripts/gen_data.py:18–39,46–63`。
- 原比较器检查全部 8 个元素，不只是有效的 3 个。判错条件是绝对误差和相对误差均超过 `1e-4`。  
  来源：`sum.asc:175–187`。

生成器输入是 `[-100,99]` 内的整数转 FP32。对这一**生成值域**，任一局部和的绝对值不超过 3200，整数求和在 FP32 中可精确表示；因此不同纯加法树有较强的等价依据。但这不能外推到任意 FP32、NaN/Inf 或大动态范围输入，也不能据 `fixed_sample=true` 硬编码输出：源码没有固定随机种子，当前输入文件内容也未提供。

### 1.2 Host、tiling 和实际启动

`GenerateTilingData(3,32)` 得到：

| 字段 | 当前值或表达式 | 用途 |
|---|---:|---|
| `outter` | 3 | 行数 |
| `inner` | 32 元素 | 输入物理行跨度 |
| `n` | 32 元素 | 每行有效归约长度 |
| `outInner` | 8 元素 | 输出物理长度 |
| `tmpBufSize` | `GetSumMaxMinTmpSize(32,4,false, …)` 返回的 `minValue`，单位 B | `Sum` 临时区 |

来源：`sum.asc:21–60`。这里 `sizeof(uint32_t)` 恰好与当前 FP32 字节宽度相同，**不是把数据转换为整数**；实际 kernel 实例是 `KernelMeanSum<float>`（151 行）。

Host 分配输入 384B、输出 32B，拷入输入，随后：

```cpp
sum_custom<<<1, 0, stream>>>(xDevice, yDevice, tilingValue);
```

tiling 是**按值参数**，不是 GM 中的 tiling 指针。当前没有 TilingKey、多实现选择器或动态 shape 分派。来源：`sum.asc:147–160,200–234`。

### 1.3 核内数据路径、资源与依赖

当前一次 `Process()`：

1. `DataCopy` 把全部 96 个 FP32 从 GM 搬到输入 UB；
2. 输入队列 `EnQue/DeQue` 建立搬入到计算的依赖；
3. 分配输出 UB，用一次 `Duplicate` 清零全部 8 个元素；
4. 调用一次高阶 `AscendC::Sum(dst,src,tmp,params)`；
5. 输出队列发布结果；
6. 一次 `DataCopy` 将全部 8 个 FP32 写回 GM。

来源：`sum.asc:87–126`。

根据 `910c-hardware.md` 的 A3/2201 说明，这条路径是：

```text
GM ──MTE2──> 输入 UB ──Vector / Sum──> 输出 UB ──MTE3──> GM
                         ↑
                     UB 临时区
```

`VECIN/VECOUT/VECCALC` 都是 UB 的逻辑位置，不是三个独立存储层级。输入和输出各只有一个物理槽；没有 tile 循环，也没有下一 tile 可供预取。队列说明依赖受到管理，不证明已经存在流水重叠。

设 `Smin` 为查询返回值，显式用户 UB 分配账为：

\[
U_{\rm explicit}
=\operatorname{AlignUp}(384,32)
+\operatorname{AlignUp}(32,32)
+\operatorname{AlignUp}(Smin,32)
=416+\operatorname{AlignUp}(Smin,32)\ {\rm B}
\]

三个独立分配不能因生命周期不同就自动取最大值。SDK/编译器预留另计；当前没有可用 UB 实值，不能宣布完整容量已验证。

### 1.4 会直接改变优化选择的事实

- **增大 `USED_CORE_NUM` 本身不合法。** kernel 不使用 `GetBlockIdx()` 分区；每个 block 都会读全部输入、写全部输出，形成重复工作和多写者。
- 输入已经一次连续搬入，输出已经一次连续写回：源码级分别只有 **1 个搬入调用、1 个搬出调用**。
- 没有 GM 中间张量、跨核 partial 或第二个 kernel，因此没有可删除的中间 GM 往返或 launch 链。
- 只调用一次 `Sum`，不能根据高阶 API 名称推断它内部有多少指令、循环或临时操作。
- 当前有效求和的数学加法工作为 `3×31=93` 次；这不是对 `Sum` 实际指令数的测量。
- 输出 padding 是被比较的内容，不能把写回从 32B 缩成 12B而不定义后 20B。
- 清零前 3 个输出随后被行和覆盖，存在**逻辑上可讨论的初始化冗余**；但当前是一次对齐的 8 元素清零，改成只初始化尾 5 元素不能仅凭“少写 3 个元素”认定更便宜，也需要核对切片地址与具体重载。

此外，现有测试程序不能直接作为已验证 baseline 的证据：`ReadFile` 不要求文件恰好填满缓冲区，调用端没有检查输入读取结果，多数 ACL 返回值也未检查，且 `main` 在比较失败后仍返回 0。来源：`data_utils.h:46–60`、`sum.asc:226,250–255`。这些是后续验收适配问题，不在本轮夹带修复。

---

## 2. 所选方案、最有竞争力的替代及联合代价

### 2.1 所选：保留当前单核三行全载

保留全部当前工作：

- 读输入 384B；
- 初始化输出 32B；
- 三个独立行归约；
- 写物理输出 32B；
- 使用原 `Sum` 查询和队列协议。

**优化覆盖为零，语义保留范围是当前完整固定 workload。** 不把“保留全部 case”写成优化覆盖，也不声称取得收益。

### 2.2 竞争方案比较

| 方案 | 可能减少的工作 | 新增或保留的工作、约束 | 本轮判断 |
|---|---|---|---|
| **同一核改用基础 `ReduceSum` 逐行归约** | 可能绕开高阶 `Sum` 的通用参数与内部调度 | 至少 3 次基础归约调用；需合法安放 3 个标量结果、保持尾 5 个零；FP32 scratch 大小与 alias 契约必须独立确认 | **最强改变候选，暂不实施**。可能更快，不能因未测否决；但当前没有明确的联合工作减少证据 |
| **三行分别交给三个 block** | 每核归约从 3 行降至 1 行 | 输入搬入由 1 次变 3 次；各核独立初始化和 scratch；紧凑输出需要短写及 padding 所有者 | 对总共 96 元素的任务，新增固定工作明确。暂不优先，但不声称实测更慢 |
| **沿 R=32 分核产生 partial 再归并** | 缩短每个 producer 的局部归约 | 增加 partial 写读、完成协议、merge、可能第二次 launch，改变归约树 | 不选。没有容量需求，归约已经很短 |
| **拆成多 tile、增加双缓冲** | 可能重叠不同 tile | 原来只有一轮，必须先增加搬运/计算片段，再增加槽和收尾 | 不选。不能为使用流水制造额外 tile |
| **仅局部控制/初始化微调** | 可能减少少量参数构造或被覆盖的清零 | 结构体只有 5 个字段、无用户热循环；可能已被编译器消除；尾清零有调用与对齐代价 | 不因改动容易就优先 |

对 R 分片，若每行分成 `S` 份 FP32 partial，仅状态有效写读的理论下界就增加：

\[
2\times3\times S\times4=24S\ {\rm B}
\]

实际还需槽对齐和同步。必要输入仍为 384B，完整纯加法归约的总数学工作并不因此减少。

### 2.3 Problem 正文怎样改变判断

这里采用的是正文中的判别条件，而不是按名称匹配：

- `problem.reduction_strategy_mismatch.md` 要求联合看 A/R、容量、partial 和合并。当前是 **AR：A1=3、R=32、A0=1**，全载没有重复扫描；不能把“只有一核”直接判成归约策略失配。
- `problem.underused_task_parallelism.md` 明确区分“有独立外轴”与“每任务足够长”。三行确实独立，但每行只有 128B 输入；这使增核的固定成本成为关键竞争项，而非自动选择多核。
- `problem.tiny_transfer_setup_amplification.md` 与 `problem.fragmented_writeback.md` 都强调：单次全载、归约标量输出很小，并不等于存在可合并碎片。当前搬入/搬出已经各一次，不能再登记一次“合并”收益。
- `problem.pipeline_serialization.md` 明确不支持对单轮全载强加缓冲。当前搬入→归约→搬出是同一数据的真实依赖，不是已有多 tile 被错误串行化。
- `problem.vector_api_fragmentation.md` 不允许仅凭小 shape 的一次调用判定碎片化。`Duplicate` 与 `Sum` 也不是可直接合并的同类独立调用。

### 2.4 其余材料对应的机会边界

- `insufficient_input_reuse`、输入驻留及 L2 复用顺序：当前每个输入只搬一次，没有可删除的重读。
- 缓存策略正文允许一次性大流式输入比较 NORMAL/DISABLE，但也警告重复调用的热工作集风险。这里只有 384B，当前执行序列的冷热态未知，不能据“本 kernel 读一次”登记 cache mismatch。
- 融合及片上中间驻留正文：当前已经单 kernel，显式中间值在 UB，没有对应待删除的链边。
- buffer 复用正文要求最后消费者和 API alias 证明。`Sum` 执行时输入、输出、scratch 共同参与，不能直接将三块重叠。
- arch22 bank-layout 正文要求真实 UB 地址及高阶 API 展开的 repeat 访问；当前两者都未提供。**不照搬 32B padding、固定 arena 地址或物理 UB 容量。**
- Scalar、Cast、Compare/Select、Cube 和 CV 正文没有对应的当前执行对象：无逐元素 Scalar 热循环、数值 Cast、条件选择、矩阵乘或跨 AIC/AIV 交接。不会为采用这些方法制造新阶段。
- norm、exp、sigmoid 等历史案例不迁移倍率或 tile 常量。特别是逐 tile UB accumulator 案例针对真实 `GetValue` 反馈；当前源码没有该反馈。

---

## 3. 注册 Action 实例与必要依赖

### 正式选择

**新增 Action 实例：0。**

原因是本轮选择不改变实现，没有可诚实绑定的优化干预：

- 不把已经存在的批量搬运重新注册为 `coalesce_contiguous_transfers`；
- 不把单核启动直接注册为“需要动态分核”；
- 不把基础归约 API 的可能替换硬塞成 `batch_vector_api_calls`——它反而可能将一次高阶调用展开为三次；
- 不把任意 API 特化称为 `hoist_invariant_control`。

### 尚未选中的意图缺口

“保持同一 owner、同一全载结构，仅降低高阶归约 API 开销”需要进一步确认实际变化：

- 若真正改变行分组、局部归约分解或合并方式，可重新审查 `action.restructure_reduction`；
- 若仅替换同语义 primitive、分解和合并均未变，当前目录没有明确的独立“归约 API lowering”意图，不能借旧 Action 放宽范围。

它目前是**未选机会/注册意图待澄清项**，不是已注册、可直接实施的成员。

---

## 4. C2 共同计划、边界、资源与 KEEP 判断

### 4.1 纸面计划：`R0-AR-full-load-single-owner`

这是从源码提取的当前计划，不是新增并行优化。

| 项目 | 冻结内容 |
|---|---|
| 适用域 | 任务指定 dav-2201；FP32；连续 `[3,32]`；`n=32`；输出物理 8 元素 |
| 算法 | 三个完整行求和，单核全载 |
| 任务划分 | 一个 block 拥有三行 |
| 输入范围 | FP32 元素 `[0,96)`，384B |
| 输出所有权 | 同一 block 唯一拥有 `[0,8)`，含后 5 个零 |
| 归约 | 核内调用原 `Sum`，不分 R，不生成跨核 partial |
| 同步 | 原输入、输出队列协议；无跨核协议 |
| GM workspace | 无显式用户 partial/workspace |
| UB | `416+AlignUp(Smin,32)` B，另计实际 SDK/编译预留 |
| entry | 保留直调 `sum_custom` |
| dispatch | 保留当前单一路径；不增加 TilingKey |

平台映射来自用户目标及 `910c-hardware.md` 的 A3/2201 说明，不冒充设备探测。实际 SDK、构建目标、可用 UB 尚未核验。

### 4.2 P 正文的采用

采用 reduction `templates/fullload.md` 的这些内容来解释和约束现有计划：

- AR 完整行归约，允许一个任务拥有 `h` 行；当前相当于 `h=3`。
- 全载资格须包含输入、输出、scratch 和预留，不仅是 384B 输入能否放下。
- 有效长度用于归约，物理对齐长度用于地址和分配。
- 输出组少时先比较减小 `h`，不能直接沿 R 拆分。

`templates/split.md` 则用于拒绝无必要的 R 分片：跨核 partial 不仅是多开核，还要承担状态写读、merge 和完整完成关系。通用 fallback 正文提醒：**不能把当前未经设备验证的 entry 写成“已有已验证 fallback”。**

### 4.3 KEEP 的准确表述

- 工程选择是 **保留 R0**。
- 输入没有正式、有效、带身份的既有 `parallel_plan`，因此不能声称已获得机器意义的 `P_KEEP`。
- 若后续要编码成旧契约产物，本次应记为 **`P_CHANGE：提取已有计划`**，明确“算法和并行结构无实际改变”。
- 没有 Action 成员，故无逐成员 O 路由结果；也不伪造“所有成员 O_KEEP”的回执。
- 本轮是保留决策，不冒充一个已经完成 handoff 校验的正式 NOOP episode。

超出上述 shape、dtype、行跨度，或改变 owner、归约树、scratch 所有权、核数和 dispatch 域，都需新的 C2。当前源码虽使用参数化 tiling 结构，并不构成任意 shape 的支持证明。

---

## 5. C3 具体交接、准确 API/数值约束及知识缺项

### 5.1 本轮可执行的实施结论：不产生 patch

C3 纸面交接应逐项写明：

1. 父本仍是给定 `reduction_sum/sum.asc`，无候选源码、二进制或新 hash。
2. 保留 `GenerateTilingData` 的原字段及按值传参 ABI。
3. 保留两个单槽队列和独立 `tmpBuf`，不引入手工 UB 地址或 alias。
4. 保留一次 96 元素输入搬运、一次 8 元素清零、一次 `Sum`、一次 8 元素输出搬运。
5. 保留输入 FP32、计算路径 FP32、输出 FP32和全部 8 个物理输出的验收。
6. 状态记录为 **paper handoff / retained / not_executed**，不是 C3 completed、正确性通过或 accepted。

### 5.2 必须保持的 API 与单位

当前实际 API 关系是：

```cpp
AscendC::GetSumMaxMinTmpSize(n, 4, false, maxValue, minValue);
pipe->InitBuffer(inQueue, 1, inner * outter * sizeof(float));
pipe->InitBuffer(outQueue, 1, outInner * sizeof(float));
pipe->InitBuffer(tmpBuf, minValue);

AscendC::DataCopy(srcLocal, srcGlobal, 96);  // FP32 元素
AscendC::Duplicate<float>(dstLocal, 0.0f, 8);
AscendC::Sum(dstLocal, srcLocal, sharedTmpBuffer, params);
AscendC::DataCopy(dstGlobal, dstLocal, 8);   // FP32 元素
```

- `InitBuffer` 长度为字节；`num=1` 是物理槽数。
- 两次 `DataCopy` 的连续 count 是元素数，当前分别为 384B、32B，均为 32B 倍数。
- `params.inner=32` 是物理行跨度；`params.n=32` 是有效归约长度；`params.outter=3` 是行数。
- `minValue` 必须来自对应 `Sum` 查询，不填文档样例里的 4KB 等常量。
- 不能把该查询值用于另一个基础 `ReduceSum`，也不能只换 scratch 的 tensor dtype 就推定空间合法。

数值方面，保留原 oracle 和 `1e-4` 判据；不改变为 FP16、整数归约、FMA 或另一近似。后 5 个零必须保留。原 `Sum` 是否只修改前三个输出、内部是否触及 padding，仍需其具体契约或后续完整输出验证闭合；当前源码的初始化表达了意图，不替代 API 正文。

### 5.3 最强替代的具体 API 缺口

FullLoad 正文给出的基础调用是：

```cpp
AscendC::ReduceSum<float>(
    resultLocal, xFp32[row * rAlign], tmpFloat,
    static_cast<int32_t>(rValid));
```

它是**四参数**基础接口，第四项是有效 count；不能添加来自其他接口的第五个 `false`。当前各行 `rValid=rAlign=32`，输入切片起点为 0、32、64 个 FP32，分别相距 128B。

但仍有两个会阻止直接替换的具体缺项：

1. **scratch 规则缺失。** 给定正文要求 `tmpFloat` 满足基础 API 空间和别名要求，却未给出当前调用的完整尺寸规则；不能沿用 `Sum` 的 `minValue`。
2. **紧凑标量输出安放未闭合。** 不能未经该基础 API 对目的地址的约束核验，直接假定 `dst[0]、dst[1]、dst[2]` 都能作为归约目的。若需分散到对齐槽后再打包，必须增加相应 UB、打包调用和同步账。

这是地址/API 合法性缺项，不是“缺 profile”。如果上述条件由后续材料补齐，即使仍无性能测量，也可以据高阶开销假设形成条件试验。

### 5.4 O 正文实际影响了什么

- `memory-transfer/recipes/coalesce.md`：证实当前已满足连续区间合并目标，故不再追加搬运合并。
- `pipeline-sync/recipes/pipeline.md`：单 tile 没有稳态重叠项；保留单槽，不人为分块。
- `buffer-lifetime/recipes/reuse.md`：独立 `InitBuffer` 不能自动共享；scratch 复用必须证明最后消费者和 API alias，故保留独立区。
- `scalar-control/recipes/tilingdata-access.md`：该方法针对 GM tiling 指针及重复热点字段；本工程是 20B 量级的按值 tiling、无用户热循环，不能照抄 GM 指针改写。
- `precision-boundaries/recipes/bounds.md`、`numeric.md`：要求物理输出、有效 count、归约树和数值域分别说明，因此不删除 padding 验收，不把整数生成值域的结论外推到全部 FP32。

没有运行 P/O router，也没有取得正文之外的 API 资料；以上是基于所给正文的人工适用性审阅。

---

## 6. 下一轮可复用的三部分摘要与未测限制

以下可作为后续 `optimization-history.md` 的简短正文，**本轮未实际写文件**。

### 当前状态

- 授权范围：一轮纸面分析；禁止工具、修改、编译和硬件测试。
- 保留父本：给定 R0 工程；FP32 `[3,32]`，物理输出 8 元素。
- 当前理解：单 block 全载三行；输入/输出各一次连续搬运；原 `Sum` 和独立 scratch；无跨核归并、GM 中间往返或 tile 流水。
- 正确性与性能：均未验证；baseline assumed，性能 `not_measured`；无候选、无正式晋升。

### 已尝试路线

| 路线 | 本轮实际工作 | 结果与限制 |
|---|---|---|
| 保留单核 AR FullLoad | 源码理解、字节/调用账和竞争方案比较；无 patch | 选择保留，不代表最优或已正确 |
| 基础 `ReduceSum` 降低高阶开销 | 仅纸面咨询 | scratch 规则、目的地址约束及输出打包代价未闭合；未实施 |
| 行并行、R 分片、双缓冲 | 仅成本比较 | 新增短搬运、partial 或分块明确；没有实测反证，不记为失败候选 |

### 剩余机会

| 机会 | 改变下轮选择的具体证据 |
|---|---|
| 高阶 `Sum` 开销 | 提供当前 SDK 的 `Sum`/基础 `ReduceSum` 实现契约；若能合法直写或廉价打包，且减少通用处理，可形成未测假设试验 |
| 行并行 | 必须先落实分核偏移、短写和 padding owner；不能只增加 blockDim。若工作域扩大到更多/更长行，重新比较 |
| 初始化微调 | 需证明尾区域合法初始化方案确实减少发射或执行，而非仅减少 3 个逻辑写入 |
| 验收可信度 | 后续获授权时核验文件完整长度、ACL 状态、完整 8 元素输出及原 `Sum` padding 行为；不把现有退出码当正确性证明 |

**未测限制：** 当前 SDK/编译分支、真实 UB 可用量、`Smin` 数值、`Sum` 内部指令与输出触及范围、设备正确性、缓存冷热态及 Task 时间均未验证。没有加速比、瓶颈占比或目标设备收益结论；本轮也不自动授权下一轮实施。