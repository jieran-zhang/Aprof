---
schema_version: aprof.knowledge-record/v1
id: planning.elementwise.continuous
kind: template
version: 1.1.0
status: active
title: 连续输出分区与均衡尾块
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/elewise/tiling.md
  original_path: ops/ascendc-tiling-design/references/elewise/tiling.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 215
  sha256: sha256:40fd7187bf84f9c454fc5a53b0c5adc1e9594e6054901f21c518cae1ee3ad0ad
  excerpt_sha256: sha256:40fd7187bf84f9c454fc5a53b0c5adc1e9594e6054901f21c518cae1ee3ad0ad
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/elewise/tiling.md
  original_path: ops/ascendc-tiling-design/references/elewise/tiling.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 215
  sha256: sha256:40fd7187bf84f9c454fc5a53b0c5adc1e9594e6054901f21c518cae1ee3ad0ad
  excerpt_sha256: sha256:40fd7187bf84f9c454fc5a53b0c5adc1e9594e6054901f21c518cae1ee3ad0ad
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/elewise/patterns.md
  original_path: ops/ascendc-tiling-design/references/elewise/patterns.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 46
  sha256: sha256:8a1351ff5295af67a53383682a4264aca6a19a113a2cdb47158938f73bae0cec
  excerpt_sha256: sha256:8a1351ff5295af67a53383682a4264aca6a19a113a2cdb47158938f73bae0cec
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/00_introduction/01_add/add_tpipe_tque/add_tpipe_tque.asc
  original_path: examples/01_simd_cpp_api/00_introduction/01_add/add_tpipe_tque/add_tpipe_tque.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 24
  - 65
  sha256: sha256:3fd854a223214eec19b03eebf4be3397c81358ebd526d07b17202a5fd522b654
  excerpt_sha256: sha256:5c62ddc8f95f62eca158343a50005bb51f6f08f057946a4d67ba030dbd26da6c
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/00_introduction/01_add/add_tpipe_tque/README.md
  original_path: examples/01_simd_cpp_api/00_introduction/01_add/add_tpipe_tque/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 7
  - 18
  sha256: sha256:14f2219ba48fdf536ac5cf018c2f70b6fd4a0a074d2dede49c9a6ca187d8e9dd
  excerpt_sha256: sha256:accaf93a389515058582a1b86c73fddc763155871b2f09255a4a08212d7541de
learning: {}
tags:
- broadcast
- elementwise
seed_reason: 固定开源修订审读并补全中文算法、所有权、字节容量与选择边界；保留原 ID/主归属/数值合同，未做 NPU 性能验证。
parent: planning.elementwise
references:
- planning.elementwise.broadcast
- planning.elementwise.fallback
evidence_status: source_reviewed_not_benchmarked
---

# 连续输出分区与均衡尾块

## 适用域与先决语义

输入、输出具有相同的逻辑 shape，且每个输出元素只依赖同一下标的输入或已冻结的只读标量。输入真实连续或已存在合法的连续视图，才可将 shape 的乘积展平为 N；带 stride 的 view 不能仅凭元素总数走本模板。N=0 在 host 空张量分支处理，不启动会执行零 count 或除以零的 kernel。

一元函数、同形 Add/Mul、独立的算术链均可采用相同所有权。C2 先明确每步 dtype、Cast 舍入、溢出/饱和、NaN/Inf、输出别名和计算顺序。来源提出半精度加减链升 FP32 的候选；这是需要与 oracle 比较的数值实现选择，不是对所有 FP16/BF16 Add 的自动改写许可，更不能保证最后 Cast 后保留任意小增量。

## 分区、任务数与核内循环

令 g 为满足实际搬运接口及输出独占写要求的元素粒度，Q=ceil(N/g) 为逻辑块数。选择 1≤C≤min(Q,C_available)，定义 q=Q//C、r=Q%C。核 c 的起始块 b_c=cq+min(c,r)，块数 n_c=q+[c<r]，其有效元素区间为 `[b_c*g, min((b_c+n_c)*g,N))`。所有区间并集恰为 `[0,N)`，交集为空；尾部不足 g 的部分由唯一末核处理，绝不通过重叠搬出尾块补齐。

核内再按 U 个元素分 tile，循环条件用当前位置小于核的有效结束位置，`valid=min(U,end-pos)`。只在 valid>0 时执行搬运与计算。U 是片上工作集粒度，g 是分核边界粒度，两者不必相同。若 C 很大而单核只有一个很短 tile，需与较少核数比较；增加 task 数、减少每核工作量、减少流水循环之间存在取舍。

所有输入只读，每个输出片段只有一个写者，无跨核归约和全局同步。精确原址逐元素操作只有在 API 与算子别名合同均允许时才可使用；部分重叠 view 可能使一个核覆盖另一核尚未读取的输入，必须用已有安全基线。

## 字节容量与成本模型

定义 A_a(x)=ceil(x/a)*a，为按 a 字节向上对齐。s_j 是第 j 个存活张量的元素字节数，d_j 是它实际分配的 buffer 份数（含双缓冲），T_api 是按当前 API、dtype、形状查询的临时字节，B_res 是其他必须预留的字节。一般容量合同为：

`B_UB = Σ_j d_j*A_aj(U*s_j) + B_fixed + T_api ≤ B_available`。

这里计入所有已分配且未释放/未合法复用的区域；仅逻辑上不再使用但 TPipe 仍保留的独立分配不能从账上删除。若共享同一物理区，必须说明不同阶段的生命周期互斥以及跨流水依赖已完成。

