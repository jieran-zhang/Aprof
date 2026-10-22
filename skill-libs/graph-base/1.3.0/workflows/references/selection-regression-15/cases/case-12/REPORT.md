# case12 / Maximum：两轮静态自主选择

主 Problem 为 `problem.broadcast_strategy_mismatch`，选择保持 `action.restructure_broadcast`；最强已注册替代为 `problem.scalar_control_hot_loop` 下的 `action.vectorize_scalar_loop`。两轮均 conditional_plan；未实现、编译、运行设备或测量。目标配置910C/A3（dav-2201）未探测，实际SDK、核数、可用UB未知。

原 host/kernel/tiling、matrix20、生成器与 verifier 已读取。kernel:125-149 的广播 scalar 路径每输出做 rank 次除模与双地址累加，再执行 `av > bv ? av : bv`。拟改域仅 FP32 广播成员11/12/20、int32广播13；同形Vector、half广播18、int64成员5/19保持。按非空 owner 与行交集一次外轴解码并递增内轴地址，减少 `(N-Rowner)*rank` 轴解码；owner切行需计入Rowner，不能假定实际核数。

## R1：路线、覆盖、代价与替代

int32 使用冻结文档明确支持的A3 int32 Max(count)。整数最大值与原条件选择数值相同。A3 Compare int32仅EQ、Select仅half/float，因此禁止int32 GT+Select。

FP32优先按原GT条件构造 Compare(c)+Select模式2(n)。原式相等（含±0）取第二输入；任一NaN使GT为false，取bv。因此不能仅凭Max名称证明NaN/符号零选择等价。原verifier调用torch.maximum并检查NaN/Inf掩码；原条件与oracle的特殊值冲突仍需明确解决，不能改oracle或声称整个API已正确。现有广播有限值矩阵不能证明完整数值域。

批量路线减少N次scalar比较，新增 `Lbatch=sum_owner,row ceil(valid_owner_row/T)` 批次。FP32每批Compare、Select各一次；Compare repeats为 `sum_j c_j/64`，Select有效元素N、逻辑repeat组 `sum_j ceil(n_j/64)` 分列。int32每批1次Max。N次比较不能减去Lbatch批次；所有逻辑计量不等于编译指令或时间。若短行选择scalar参数分支，比较工作保留。

FP32段长 `c_j=64*ceil(n_j/64)`，predicate分配 `M_j=32*ceil(ceil(c_j/8)/32)`。三个独立单槽数据区的保守峰值 `max_j(12*c_j+M_j+8192)+Bresident+Bother` 字节需满足未知实际Uavailable。8192B为Select模式2 API临时区，非重叠段可复用；多槽及alias另证。int32独立预算 `3*A(4*T)+Bresident+Bother`，不套用FP32 predicate/Select费用。

只补两个输入[n,c)缺口，padding写上界 `2*sum(c_j-n_j)` 元素；DataCopyPad32B不保证Compare256B域。不可无条件Duplicate到未对齐a[n]；选合法对齐尾片、mask或scalar填充并闭合依赖。MTE2→V、Compare→Select predicate写读、V→MTE3需成立。模式2逐repeat消费不同predicate；模式0不能替代。回写仅 `4*sum(n_j)` 有效字节，padding不进GM。

最强替代泛化vectorize也需支付FP32 padding、predicate、8KB与同步，逐元素gather还保留N*rank解码并可能新增Boffset，因此仍优先广播重构。短行可在重构内采用每行scalar条件选择，保留解码收益而避免批量准备；未测前不设固定长度阈值。必要GM读写、短行scalar比较、其它dtype路径与原oracle边界均为残余。

## R2：新增静态证据与实质复评

matrix20与真实dispatch交叉后的下表假设完整行未被owner截断、T足够且独立单槽。仅为纸面构造预算，未含额外驻留/其它区，不是设备容量或成绩。

|成员|dtype/n|Compare c|predicate M|三数据区+predicate+8KB|padding写上界|Compare repeats|
|---|---|---:|---:|---:|---:|---:|
|11|FP32/513|576|96B|15200B|126元素|9|
|12|FP32/37|64|32B|8992B|54元素|1|
|20|FP32/101|128|32B|9760B|54元素|2|
|13|int32/256|不适用|不适用|三数据区3072B另加其它区|不套FP32补齐|Max另计|

R2保留广播重构，实质调整：撤回FP32无条件Max；采用GT+Select完整尾域/临时区预算；37/101短行的每行scalar方案成为明确参数比较项。原R1没有patch/correctness/timing，R2只更新范围、机制、代价，不支持任何性能预测。

反事实纸面probe，非实测：保持输出总量近似不变，将FP32完整行513改为37。单段预算15200B降至8992B，但padding写/有效元素126/513升至54/37，批次数/有效元素约增513/37倍，固定8192B不随有效数据缩小。可能调整为每行scalar，仍保留广播重构的外轴解码收益。若压紧多行合批，需重证UB pitch、predicate位偏移和owner，不能直接展平带padding行。

## 实际文档与影响

P/O内部router结果见两轮 `*-action-consult-r*.json`。读取正文path/hash/locator、before/after及适用范围见 `consultation-r*.json`；Max原始来源全文读取回执见 `compare-select-review.json`。

- P broadcast：采用zero-stride位图、行源起点和owner原则；部分适用，不能把补齐冒充真实shape对齐，int32不直接套静态Broadcast dtype表。
- P continuous：采用连续owner与有效长度/容量原则；部分适用，不能消除广播语义。
- O batch：采用A3 memory-vector路线；不能从Add count推Compare尾部合法。
- O compare-select-tail：实质改变FP32 API路线、256B执行域、predicate、模式2、8192B、同步与短行比较。部分适用：FP32合法构造骨架采用，实际SDK/数值闭合待证；int32只采用排除边界，不套GT+Select。
- 固定来源 Max.md：确认A3 int32/count支持，不证明FP32异常值等价。
- O input-tile-residency：同地址同版本且异步生命周期完整才驻留；部分适用，删copy不等于物理分配自动减少。

机读入口rounds.json绑定两轮decision-v2、C1、retrieval、expansion、P/O咨询和runtime回执。其他四例160个文件hash未变；原source未改。未有正式确认C2或P/O KEEP；结构not_implemented、正确性not_tested、性能not_measured。
