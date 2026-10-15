# API Algorithm Optimization Strategies

本文用于 `problem_family=api_algorithm` 的 candidate 设计。目标是让 agent 能做 API、算法局部和片上融合级
改写，同时避免非法 API、精度变化和平台越界。

## Scalar Anti-patterns

热路径出现以下模式时，优先生成结构性 rewrite，而不是只调参数：

- 多层小循环轴可合并但仍逐轴循环。
- 每 tile 重复计算 shape、offset、stride、mask 等 loop invariant。
- 分支在内层循环中随元素/小 tile 变化，导致 Scalar 占比高。
- `GetValue/SetValue` 在生产热路径逐元素访问 GM/UB。
- `std::` 容器、动态内存、复杂对象构造或 Host/Kernel 头混用。
- TPipe/TBuffer/TQue 封装只服务单 stage，小 case 中封装开销超过收益。
- SetFlag/WaitFlag 可以表达局部依赖，却使用 queue 或全局 barrier。
- Scalar 与 Vector 间频繁同步等待或数据搬移。
- debug/稀疏例外路径没有与热路径隔离。

## Vector / API Templates

| 场景 | Decision gate | Structural patch shape |
| --- | --- | --- |
| repeatTime 风险 | 行数/repeat 接近或超过 API 上限 | Host tileRows 限制或 Kernel 分批 repeat，恢复 mask/tail |
| Counter mode | 正常 repeat 下 stride/广播低效且平台支持 | 使用 Counter mode 或保留 normal fallback |
| Cast 密集 | Cast 指令占比 >20% 或 fp16/fp32 往返 | 合并 Cast、统一 compute dtype、保留 RoundMode |
| UB fusion | VECTOR 段之间有 MTE3+MTE2 GM 往返 | Vector/Reduce/Cast 链留 UB，延迟 CopyOut |
| 融合指令 | Mul+Add/Sub/Acc 模式明显 | 使用 VMULA/VMULS/VMADD 类 fused instruction |
| 低延迟 reduce | 手写 scalar/for reduce 或 repeat 低效 | 使用合法 Reduce API / tree reduce / group reduce |
| Online softmax | 完整 score/prob GM staging 或双 pass 开销 | running max/sum/O_acc 增量更新 |
| Sort/MrgSort | 标量 compare 或逐元素 TopK | Sort/MrgSort/radix/two-level merge，维护 index/tie-break |

## Platform / API Boundary

- API overload、repeat/mask、Cast mode、DataCopyPad、Pipeline event 不确定时，只能通过 optional index 点读具体文档。
- A2/A3/Blaze/GMM/MatMul 高阶 API 不能直接套到所有 SoC；候选要写平台边界。
- `GlobalTensor::GetValue/SetValue` 生产热路径通常不可接受；稀疏输出、TopK、NonZero 需结合算法语义判断。
- MatMul/FA/Sort/Reduce API candidate 必须同时写 workspace、dtype accumulate、tail、同步和平台支持。

## Capacity / Semantics

- Fusion 后 `live_ub_bytes <= UB`，且 tail mask/padding 不会进入后续 math。
- repeat 分批后每批 mask、stride、地址偏移和 `repeatTime` 类型上限都成立。
- Cast/Reduce/Softmax 改写不得改变舍入、accumulate dtype、稳定性或相等值规则，除非用户显式允许。
- Sort/TopK index 输出、稳定性、NaN/Inf 和 tie-break 是语义门禁，不是性能细节。

## Abort Conditions

- API overload、平台支持或 repeat limit 未确认。
- candidate 降精度、改变排序/归约稳定性或缩小 dtype/shape 支持。
- UB fusion 超容、lifetime alias 不清或 padding 语义不清。
- Counter mode、MrgSort、MatMul、Reduce API 平台边界不可确认。

## Metric Delta

- Scalar/ICache/ScalarLDST 开销下降，Vector repeat 效率上升。
- Cast/misc 指令占比下降或符合精度模型。
- GM 往返减少，UB 内融合链更长。
- 算法阶段 Sync/等待减少且精度 gate 通过。
