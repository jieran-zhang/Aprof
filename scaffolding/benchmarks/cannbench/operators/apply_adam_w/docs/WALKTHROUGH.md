## 设计串讲

### 审查结论

- [ ] 设计可直接开发（无阻塞问题）
- [x] 设计需要修改后开发（有阻塞/讨论问题）
- [ ] 设计存在严重问题，无法开发

总体数学数据流与逐元素多核切分方向成立，但当前版本尚不能直接翻译成可靠的 Ascend C 实现。主要阻塞点是 FP32 主 Buffer 的逻辑位置不满足 `DataCopyPad` 搬运通路约束、伪代码缺少跨流水同步，以及对 `Sqrt(0)`/负数/除零的 IEEE 传播假设与官方 API 文档不一致。以下 API 结论均基于对 `third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/` 中同名前缀全部变体的通配符检索，而非单文件存在性猜测。

### 质疑清单

#### 问题 1：FP32 分支的主 Buffer 位置不支持 `DataCopyPad` 通路

- **类别**：API 可行性
- **严重程度**：🔴 阻塞
- **设计文档位置**：DESIGN.md 第 1.5 节、2.4.1 节
- **问题描述**：内存表把 `bufA/bufB/bufC/bufD` 全部定义为 `TPosition::VECCALC`，但 FP32 伪代码直接执行 GM→A/B/C/D 和 A→GM 的 `DataCopyPad`。官方文档仅列出 `GM->VECIN/VECOUT`、`VECIN/VECOUT->GM`（以及本地到 TSCM）通路，不包含 GM↔VECCALC。因此按当前 Buffer 表实现，FP32 路径的搬入/搬出不满足 API 支持范围。
- **审查者视角**：这是编译/运行前的结构性冲突，不是尾块参数的小修补；FP32 又覆盖 8 个强制 case，无法绕过该分支。
- **建议方案**：重新确定 A/B/C/D 的实际 `TPosition` 和生命周期。可将需要直接 GM 搬运的 Tensor 放在 VECIN/VECOUT，或引入合法的输入/输出 Queue 后再进入计算 Buffer；选择后要同步更新 §1.3、§1.5、§2.4 以及 UB 预算。不要只在代码里临时改位置而保留错误设计。
- **文档依据**：通配符检索 `ls .../context/ | grep -i '^DataCopyPad'` 仅得到 `DataCopyPad(ISASI).md`；该文件“不同产品型号对函数原型的支持度”表明确 A2/A3 支持 `GM->VECIN/VECOUT、VECIN/VECOUT->GM、VECIN/VECOUT->TSCM`，未列 VECCALC 通路。其函数原型是 `DataCopyPad(LocalTensor<T>, GlobalTensor<T>, DataCopyExtParams, DataCopyPadExtParams<T>)` 和反向重载。

#### 问题 2：伪代码缺少跨流水同步，且 `rawIn` 会被连续复用覆盖

- **类别**：伪代码可实现性
- **严重程度**：🔴 阻塞
- **设计文档位置**：DESIGN.md 第 1.3 节、1.5 节、2.4.1 节、2.4.2 节
- **问题描述**：伪代码把 `DataCopyPad -> Cast/Vector -> DataCopyPad` 当作普通 C++ 串行语句，但没有 Queue 的 `EnQue/DeQue`，也没有明确的 MTE2→V、V→MTE3 事件同步。半精度路径还在循环中对四个输入复用唯一 `rawIn`：前一次 `Cast` 尚未消费完 rawIn 时，下一次 MTE2 搬入即可覆盖它。FP32 路径同样可能在四次 MTE2 完成前启动 Vector，或在最终 Add 完成前由 MTE3 搬出 A。
- **审查者视角**：官方示例使用 `TQue<VECIN>` 搬入后 `EnQue/DeQue`，并通过 `TQue<VECOUT>` 在计算与搬出间建立依赖。当前设计只描述了存储容量，没有描述生产者/消费者同步，无法保证结果确定性，尤其是 raw buffer 复用时。
- **建议方案**：在设计层明确一种完整同步模型并写入伪代码：（1）优先采用 Queue，逐次 `AllocTensor -> DataCopyPad -> EnQue -> DeQue -> Cast -> FreeTensor`，输出同理；或（2）明确使用合法 event ID 的 `SetFlag/WaitFlag` 建立 MTE2_V、V_MTE2、V_MTE3 依赖。若依赖编译器自动同步，也必须通过最小 kernel 编译/反汇编及真实 NPU 重复压力测试证明 rawIn 复用无覆盖；不能只靠源码语句顺序假设。选定模型后重新计算 Queue depth 对 UB 的占用。
- **文档依据**：通配符检索得到 `SetFlag-WaitFlag(ISASI).md`、`SetFlag-WaitFlag.md`、`TQue.md` 等。`SetFlag-WaitFlag(ISASI).md` 明确“同一核内不同流水之间具有数据依赖时需要插入同步”，并列出 `MTE2_V`、`V_MTE2`、`V_MTE3`；`DataCopyPad(ISASI).md` 的完整示例用 VECIN/VECOUT Queue 的 `EnQue/DeQue` 串联 CopyIn、Compute、CopyOut。

