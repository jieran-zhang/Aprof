---
schema_version: aprof.knowledge-record/v1
id: planning.elementwise.fallback
kind: strategy
version: 1.1.0
status: active
title: Elementwise / Broadcast 通用回退
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
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/broadcast/patterns.md
  original_path: ops/ascendc-tiling-design/references/broadcast/patterns.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 165
  sha256: sha256:8b118ddbc4e70ada3debaf013838c8690abc85bb5f9d847d113ed2db40208830
  excerpt_sha256: sha256:8b118ddbc4e70ada3debaf013838c8690abc85bb5f9d847d113ed2db40208830
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
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/adv_api/tensor_transform/Broadcast.md
  original_path: docs/zh/api/SIMD-API/adv_api/tensor_transform/Broadcast.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 63
  - 194
  sha256: sha256:22082229ba15eb475b6cb592ea173481932704e0028eda06b6b53f9e6b39122a
  excerpt_sha256: sha256:cbf6c8dfa159a783b9ebfcf56b8cf7108491548ed1c0fe7183f806874dca6fd0
learning: {}
tags:
- broadcast
- elementwise
seed_reason: 固定开源修订审读并补全中文算法、所有权、字节容量与选择边界；保留原 ID/主归属/数值合同，未做 NPU 性能验证。
parent: planning.elementwise
references:
- planning.elementwise.continuous
- planning.elementwise.broadcast
evidence_status: source_reviewed_not_benchmarked
---

# Elementwise / Broadcast 通用回退

## 回退触发与必须保留的合同

当连续性、广播形状、有效长度、容量、API 支持或数值等价任一项未知/不成立时，保留已有已验证 entry/key。回退首先是一条实际可执行且被验证的路径；本条给出如何记录与最小化它的规划，不因来源中有示意 API 就声称新 baseline 已验证。C2 写出专用路径的完整适用谓词以及互补域，host 对每个输入只能选择一个互斥 entry，不能先执行部分新输出再静默改走旧路径。

逐元素运算保留原计算顺序、dtype/Cast、特殊值、输出别名规则；广播保留完整右对齐 shape 和真实 stride。若输入非连续，不展平为同形线性数组；若存在部分重叠的输入输出 view，不允许无依据地分核并发。空输出在 host 返回，非法 shape 按原接口错误处理。

## 最小任务所有权与可容纳的片段

连续、同形的已知子域可令每个任务拥有一个不相交的连续输出片段；一般广播/stride 子域按输出坐标解码，读取 `Σcoord_i*stride_ji`，广播轴 stride=0。每个输出只写一次，输入只读，无归约和全局同步。最保守的单任务执行也必须完整覆盖全部输出，不能靠启动多核掩盖分区证据缺失。

固定 tile U 至少为一个当前 API 合法且可容纳的有效工作单元。令 A_a 为字节对齐，s_j 为每个独立输入/输出/计算区元素字节，d_j 为实际份数：`B_UB=Σ_j d_j*A_a(U_j*s_j)+B_fixed+T_api≤B_available`。stride 广播的 U_j 可小于输出 U，但若实现显式展开就另计 U*s_j。即使 fallback 也不能忽略升 FP32、双缓冲和 Broadcast 临时区。

无法证明一个向量 tile 的资源或 API 约束时，继续使用原框架/库实现；“U=1”不是普遍安全策略，基础搬运/向量接口仍可能要求最小地址/长度粒度。必要流量约为有效输入读取字节加输出字节，一般索引实现可能重复读取广播源；这是保证语义的基准成本，不作收益承诺。

## 执行骨架与可复用片段

```python
if validated_specialized_domain(metadata):
    return specialized_entry(metadata)
assert baseline_entry_is_validated_for(metadata)
# 下列逻辑是 baseline 应满足的语义，不是擅自替换现有 baseline。
for out_tile in uniquely_owned_output_tiles():
    for out_coord in valid_coords(out_tile):
        args = [read_input(j, sum(out_coord[i]*stride[j][i]
                                 for i in range(rank))) for j in inputs]
        write_once(out_coord, oracle_elementwise(args))
```

在已确认的连续 FP32 Add 主片域，当前工程的队列已完成搬入且 x/y/z 是不重叠、容量足够的 LocalTensor，n>0 且满足接口合法范围时，计算部分可保持如下最小代码；非对齐搬入/搬出仍由原基线封装处理：

```cpp
AscendC::Add(zLocal, xLocal, yLocal, n);
```

来源 Add 工程用 AllocTensor→DataCopy→EnQue→DeQue→Add→EnQue→DeQue→DataCopy→FreeTensor 管理生命周期。保留该同步链，不能把局部 Add 片段当完整 kernel。来源工程的整除长度、固定核数与每核全载只是样例条件；回退 entry 仍需覆盖任意声明形状的尾块。

## 往专用路径补证据与验证

| 缺项 | 补齐后可重新比较的方向 |
| --- | --- |
| 真实连续性/stride 未知 | 固定 shape-stride 映射后比较连续分区 |
| 广播轴或复用域未知 | 明确输入 offset 与每核复用范围后比较 UB 广播 |
| UB/API 临时区未核算 | 给出字节账和合法最小 tile，再讨论队列深度 |
| dtype/数值误差未定义 | 对照原 oracle 验证计算与 Cast 顺序 |
| 平台能力未知 | 按实际 SoC/SDK 编译目标确认 API，保持现有 entry |

验证空/标量、非整除 tile、多核尾块、非连续 view、交替广播轴、别名和所有输出覆盖；用 sentinel 检查只写有效输出且没有空洞。910C/A3 不默认支持 950 的 NDDMA/动态 Broadcast；scope=all 是检索范围。来源事实为连续分块、广播索引与 TQue 数据流；一般坐标 baseline、互斥分派和容量账为工程推导。来源审读完成，未进行 NPU 性能测量，未将未验证的草图注册为新的 fallback entry。