同 dtype 二输入 Add、两个输入队列与一个输出队列深度都为 d 时，数据区约 `3*d*A_a(U*s)` 字节；升 FP32 另有 K 个非别名中间区，则另加 `K*A_a(4U)`。K 由 API 的 dst/src 别名约束决定，不应把一个 Cast buffer 当三个运算都能安全原址复用。UB 余量不足一个合法 tile 时直接淘汰该候选，不能把 U 强制改成 1 掩盖超容。

一次无复用扫描的必要 GM 数据量为 `B_GM=N*(Σ_inputs s_i+Σ_outputs s_o)`，不含额外 workspace、重读和隐式变换。设 F 为计算操作量、BW_eff/P_eff 为同一目标机测得的有效带宽/算力，则 `max(B_GM/BW_eff,F/P_eff)` 只是服务时间下界；实际还包括 launch、tile 循环、同步及尾块开销。该表达式用于解释候选，不能给出未经测量的微秒数。

来源有 bits/bytes 混用的示意公式；本条全部以字节重推，若输入是 bit 宽度 b，先显式转换 s=b/8。上游 4KB 每核、512 元素、256B repeat 等是其示例选择，不能代替当前目标的合法对齐或性能阈值。

## 参数选择与替代边界

| 决策 | 优先检查的条件 | 不满足时的路径 |
| --- | --- | --- |
| 展平 | 同 shape、真实连续、逐元素无依赖 | 广播模板或保留 stride 的基线 |
| 更多核 | 独立逻辑块够多，单核工作能摊销启动/调度成本 | 比较更少 C，并保持完整覆盖 |
| 更大 U | 片上容量、API count 范围、足够 tile 循环 | 减 U 或降低队列深度 |
| 双缓冲 | 两份数据区确实可容纳，存在可重叠阶段 | 单缓冲；双缓冲本身不证明速度更快 |
| 半精度升 FP32 | 语义允许且精度需要，K 已确认 | 保持 oracle 认可的原 dtype 路径 |

Host 用溢出安全的宽整数计算 shape 乘积、Q、偏移与 U*s；把 uint64 值转换为搬运接口的 uint32/int32 字段前验证范围。tile 的有效长度、存储长度、搬运字段单位要分别保存，不能共享一个含义不清的 length。

## 可执行伪代码

```python
# host；checked_product 与 choose_tile 已证明不溢出、容量足够。
N = checked_product(shape)
if N == 0: return empty_result(shape)
Q = (N + g - 1) // g
C = choose_cores(1, min(Q, available_cores))
q, r = divmod(Q, C)
U = choose_tile(capacity_bytes, dtype_sizes, queue_depths, api_tmp)
# kernel(c)
begin = (c*q + min(c, r))*g
end = min(begin + (q + int(c < r))*g, N)
for pos in range(begin, end, U):
    valid = min(U, end-pos)
    xs = load_valid_inputs(pos, valid)  # queue producer -> consumer
    ys = elementwise_with_frozen_casts(xs, valid)
    store_valid_outputs(pos, ys, valid) # 不写 [valid,U) 的 padding
```

## 有界 Ascend C 片段与同步上下文

下段采用来源 Add 样例的 TQue 生命周期，适用于一个合法对齐的 FP32 主 tile。xGm/yGm/zGm 已按本核 begin 绑定；队列已用字节容量初始化；pos 相对本核起点；n>0 且符合 DataCopy 主块约束。非对齐尾 tile 改用经核验的有效长度 DataCopyPad 封装，不能直接沿用主块搬出。

```cpp
// 包含 kernel_operator.h；inX/inY 为 VECIN，outZ 为 VECOUT。
auto x = inX.AllocTensor<float>();
auto y = inY.AllocTensor<float>();
AscendC::DataCopy(x, xGm[pos], n);
AscendC::DataCopy(y, yGm[pos], n);
inX.EnQue(x); inY.EnQue(y);
x = inX.DeQue<float>(); y = inY.DeQue<float>();
auto z = outZ.AllocTensor<float>();
AscendC::Add(z, x, y, n);
outZ.EnQue(z);
inX.FreeTensor(x); inY.FreeTensor(y);
z = outZ.DeQue<float>();
AscendC::DataCopy(zGm[pos], z, n);
outZ.FreeTensor(z);
```

EnQue/DeQue 表达搬入→计算→搬出依赖；不得在同一物理区的异步消费者完成前覆盖或回收。原 Add 样例固定可整除的输入并将每核整段一次放进 UB，本条的 q/r 和核内 U 循环是为任意合法长度增加的规划推导，不能把样例直接改 totalLength 后视作通用 kernel。

## 平台、验证与证据

固定 asc-devkit 样例 README 给出的范围是 Atlas A2/A3（CANN≥9.0）和 950PR/950DT（CANN≥9.1）；这是该修订的样例范围。面向 910C/A3 应核对实际 SoC/编译目标，不能借用 950 的寄存器路径、NDDMA 或动态 Broadcast 能力。scope=all 仅表示可检索，未证明任意平台、dtype、API 组合可执行。

至少验证 N∈{0,1,g−1,g,g+1,U−1,U,U+1}、Q 不能整除 C、多核最后一片、最大整数偏移、全分配容量和精确输出覆盖。数值用大/小量级混合、±0、NaN/Inf、溢出边界检查声明的合同。来源事实是均匀连续分区、UB 分块、队列数据流；均衡公式、字节模型与参数比较为本条工程推导。证据状态为 source_reviewed_not_benchmarked，无 NPU 时延或收益验证。