#### 问题 3：零值、负值和除零行为被当作 IEEE 传播，但 API 文档不作该保证

- **类别**：精度风险
- **严重程度**：🔴 阻塞
- **设计文档位置**：DESIGN.md 第 1.1 节、1.2 节、2.3 节、2.4 节
- **问题描述**：设计写明负 `v_hat`“遵循 sqrt 的浮点传播行为”、`epsilon=0` 时按 IEEE 特殊值比较，并计划直接执行 `Sqrt(D,D)`/`Div(C,C,D)`。但 `Sqrt.md` 明确警告“src 中的数值为非正数，可能会产生未知结果”，这包含强制 case 14 的 `sqrt(0)`；`Div.md` 另有“注意除零错误”。因此“真实 NPU 验证一下”不能替代一个覆盖声明支持域的设计。当前接口还允许 `epsilon=0`，若 `v_hat=0`，分母就是零。
- **审查者视角**：case 14 是全零强制用例，期望 `0/(sqrt(0)+1e-8)=0`；case 13/通用输入又要求 NaN 和 epsilon=0 语义。设计依赖官方明确标为未知/错误的输入域，强制 case 是否可靠通过没有设计保证。
- **建议方案**：补充特殊域策略并给出 UB/性能代价。例如保留 `v_hat` 的符号/零值 mask，把 `Sqrt` 的输入替换为严格正的安全值，再用 `Compare/Select` 恢复 `sqrt(0)=0` 和负值→NaN；对分母零值显式构造与 golden 一致的 Inf/NaN，避免直接依赖未定义除零。若最终决定仅以目标 DAV_2201 实测行为为契约，应收窄“通用接口”声明，并把 case 14、epsilon=0+零分母、负 v_hat、±Inf/NaN 的定向测试设为开发前门禁，而不是开发完成后的观察项。
- **文档依据**：通配符检索 `^Sqrt` 仅得到 `Sqrt.md`，其“约束说明”有上述非正数警告；检索 `^Div` 仅得到 `Div.md`，其“约束说明”明确提示除零错误。两者虽然均支持 A2/A3 和 FP32，但产品支持不等于特殊输入语义有保证。

#### 问题 4：修正搬运与同步设计后，当前 UB 预算不再是闭合证明

- **类别**：内存规划
- **严重程度**：🟡 需讨论
- **设计文档位置**：DESIGN.md 第 1.5 节、2.2 节
- **问题描述**：预算只计四个 FP32 TBuf 与半精度 `rawIn/rawOut`，把 2048 B 泛称为“队列/实现余量”，但没有列出 Queue 类型、depth、每个 Buffer 的实际 `InitBuffer` 大小及对齐。问题 1/2 的修正很可能需要 FP32 输入/输出 Queue、额外暂存或多份事件安全 Buffer；这些不能事后默认由 2048 B 覆盖。特别是若为了处理问题 3 保存原始 `v_hat`/mask，也会增加 VECCALC 占用。
- **审查者视角**：`U` 已按近似分母尽量取到最大值，任何未建模的整 tile Buffer 都远大于 2048 B。现在的公式只能证明原设想的裸 TBuf 数量，而不能证明一个合法同步实现能够初始化成功。
- **建议方案**：在确定 TPosition/Queue/特殊值策略后，按真实对象逐项列出 `InitBuffer(queue_or_buf, depth, bytes)`，把所有按 256 B 对齐后的值相加，再反推 U。给出 Host 端整数溢出检查与 `sumAllocated <= ubSize - fixedReserve` 断言；reserve 仅保留给常数级开销，不承接整 tile 缓冲。

#### 问题 5：偏差修正从除法改为乘倒数，标量计算精度契约未定义

