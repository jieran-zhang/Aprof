## 一、本轮决定与证据边界

**a、b 均选择同一个完整试验方案：仅将两个一次性输入 `x1_、x2_` 的 L2 hint 改为 `DISABLE`，输出 `y_` 显式保持 `NORMAL`；保留当前分核、4096 元素 tile、三个单槽队列、Max、DataCopyPad 和队列生命周期。**

这不是认定“当前缓存策略错误”，而是一个有来源依据、当前结构适用、额外资源代价小的假设试验：

- 两输入已经各读一次，没有可删除的重复输入读取。
- 普通逐元素计算已经由 Vector Max 完成，没有本 workload 上的逐元素 Scalar 数据循环。
- 输入无跨调用复用，禁用输入缓存不会丢失题设中的输入复用机会；可能减少填充/替换干扰，但净收益未知。
- 与输入预取流水相比，本方案不增加 UB 槽、不改变依赖拓扑，也不要求缩 tile。
- **a 不同步禁用输出缓存**：输出确实没有后继设备消费者，但材料没有证明当前目标 SDK 的这条 UB→GM `DataCopyPad` 会产生怎样的写缓存行为，也没有 D2H 收益证据。输出 bypass 保留为有竞争力的条件候选，不能从输入 Add 示例直接推定。
- **b 保留输出 NORMAL 有额外理由**：后继设备 kernel 随即完整读 `y`，输出存在明确的设备端复用窗口。NORMAL 只保留利用这个窗口的可能性，不保证命中。

本轮只完成纸面决策和 C2/C3 交接。**未修改、未编译、未运行，正确性和性能均为 `not_measured`，不作 C3 completed 或工程接纳声明。**以下为依据所给正文作出的人工路由分析，不声称运行过 router、生成过 hash 或通过过契约校验。

---

## 二、共同的当前实际路径与成本底账

### 1. 数学、分派和数据依赖

当前路径为：

```text
maximum_kernel
  → dtype == MAX_FLOAT32
  → DispatchMaximum<float>
  → sameShape
  → KernelMaximumSame<float>
```

依据 `maximum_kernel.asc:154–180`。计算为：

\[
y[i]=\operatorname{Maximum}(x1[i],x2[i]),\quad 0\le i<N,\quad N=1048576。
\]

float 分支直接执行 `AscendC::Max(out,a,b,count)`，没有 Cast、归约、跨核合并或 GM 中间结果往返，见 `:44–62`。本方案保留该 API 和参数顺序，因此不引入 Max 与三元选择之间的数值替换问题；有限非 NaN 域仍包括符号零，后续完整正确性应覆盖，但不能声称本轮已经验证外部 oracle 的所有细节。

每核起点、有效长度为：

\[
B_c=c\,B,\quad
L_c=\min(B,\max(N-B_c,0)),\quad B=\text{blockLength}。
\]

核内第 \(i\) 个 tile 使用相对偏移 \(iT\)，有效量：

\[
v_{c,i}=\min(T,L_c-iT),\quad T=4096。
\]

输入和输出都是本核连续区间的视图；题设确认输出互斥、尾块完整。核内路径为：

```text
GM x1/x2
  ─MTE2、DataCopyPad→ 两个独立 VECIN/UB 槽
  ─输入队列就绪→ Vector Max
  → 独立 VECOUT/UB 槽
  ─输出队列就绪→ MTE3、DataCopyPad
  → GM y
```

队列同时承担就绪及槽复用协议。不能将 `FreeTensor` 理解为任意手工地址可以立即覆盖，也不能由存在队列推断已经获得了充分重叠。

### 2. 可复算的工作量

设启动核数为 \(C\)，有效核数为 \(C_a\)，总 tile 数：

\[
K=\sum_{c:L_c>0}\left\lceil L_c/4096\right\rceil。
\]

源码 tiling 的候选核数是 `min(cores,256)` 再至少取 1，实际 `cores` 未给。**不能直接把 \(K\) 写成 256**：总元素数虽整除 tile，核边界未必整除 tile。一般有：

\[
256\le K\le256+C_a-1。
\]

每次 Maximum 调用的源码级工作：

| 项目 | 数量 |
|---|---:|
| x1 有效读 | 4,194,304 B |
| x2 有效读 | 4,194,304 B |
| y 有效写 | 4,194,304 B |
| 总有效逻辑 GM payload | **12,582,912 B，即 12 MiB** |
| GM→UB DataCopyPad 调用 | \(2K\) |
| UB→GM DataCopyPad 调用 | \(K\) |
| Max API 调用 | \(K\)，处理 \(N\) 个有效元素 |
| 队列管理调用 | \(12K\)：每 tile 各 3 次 Alloc/EnQue/DeQue/Free |

