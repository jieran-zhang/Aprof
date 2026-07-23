# Bound Deep Routing

本文把 single-core bound 现象蒸馏成 AProf 诊断侧的二级路由。它不替代六类
problem family；它只帮助 agent 在看到 `Scalar`、`MTE`、`VEC/CUBE` 或 no-bound
现象后，继续追问更精确的源码根因、metric 反证和缺失证据。

## 读取策略

- 只有 `PipeUtilization.csv`、trace/timeline、`ArithmeticUtilization.csv` 或源码形态已经指向
  `Scalar` / `Memory` / `VEC` / `CUBE` / no-bound 时才读取本文。
- 读取本文后仍然回到六类 reference：`tiling`、`data_movement`、`pipeline_parallel`、
  `onchip_memory`、`ai_core_utilization`、`api_algorithm`。
- 不直接读取 CANNBot 大型 `SKILL.md`。若需要核对具体 API 或算子族细节，按
  [cannbot-knowledge-index.md](cannbot-knowledge-index.md) 点读单个具体 reference。

## 输入信号

| 信号 | 主要来源 | 先问的问题 |
| --- | --- | --- |
| Scalar 占比高 | `PipeUtilization.csv`、trace、源码 | 是 tiny workload、repeat/mask 控制开销、热循环分支，还是编译器 spill/LoadStore？ |
| MTE2/MTE3 高 | `PipeUtilization.csv`、`Memory.csv`、trace | 是真带宽 bound、假 MTE 小块 bound、重复 GM 往返，还是 DB 未重叠？ |
| VEC 高 | `PipeUtilization.csv`、`ArithmeticUtilization.csv`、trace | 是真实高延迟向量指令、Cast/reduce/API 低效，还是 UB bank conflict 放大？ |
| CUBE 低或高 | `PipeUtilization.csv`、`ArithmeticUtilization.csv`、trace | 是 compute roofline、L1/L0 复用、Fixpipe、AIC/AIV 节拍，还是任务数不足？ |
| 各 pipe 都不高 | `PipeUtilization.csv`、trace | 是 no-bound 流水气泡、同步等待、MTE2 preload gap、测量/小 workload 限制？ |

## Scalar Bound 二级判别

先排除 `workload_limited`：tiny/small workload、每核元素很少、Task Duration 被启动和
TPipe 初始化主导时，Scalar 高不等于 API 问题。

| 深层根因 | 源码锚点 | Metric / 反证 | 路由 |
| --- | --- | --- | --- |
| repeat/mask/tail 控制开销 | 每条 Vector API 前手算 `repeatTimes`、`tailSize`、`SetVectorMask`；tail 单独小分支 | Scalar 高但 VEC/MTE 不高；tail case 明显慢 | `api_algorithm` + `tiling` |
| 热循环分支过多 | `if (i==0)`、`if (i==last)`、`if (i % k == 0)` 在大循环内 | trace 中 Scalar 窗口周期性出现；ICache miss 可疑 | `api_algorithm` |
| 隐式状态机循环 | `while(Iterate(...))`、多级 `Next()` 状态推进 | Scalar/ICache 高，源码函数很大且分支密集 | `api_algorithm` |
| 编译器 spill / LoadStore | 大结构体、结构体数组动态下标、成员变量热访问、多级指针、hot loop 取地址/构造对象 | Scalar 高但实际标量算法不多；需要编译报告或 trace 指令类型确认 | `api_algorithm` |
| Queue/TBuf/Tpipe 抽象过重 | 简单固定场景仍在 hot loop 维护 queue/buffer 状态 | Scalar 高且同步/queue 操作密集；替换需验证语义 | `pipeline_parallel` + `api_algorithm` |

输出时不要只写“Scalar 高”。必须说明它更像 workload 限制、控制开销、spill、同步抽象，
还是缺证据。

## Memory Bound 二级判别

MTE 高至少分成四类，优化方向和诊断证据完全不同：

| 深层根因 | 判别方法 | 反证 | 路由 |
| --- | --- | --- | --- |
| 真带宽 bound | `Memory.csv` 带宽利用率接近平台上限；实际/理论搬运耗时接近；copy 粒度大且连续 | 带宽低、指令密度高、L2 hit 低时不是纯带宽上限 | `data_movement` |
| 假 MTE bound / 小块 bound | MTE2 高但带宽不高；单次 copy 字节小；`ai*_mte*_instructions` 密集 | copy 粒度大且带宽高时不成立 | `tiling` + `data_movement` |
| 重复 GM 往返 | 读/写流量放大，Vector 链中间结果 `CopyOut` 后又 `CopyIn`，workspace 自读自写 | 理论最小流量与实际流量接近时不成立 | `data_movement` + `onchip_memory` |
| 搬运未重叠 | trace 中 MTE2、VEC/CUBE、MTE3 串行；`InitBuffer(...,2)` 但 EnQue/DeQue 顺序阻塞 | trace 有稳定 overlap 时不成立 | `pipeline_parallel` |
| L2/局部性失败 | L2 hit 低，切分轴破坏连续性，跨核重复读 | 一次性流式读且无复用需求时低 hit 不一定是问题 | `onchip_memory` + `data_movement` |