- **类别**：精度风险
- **严重程度**：🟡 需讨论
- **设计文档位置**：DESIGN.md 第 1.1 节、1.4 节、2.2 节、2.4 节
- **问题描述**：golden 表达式是 `m_new / (1-beta1**step)`、`v_new / (1-beta2**step)`；设计改成 Host 计算 `invBias` 后 Kernel `Muls`。这会改变舍入点，且文档没有规定 Host 的 `pow`/减法/倒数使用 float 还是 double、何时 cast 到 TilingData 的 float，也没有规定极大 step 或 beta 接近 1 时的下溢/溢出行为。
- **审查者视角**：现有评分 case 都是 step=1，风险可能被宽阈值掩盖，但设计声称支持通用 step，并计划增加 step=100 smoke case。没有标量位级契约就难以判断偏差来自 Kernel 还是 Host 预计算。
- **建议方案**：明确 TilingData 字段类型和 Host 计算顺序；建议用 double 计算 `pow` 与倒数、做 finite/denominator 检查后显式 cast float，并在 golden 侧用完全相同的标量值做诊断。同时增加“Kernel 乘倒数 vs golden 直接除法”的误差评估；若不满足阈值，改为 Kernel 标量除法等更贴近 golden 的实现。至少覆盖 step=1、2、100 和 beta 接近 1 的边界。

#### 问题 6：API 证据链接路径错误，后续开发者无法按文档复核

- **类别**：API 可行性
- **严重程度**：🟢 建议
- **设计文档位置**：DESIGN.md 第 1.2 节
- **问题描述**：表中链接使用 `../../../asc-devkit/docs/api/context/...`。从当前文件 `benchmarks/cannbench/operators/apply_adam_w/docs/DESIGN.md` 解析，该路径落到 `benchmarks/cannbench/asc-devkit/...`，而实际文档位于 `third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/...`，链接不可达。
- **审查者视角**：设计声称 API 已核验，但证据链接无法打开，会削弱审查和后续维护的可追溯性；也容易让开发者误以为查阅了另一份 devkit。
- **建议方案**：改为从仓库根可验证的正确相对路径，或在文首定义实际 `$ASC_DEVKIT_DIR` 后引用绝对的仓库内相对位置。保留每个 API 的同名前缀检索结果，尤其是 `Axpy.md/Axpy-25.md/Axpy接口.md` 三个变体的取舍依据。
- **文档依据**：实际通配符检索显示 `Axpy` 有 `Axpy.md`、`Axpy-25.md`、`Axpy接口.md` 三个变体；其余本设计使用的 API 也已分别检索 `^DataCopyPad/^Cast/^Muls/^Mul/^Sqrt/^Adds/^Div/^Add`。当前仓库仅在官方 plugin 目录下找到 `asc-devkit/docs/api/context`。

### Architect 回应

#### 问题 1：FP32 主 Buffer 的 TPosition 与 DataCopyPad 通路冲突

- **回应**：已修改（接受）
- **理由**：质疑成立。FP32 不再把 GM 数据直接搬入 VECCALC。修订后使用 `qVar/qGrad/qM/qV: TQue<VECIN,1>` 搬入四输入，结果写 `qOut: TQue<VECOUT,1>` 后搬出。计算 API 支持 VECIN/VECOUT LocalTensor，因而无需额外的 VECIN→VECCALC 拷贝。
- **文档依据**：`third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/DataCopyPad(ISASI).md` 的支持通路表与完整 Queue 示例；同目录 `Add.md`、`Mul.md`、`Muls.md` 等参数表明确 LocalTensor 支持 VECIN/VECCALC/VECOUT。
- **DESIGN.md 变更**：更新 §1.2、§1.3、§1.5、§2.2、§2.4.1；FP32 UB 对象改为四输入 Queue + 一输出 Queue。

#### 问题 2：缺少跨流水同步且 rawIn 复用存在覆盖风险

- **回应**：已修改（接受）
- **理由**：质疑成立。两条 dtype 路径均采用 Queue 同步模型，不依赖普通 C++ 语句顺序。CopyIn 均为 `AllocTensor→DataCopyPad→EnQue→DeQue`，输出为 `AllocTensor→Vector→EnQue→DeQue→DataCopyPad→FreeTensor`。半精度 `qRawIn` 必须在 Cast 消费后 `FreeTensor`，才处理下一个输入。
- **文档依据**：`DataCopyPad(ISASI).md` 完整示例使用 VECIN/VECOUT Queue；`third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/TQue.md` 说明 EnQue/DeQue 的生产者消费者同步。未选择手工 event ID，因此无需引入易错的 SetFlag/WaitFlag 编号管理。
- **DESIGN.md 变更**：更新 §1.3、§1.4、§1.5、§2.4.1、§2.4.2，伪代码写明每次 Queue 操作及 rawIn 生命周期。