这些是源码调用和有效 payload，不是硬件指令数、HBM 字节或时间。

令 \(A(z)=\operatorname{AlignUp}(z,32)\)。当前 float 分支的显式 UB 分配：

\[
U_0=3A(4T)=49152\text{ B}=48\text{ KiB}。
\]

三个 `tmp` 转换区不在 float 分支分配。上述数值不含编译器/框架预留；当前可用 UB、SDK 版本、实际编译资源报告未提供。

### 3. 正文对机会判断的实际影响

- `problem.insufficient_input_reuse` 和 `input-tile-residency` 要求重复消费同一原值。这里每个输入元素只消费一次，**可删重读量为 0**，不采用输入驻留。
- `problem.scalar_control_hot_loop` 不适用于当前数据计算路径；`MaximumScalar` 是其他分派域，不能拿它给当前 float sameShape 分支绑定事实。
- `problem.pipeline_serialization` 使我继续审查单槽依赖，而非看到 TQue 就停止；但当前真实重叠和关键路径仍未知。
- `problem.memory_bandwidth_saturation` 要求目标持续带宽证据，因此本轮不判定带宽饱和；12 MiB 必要 payload 也不证明存在可消除流量。
- `problem.cache_policy_mismatch` 与 `action.align_cache_policy` 明确允许对一次性流比较默认/禁用，不要求先证明收益；同时禁止把低首次命中率或 hint 本身写成错误策略、驻留或加速证据。

---

## 三、子例 a：输出只 D2H 一次

### 1. 实际路径、依赖及关键事实

Maximum 内部路径与上述完全相同。输出必须完整写入 GM，并在合法执行完成关系之后供 D2H 读取。不能删除最终写回，也不能把 D2H 当成 UB 消费者。

访问轨迹：

| 对象 | 本次访问 | 后继设备复用 |
|---|---|---|
| x1、x2 | 每元素读一次 | 无跨调用复用 |
| y | 每元素写一次 | 无；仅 D2H 一次 |

没有输入驻留或 L2 复用顺序重排可减少的逻辑读取；D2H 的实际缓存路径、管理周期和耗时未知。

### 2. 主方案及全部工作变化

方案标识：**`s_f32_input_stream_cache`，子例 a 实例 `A_cache_a`**。

- x1、x2：默认 NORMAL → DISABLE。
- y：显式 NORMAL。
- 每个启动 block 初始化增加 3 次 `SetL2CacheHint` 调用，新增源码调用量为 \(3C\)，不是每 tile 执行。
- 保持 \(3K\) 次搬运、\(K\) 次 Max、\(12K\) 次队列管理、12 MiB 有效逻辑 payload。
- UB 保持 \(U_0\)，workspace 保持 0。
- 不增加清零、转换、预处理表、事件或 kernel launch。
- 假设变化仅为输入访问的缓存填充/替换和实际等待；HBM 字节是否变化未知。
- y 的可能写缓存管理成本仍是残余工作，本轮没有宣称解决。

选择它而非输出 bypass，是因为输入路径有明确的一次性读取事实及对应来源方法，而输出路径还需要核验具体搬出指令的 hint 落实与 D2H 影响。这是**作用路径证据强弱的差别**，不是统一要求先测出收益。

### 3. 最有竞争力替代

**低资源替代：三个对象均 DISABLE。**

其余工作、UB、workspace、调用数与主方案相同；若主方案已显式设置 y NORMAL，替代只是更换第三个 hint 的 mode，不额外增加调用。

潜在收益对象是 y 的 4 MiB 写流相关缓存管理，而不是删除 4 MiB 输出。新增风险是写分配/实际写出行为变化及 D2H 链路影响。a 没有失去后继设备命中的风险，但这仍不证明 bypass 有益。材料要求核验目标搬出 API/编译结果，故本轮不将其标成实施条件已闭合。

**最强不同机制替代：双输入槽、单输出槽的一 tile 前瞻预取。**其完整成本见第五节。a 的端到端比较还必须包含 D2H，不能仅凭 Maximum kernel 时间缩短接纳整个输出链。

---

## 四、子例 b：输出随即被设备 kernel 顺序完整读

### 1. 实际路径、依赖及关键事实

Maximum 内部数学和队列路径不变。之后还有：

```text
Maximum 完成 GM y 写入
  → 原有 stream/事件执行依赖
  → 后继设备 kernel 完整顺序读取 y
```

题设没有给出消费者数学、核分区、其他输入或 scratch，因此不能实施融合，也不能声称将 y 留在本核 UB 就能交给另一 kernel。