## VEC Bound 二级判别

VEC 高可能是真计算瓶颈，也可能是 API/UB 问题放大：

| 深层根因 | 判别方法 | 反证 | 路由 |
| --- | --- | --- | --- |
| 高延迟向量指令主导 | trace 中 `exp/log/rec/rsqrt` 或 reduce 类事件占比高；算法确实需要 | 算法可以融合或替换但未做，不能直接写“已到极限” | `api_algorithm` |
| Cast 密集 | FP16/BF16 输入下 fp32 vector/cast 指令比例异常；源码多次 `Cast` 往返 | 精度要求必须全链 FP32 且 Cast 已批量化 | `api_algorithm` + `onchip_memory` |
| UB bank conflict | `ResourceConflictRatio.csv` 中 vector conflict 高；连续 buffer 起址或 `blk_stride` 易回卷同 bank/group | MTE 或同步才是主导时不要归因 bank | `onchip_memory` |
| Vector 粒度太小 | Vector API count/repeat 小，tail 单独 API 多，MTE/Scalar 也高 | 单次 tile 足够大且 VEC 指令本身为主时不成立 | `tiling` + `api_algorithm` |
| UB 融合链缺失 | 多步 vector 中间结果落 GM；MTE2/MTE3 夹在 vector 段之间 | 中间结果跨 kernel 或跨 task 必须持久化时不成立 | `data_movement` + `api_algorithm` |

## CUBE / Mix Kernel 二级判别

MatMul、GMM、FA 先同时看 AIC、AIV、MTE1/MTE2、Fixpipe 和任务数：

| 深层根因 | 判别方法 | 路由 |
| --- | --- | --- |
| MN 任务数不足 | `ceil(M/baseM) * ceil(N/baseN) < AIC` 或 `totalTasks << coreNum` | `ai_core_utilization` + `tiling` |
| MN 尾碎片负载不均 | 核间 `aic_time` 差异大，尾 M/N tile 拖慢 | `tiling` + `ai_core_utilization` |
| 长 K 可切分 | MN 欠并行但 K 很长，默认只在核内 K loop | `ai_core_utilization` |
| L1/L0 复用不足 | GM->L1/MTE1 高，L1/L0 预算或 pingpong 不合理 | `onchip_memory` + `data_movement` |
| Fixpipe/写回异常 | `aic_fixpipe_ratio` 高，ODD-M/N、row stride、后处理写回可疑 | `tiling` + `api_algorithm` |
| AIC/AIV 节拍不匹配 | AIC/AIV time 差大、wait 高、后处理或 workspace 往返 | `pipeline_parallel` + `ai_core_utilization` |

## No-Bound 二级判别

各 pipe 都不高时不要立即给泛化优化建议，先分流：

| 深层根因 | 证据 | 路由 |
| --- | --- | --- |
| 流水气泡 | trace 中 CopyIn/Compute/CopyOut 之间有空洞；wait ratio 高 | `pipeline_parallel` |
| 假 pingpong | L1/UB 双缓冲空间存在，但 `SetFlag` 后紧跟 `WaitFlag`，或 PING/PONG 间 gap 明显 | `pipeline_parallel` |
| 同步过强 | `PipeBarrier<PIPE_ALL>`、`SyncAll`、全局 wait 在 tile 循环内 | `pipeline_parallel` + `api_algorithm` |
| 小 workload | workload model 显示可达利用率低，observed 接近 attainable | `workload_limited` |
| 测量不足 | 单次 run、CV 不稳、sim-only proxy | `measurement_limited` |

## 输出要求

- 每个最终问题至少给 2 个 metric：一个源码/tiling 锚点，一个 report/trace/硬件分母。
- 对 bound 现象输出 `bound_interpretation` 或写入 `roofline_interpretation`，说明为何没有停留在表层现象。
- 对未确认的二级根因写入 `missing_evidence`，例如 `Memory.csv`、`ResourceConflictRatio.csv`、trace
  overlap、L1/UB capacity formula、repeat/mask 参数、platform bank structure。