#### 问题 3：Sqrt 非正输入与 Div 零分母没有文档保证

- **回应**：已修改（接受）
- **理由**：质疑成立。新增统一 `SafeSqrt/SafeDiv`。SafeSqrt 用 Compare mask 和 Select 把非正输入替换为 `FLT_MIN` 后才调用 Sqrt，再显式恢复 zero→0、negative/NaN→quiet NaN。SafeDiv 把零分母替换为 1 后才调用 Div，再依据原 numerator 的符号/ordered/zero mask 恢复 +Inf、-Inf 或 NaN。强制 case 14 不再直接把 0 送进 Sqrt；通用 epsilon=0+零分母也不再直接触发 Div 除零。
- **文档依据**：`Sqrt.md` 的非正输入警告、`Div.md` 的除零警告；`Compare.md`、`CompareScalar.md`、`Select.md`、`Duplicate.md` 均声明支持 A2 FP32。`Select.md` 的模式1/2临时区要求已计入 8KB UB。
- **DESIGN.md 变更**：更新 §1.1、§1.2/§1.2.1、§1.3、§1.4、§1.5、§2.2、§2.3，并新增 §2.4.3 的完整特殊域伪代码和开发前真实 NPU mask 语义门禁。

#### 问题 4：搬运、同步及特殊域修正后 UB 预算不闭合

- **回应**：已修改（接受）
- **理由**：质疑成立。修订后逐对象列出 Queue/TBuf 的 depth、TPosition 和对齐大小。FP32 为 `5*Align256(4U)`，半精度为 `4*Align256(4U)+2*Align256(2U)`，两者都等效为 20U；再统一加入 `Align256(U/8)` mask、Select 固定 8192B 和仅用于常数级开销的 2048B reserve。Host 必须 checked add/multiply 并断言实际分配和不超过 UB。
- **文档依据**：`Select.md` §约束说明明确 A2 模式1/2需要预留8KB；`Compare.md/CompareScalar.md` 规定 count 对应字节数需 256B 对齐；`TQue.md` 与 DataCopyPad 示例给出 depth=1 InitBuffer 模式。
- **DESIGN.md 变更**：重写 §1.5 和 §2.2 的对象表、公式、整数溢出检查及 `sumAllocated` 断言。

#### 问题 5：乘倒数的 Host 标量精度契约不明确

- **回应**：已修改（接受）
- **理由**：质疑成立。attrs 先提升为 double，严格按 `pow(double,int64)→1.0-power` 求 denominator；检查有限且正后显式 cast 到 float，再执行一次 float 除法得到写入 TilingData 的 reciprocal。结果记录同时保存 double denominator、float denominator、float reciprocal。step=1/2/100 和 beta near 1 纳入定向测试；若乘倒数与 golden 直接除法超过对应 dtype 阈值，Developer 必须返回 design_issue，再改用显式 denominator Tensor + Div，而非放宽精度标准。
- **文档依据**：任务 `golden.py` 的 `1-beta**step` 直接除法；`Muls.md` 要求 scalar 与 FP32 Tensor 元素类型一致；`Div.md` 提供 FP32 Tensor 除法备选路径。
- **DESIGN.md 变更**：更新 §1.1 标量计算顺序与检查，§2.2 TilingData 增加 bias denominator 诊断字段，并保留测试门禁。

#### 问题 6：API 证据链接未直接指向官方 plugin 真源

- **回应**：部分修改
- **理由**：原链接实际可达：`benchmarks/cannbench/asc-devkit` 是指向 `third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit` 的有效符号链接，`readlink -f` 和文件存在性检查均已确认。因此“链接不可达/仅 plugin 目录存在”这一事实判断不成立。但直接引用官方 plugin 真源确实更清晰、更可追溯，故接受改链建议。
- **文档依据**：工作区 `benchmarks/cannbench/asc-devkit` 的 symlink 目标；官方真源 `third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/docs/api/context/`；`Axpy.md`、`Axpy-25.md`、`Axpy接口.md` 三个变体均已核验并记录取舍。
- **DESIGN.md 变更**：§1.2 所有链接改为 `../../../../../third_party/cannbot-skills/plugins-official/ops-direct-invoke/asc-devkit/...`，并明确 Axpy 三变体检索结论。

### 回应统计

- 接受 5 项，保留 0 项，部分修改 1 项。
- `DESIGN.md`：已更新。