后继消费增加 **4 MiB 逻辑 GM 读取**；连同 Maximum，已知部分为 16 MiB payload，不含消费者的其他读写。不能将这 4 MiB 全部记为 HBM 读取。

### 2. 主方案及成本变化

仍选择 `s_f32_input_stream_cache`，实例 **`A_cache_b`**，代码可以与 a 相同。

- 两输入 DISABLE，y NORMAL。
- Maximum 内部的新增调用、UB、workspace、payload、队列及数学工作与 a 完全相同。
- 与 a 的不同在于：**y 的 NORMAL 现在对应一个明确后继设备读窗口**。输入 bypass 可能减少与该输出/系统其他工作集的替换竞争，但没有命中数据，不能量化。
- 下游读量仍完整保留，hint 不代替跨 kernel 完成依赖。

### 3. 最有竞争力替代

**最强不同机制替代仍为双输入槽预取。**它不依赖输出缓存行为，但需要额外 UB 和生命周期证明，且只有每核多 tile 时有稳态机会。

将 y 也 DISABLE 是成本很低的策略替代，但在 b 中有明确的额外风险：失去刚生成输出的设备端缓存复用。若简化为覆盖全部 y 的一个缓存窗口模型，后继读取的 HBM 差额可能在 0 到 4 MiB 之间；实际写分配、可驻留部分、读核集合和复用距离均未知，不能将此范围当实测或保证。

融合则可能在合法情况下减少一次 launch 及最多一对 y 写读，即 8 MiB 逻辑流量；但**消费者语义、owner、布局和资源缺失是实施缺口**。不能仅凭“随即顺序读”确认融合边界，也不能用 `keep_intermediate_onchip` 越过 dispatch。

---

## 五、与主方案共同比较的流水、tile 和管理替代

### 1. 双输入槽预取：本轮最强不同机制替代

绑定已有注册意图 `action.software_pipeline_stages`，但本轮**未选为实施成员**。

保持 \(T=4096\)，两个输入各 2 个物理槽，y 仍 1 槽：

\[
U_{\mathrm{prefetch}}=5A(4T)=81920\text{ B}=80\text{ KiB}，
\]
比当前增加 **32768 B**。工作仍为 \(3K\) 次 DMA API、\(K\) 次 Max、12 MiB payload；队列管理次数仍约 \(12K\)，另加前瞻边界和序言/收尾控制。

一个可审查的队列调度是：

1. 序言搬入 tile 0 并 EnQue。
2. 每轮先 DeQue 当前 a、b。
3. 若 next tile 存在，Alloc 第二组输入槽、搬入 next、EnQue；此时每条输入队列最多一个未 DeQue 项，可保持 depth=1。
4. 当前 tile 分配 y、执行原 Max，释放当前输入租约；按原输出队列协议搬出 y。
5. 下一轮处理预取项；最后不再预取，完成 pending 输出和队列资源收尾。

这提供 MTE2(next) 与 V(current) 的独立窗口，不保证实际重叠。单输出槽仍保留 MTE3 读完旧 y 后才能覆写的约束。

**为什么本轮未优先选择：**

- Max 每元素仅一次操作，能够新增隐藏的计算窗口可能很短；原版也不等于所有流水完全串行。
- 增加 32 KiB 显式分配，却不减少必要字节和调用数。
- 实际 \(C\) 未给；若每核只有一个 tile，就没有前瞻收益。
- 当前可用 UB 未知，实施前须满足  
  \[
  81920+B_{\mathrm{其他}}+T_{\mathrm{API}}\le B_{\mathrm{available}}。
  \]
  这是容量门禁，不是缺 profile 的统一否决。

若以后显示输入等待确在关键路径、核内有足够多 tile 且容量闭合，此替代应重开，不能因本轮已选 cache 而忽略。

### 2. 单槽 tile 放大到 8192

注册意图可用 `action.coalesce_contiguous_transfers` 表达完整合并方案，不必再按输入、输出、Max 各拆一个 Action。

\[
U_{8192}=3A(4\times8192)=98304\text{ B}=96\text{ KiB}。
\]

令每核原 tile 数为 \(K_c\)，则：

\[
K_{8192}=\sum_c\left\lceil K_c/2\right\rceil。
\]

搬运、Max、队列调用分别降为 \(3K_{8192}\)、\(K_{8192}\)、\(12K_{8192}\)，必要 payload 不变。代价为增加 48 KiB 分配、更长槽生命周期，以及可能失去更合适的流水粒度。不能因原整 tile 为 16 KiB 就借用其他设备“小包阈值”认定 setup 主导；本轮不优先承担这笔容量。

### 3. 静态 buffer/event 管理简化

`action.simplify_buffer_event_management` 可以比较同样 48 KiB 数据区下减少反复队列管理的表达，但必须新增完整的 ready/free、首次状态、事件所有权和退出 drain 证明。减少 \(12K\) 个源码管理调用不代表减少相同数量的硬件工作；事件和分支也有成本。已有 `p_same` 没有授权这类生命周期改变，本轮不夹带实施。

少量 `tileElements` 字段缓存也是合法候选，但只针对每 tile 控制，编译器可能已经外提；不足以使我放弃上述主要流量、流水和管理机会比较。

---

## 六、统一 C2 交接

### 1. Action 绑定和条件状态

采用所给 **D v0007 的 `action.align_cache_policy`**，纸面登记两个 workload 绑定实例：

| 项目 | `A_cache_a` | `A_cache_b` |
|---|---|---|
| parent | 输入中的原始 `maximum_kernel.asc`、`maximum_tiling.h` | 同左 |
| target | `KernelMaximumSame<float>` 的 x1_/x2_/y_ | 同左 |
| stage | Init 中 GlobalTensor 绑定后、首次 DMA 前 | 同左 |
| workload | a 的完整执行轨迹 | b 的完整执行轨迹 |
| 参数 | 输入 DISABLE，输出 NORMAL | 同左 |
| 不变量 | 原数学、有效域、唯一写者、全部完成边 | 同左 |

条件解释：

- `symptom.source.cache_policy_mismatch`：登记的是一次性输入使用默认缓存的**可比较结构线索**，不是已证错误或瓶颈；b 还具有输入一次性、输出后继复用的区别。
- `cache_api`：所给正文支持 A2/A3 默认接口的 NORMAL/DISABLE；实际安装 SDK 和指令落实尚待 C3 构建核验。不使用预留的 READ/WRITE 模板参数或 PERSISTENT。
- `semantic_equivalence`：不改地址、值、操作和同步，静态变换依据成立；完整 oracle 尚未运行。
- `capacity`：不增加任何 UB/GM 分配；仍继承并核验原分配预算，不能将未给出的 UB 上限填为已知。

精确 template/source hash、本地任务身份未生成，故这是**待正式绑定的纸面实例记录**，不是已通过 runtime 校验的实例。

### 2. 共同计划与 KEEP 裁定

建立后继计划 **`p_same_cache_f32_v1`**，不直接宣称 `P_KEEP`：

- `p_same` 只给出原单槽资源和所有权声明，没有缓存策略许可自由度及完整后继访问合同。
- 后继计划保留算法与并行划分，补齐缓存策略、依赖和适用范围。**这主要是提取/补全已有计划，不统计为并行优化。**
- 不借此计划授权双输入槽、显式 event、广播或 int64 改写。

共同合同：

| 方面 | 冻结内容 |
|---|---|
| 所有权 | 每核原连续区间唯一写者；无重分核 |
| 布局 | 原连续 FP32 GM 和独立 VECIN/VECOUT UB 槽 |
| 数值 | 原 `Max(out,a,b,valid)`，无 Cast、近似或操作顺序变化 |
| workspace | 0，无新增段、owner 或清零 |
| 同步 | 原输入就绪、输入复用、输出就绪、输出复用全部保留 |
| 容量 | \(3A(4T)+B_{\mathrm{其他}}+T_{\mathrm{API}}\le B_{\mathrm{available}}\)，T 固定4096 |
| 外部完成 | a 保留 kernel→D2H；b 保留 kernel→消费者的原执行依赖 |
| 许可自由度 | 仅本次三个 GlobalTensor 的指定 hint 设置 |
| 禁止越界 | 不调 tile/槽数、不删队列、不改 owner/通路/融合边界 |

P 路由正文采用 `planning.elementwise.continuous`：实际影响是确认必要三路 payload、分离 tile 与 owner 粒度、按物理槽计容量，并决定本轮**不重分区**，而非机械采用模板的另一套 q/r 公式。

### 3. dispatch 与通用 fallback

- 不新增 Tiling Key，不按 a/b 名称、shape 赢家或计时结果分派。
- 只在已有 float sameShape 编译路径加入策略；其他 dtype、broadcast、int64 代码不因本轮变更而重写。
- 原始 float sameShape 实现保留为可恢复父本。
- **保留原分派不等于已证明通用 fallback 全域正确。**尤其当前 half 非 sameShape 分支直接进入 LastAxisBroadcast，其假设并非由一般广播 tiling 自动保证。这个既有覆盖缺口应单列，不能用 `p_same` 或本轮 float 验证给它背书。本轮不夹带无关 fallback 算法修复；正式宣称全算子覆盖前须补齐相应合同和验证。

---

## 七、C3 准确实施步骤及所用正文

在以后获得实施权限时，C3 按下列顺序落地；本轮未执行。

1. 冻结原父本、目标 SDK/编译目标及实际源码身份，绑定上述方案、两个实例与 C2 后继计划。
2. O 人工路由目标：
   - `implementation.memory-transfer.cache-hint`
   - 支持项 `implementation.tiling-tail.valid-length`
   - 支持项 `implementation.precision-boundaries.bounds`
3. 在 `KernelMaximumSame<T>::Init` 的三个 `SetGlobalBuffer` 后，仅对 `T=float` 增加：
   ```cpp
   if constexpr (std::is_same<T, float>::value) {
       x1_.SetL2CacheHint(AscendC::CacheMode::CACHE_MODE_DISABLE);
       x2_.SetL2CacheHint(AscendC::CacheMode::CACHE_MODE_DISABLE);
       y_.SetL2CacheHint(AscendC::CacheMode::CACHE_MODE_NORMAL);
   }
   ```
   不改变 tiling 结构、ABI、分核或 `Process()`。
4. 逐项核对实际补丁：
   - hint 在首次 DMA 前设置，不在 tile 循环重复设置；
   - 不使用显式 READ/WRITE 模板参数；
   - 两输入 GM 在 DMA 最后读取完成前仍有效；
   - 输出 NORMAL 不被误当作同步或驻留保证；
   - 没有引入其他分配、清零、barrier 或隐式候选分派。
5. 审查并构建 dav-2201 路径，核对安装 SDK 支持和生成搬运指令是否落实输入 hint。若未落实，记录“干预未实现”，不将无收益当作缓存机制反证。
6. 运行原 oracle 的完整正确性；覆盖符号零、有限极值、非整除核尾、短尾及相关 fallback 回归。源变化后不能复用旧正确性。
7. 正确性和运行条件齐备后，按同一冷/热态协议比较：
   - a：Maximum Task，并单独报告含 D2H 的完整范围；
   - b：Maximum Task及“Maximum→消费者”完整序列；
   - 可得时观察 MTE2、HBM、L2，不能用 hit 降低单独判失败，也不能用引擎指标改善替代总时长。

**正文的具体影响**：cache-hint 正文使本轮按 tensor 而非整算子设置策略、把 y 的后继消费纳入分析，并限制使用默认 RW 接口；valid-length/bounds 正文使所有有效 count、DataCopyPad 字节、原尾部及容量保持原样，不为 hint 试验增加 padding 或扩大 GM 访问。未采用 static-lease、pipeline 或 coalesce，不能把这些命中条目记成已执行优化。

---

## 八、供后继复用的摘要与待验证事项

### 当前状态

- 授权：一轮纸面优化及 C2/C3 交接，无工具、无构建、无硬件执行。
- 保留实现：输入中的原始源码；候选尚未产生。
- 选择：a/b 共用“输入 DISABLE、输出 NORMAL”，三单槽、T=4096、workspace=0。
- 状态：静态分析完成；API/编译落实、完整正确性、性能均未验证。

### 已分析路线

| 路线 | 可复用结论 | 重开条件 |
|---|---|---|
| 输入缓存策略 | 无重复输入可删；不新增 UB，新增 \(3C\) 次初始化调用 | 生成指令落实后比较完整序列 |
| a 输出 bypass | 无后继设备复用，但不能由输入示例证明写路径收益 | 搬出 hint 支持及 D2H 影响核验 |
| 双输入槽预取 | 80 KiB 数据区，新增32 KiB；调用和 payload 不减 | 多 tile、容量闭合、关键输入等待 |
| 8192 单槽 tile | 96 KiB，减少 tile/API 数，不减必要字节 | 发射成本证据及容量允许 |
| 静态租约管理 | 可比较管理表达，必须完整重建事件闭环 | 管理成本值得付出协议复杂度 |
| b 融合 | 最多可省一对 y 写读的条件性上界 | 提供消费者完整语义、owner和资源 |

### 必须分开验证的缺项

1. **实施合法性**：实际 SDK、可用 UB及预留、API/编译支持、完整 fallback 覆盖。
2. **干预是否实现**：输入 hint 是否进入真实搬运指令，实际运行是否命中修改分支。
3. **正确性**：原 oracle 全输出、边界和重复调用。
4. **性能预测**：缓存管理是否减少、其他工作集是否受损、b 的后继消费是否变化。
5. **工程裁定**：只能依据有效完整计时接纳；当前没有加速比、正确性通过或 production best。