---
schema_version: aprof.knowledge-record/v1
id: planning.reduction.fallback
kind: strategy
version: 1.1.0
status: active
title: Reduction / Norm / Softmax 通用回退
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 151
  sha256: sha256:c74ad927867806d42723213292831e22c84a2e84d75230e5aa615dee1500782a
  excerpt_sha256: sha256:c74ad927867806d42723213292831e22c84a2e84d75230e5aa615dee1500782a
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/patterns.md
  original_path: ops/ascendc-tiling-design/references/reduction/patterns.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 212
  sha256: sha256:9b8d774662fadf2fc4db38e48bd4124974d27a8ad7a6feac73a1ef55937fdcd8
  excerpt_sha256: sha256:9b8d774662fadf2fc4db38e48bd4124974d27a8ad7a6feac73a1ef55937fdcd8
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 151
  sha256: sha256:a41ac2ff57f181c342d823a1b453bfabfb20c56bf840e31f4dff7232cefdc80a
  excerpt_sha256: sha256:a41ac2ff57f181c342d823a1b453bfabfb20c56bf840e31f4dff7232cefdc80a
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/ar-colsplit.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-colsplit.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 149
  sha256: sha256:88ada1918f629dec9839471d1be29cddf4e25b4f9839a59fc3d7678fbd555996
  excerpt_sha256: sha256:88ada1918f629dec9839471d1be29cddf4e25b4f9839a59fc3d7678fbd555996
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/ara-rowsplit.md
  original_path: ops/ascendc-tiling-design/references/reduction/ara-rowsplit.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 219
  sha256: sha256:e7c5be5d9f510f22c989fa443a8dfe5e929312b2ccb82cb3cc59f2fdf83d9d25
  excerpt_sha256: sha256:e7c5be5d9f510f22c989fa443a8dfe5e929312b2ccb82cb3cc59f2fdf83d9d25
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/alg-welford.md
  original_path: ops/ascendc-tiling-design/references/reduction/alg-welford.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 74
  sha256: sha256:6c8e784dad546cb1caa07867596721b3d1c8ecc746396df5392054f44d84eb28
  excerpt_sha256: sha256:6c8e784dad546cb1caa07867596721b3d1c8ecc746396df5392054f44d84eb28
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/multi-axis-transform.md
  original_path: ops/ascendc-tiling-design/references/reduction/multi-axis-transform.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 83
  sha256: sha256:2a18e0f523a8101607fc3fbe388517869ce25bd6d2f51be57444f46617f7d96f
  excerpt_sha256: sha256:2a18e0f523a8101607fc3fbe388517869ce25bd6d2f51be57444f46617f7d96f
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/reduction_compute/ReduceSum.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/reduction_compute/ReduceSum.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 38
  - 221
  sha256: sha256:bd72fc07e459c8cc3e15984c2ba1c3b06071a24ecbf7f1ca1116f85ae55888bf
  excerpt_sha256: sha256:52af589db67d29084013c336da7bebe1a3eeee3677fc13ee8b7e57e5772c604a
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/adv_api/reduction_operations/ReduceSum_interface/ReduceSum.md
  original_path: docs/zh/api/SIMD-API/adv_api/reduction_operations/ReduceSum_interface/ReduceSum.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 40
  - 107
  sha256: sha256:d6cbc4b85d82e5cedc72de6bc544a61b600f2528cf028685bed88ea8c014c3fc
  excerpt_sha256: sha256:dc8c50c09005460290fb06a2c8c4fb6cb9a8828f521a1e9f01735acd2be90de6
learning: {}
tags:
- numerical-state
- reduction
seed_reason: 固定开源修订审读并补全中文算法、所有权、字节容量与选择边界；保留原 ID/主归属/数值合同，未做 NPU 性能验证。
parent: planning.reduction
references:
- planning.reduction.fullload
- planning.reduction.split
- planning.reduction.statistics
evidence_status: source_reviewed_not_benchmarked
---

# Reduction / Norm / Softmax 通用回退

## 适用条件与保留对象

FullLoad 无法证明完整工作集可容纳、split 缺少合并/同步依据、统计状态不满足精度合同，或 layout/dtype/平台不在候选范围时，执行已有已验证的归约 entry/key。C2 必须写明该真实 fallback 的入口、支持范围及与专用路径互斥的谓词；本条的算法骨架用于审阅回退正确性，不把新写的通用循环自动认作已验证实现。

回退保留归约轴与 keepDims、输入变换、累加 dtype、归约顺序/允许误差、count/correction、epsilon 位置、NaN/Inf/±0、arg tie 与索引类型。空归约组、非法轴、不合法 p 按原接口返回或报错。不得把 variance/std/norm/softmax 统一降为 sum，也不得把空输入交给可能不写结果的零 count API。

## 输出所有权与保守流式规划

最保守的向量规划按非归约输出组分核，每组唯一 owner，用小而合法的输入 chunk 遍历全部真实归约坐标；仅在这个核内合并状态，完成后 finalize 一次并写一次。即使独立输出组少于核数，也可少开核完成，先保证语义，不强制用跨核 partial。

连续尾轴可以按 AR 处理；ARA 每次搬连续 A0 小片并沿 R 遍历；交替多轴或非连续 view 通过真实 stride 的嵌套循环读取。不能将非邻接的归约轴直接相乘后按连续内存读取。若同一输出还要广播回输入（LayerNorm/softmax），先完成该组统计，再执行对应输出变换；分载场景允许重读输入以换取容量。

单核/单 owner 的 chunk 流程无全局同步，仅需搬入、计算、搬出的核内依赖。若原基线本来是跨核算法，则保留它已验证的 workspace、完成关系和合并者，不删掉 merge 阶段或用 PipeBarrier 替代全局协议。

## 容量、成本与不能省略的状态

令 L 为输入 chunk 元素数，V 为有效输出 lanes，s_in/s_acc 为字节；A_a 为按字节对齐，d 是输入队列实际份数，K 是独立计算区份数：

`B_UB=d*A_a(L*s_in)+K*A_a(L*s_acc)+B_state(V)+B_out+T_api+B_other≤B_available`。

B_state 根据操作分别包含 sum，sum+count，value+index，(count,mean,M2)，或 softmax 的 max/sum 等状态。输出 count 与 padding 元素数分开记录，最后一个 chunk 用真实有效长度。T_api 应按当前形状、dtype、pattern 与是否复用源查询；一个最小合法 chunk 也放不下时使用现有框架基线，不强行 clamp L=1 继续。

流式单次 sum 必要输入量约 N*s_in，不产生跨核 workspace；centered TwoPass 分载统计可能需要两遍输入，softmax max/sum/output 重算可能需要三遍。若完整组留在 UB，几轮计算可只读一次 GM。回退的成本应记录实际读遍数和 launch；不能以来源固定 R 阈值、核数或临时区大小代替当前参数。

## 执行与数值骨架

```python
if proven_specialized_domain(metadata):
    return specialized_entry(metadata)
assert baseline_entry_is_validated_for(metadata)
for g in uniquely_owned_output_groups():
    state = initial_state_with_empty_flag(op)
    for coords in valid_reduction_chunks(g, true_strides):
        x = load_chunk(coords)  # 队列完成搬入
        partial = local_statistic(x, valid_count(coords), op)
        state = merge_in_original_order(state, partial, op)
    statistic = finalize_once(state, exact_count, correction, p)
    if needs_normalized_output(op):
        for coords in valid_reduction_chunks(g, true_strides):
            emit_owned_transform(coords, load_chunk(coords), statistic)
    else:
        write_owned_group(g, statistic)
```

只在已经证明的连续 FP32 sum 子域，xLocal 是就绪的 LocalTensor，tmpFloat/result 的分配与别名符合基础 ReduceSum，0<n≤INT32_MAX 时，局部归约可复用：

```cpp
// 基础 ReduceSum 四参数；n 是当前有效样本数，不是 padded 长度。
AscendC::ReduceSum<float>(resultLocal, xLocal, tmpFloat,
                         static_cast<int32_t>(n));
```

随后按原算法把该结果合并到同组状态。这个片段不覆盖 mean 的除数、NaN/max 的处理或完整队列；高级 Pattern::Reduce::RA 是不同重载，其 uint8_t 临时区、shape 和 srcInnerPad 要独立核验。

## 恢复专用路径的证据与验证

| 缺失项 | 需要的具体证据 |
| --- | --- |
| FullLoad 能力 | 按输入/累加 dtype 分开的对齐工作集、所有队列与 API 临时区 |
| 分块合并 | partial 状态、单位元、顺序、最后有效 count、finalize 一次 |
| 跨核同步 | 唯一 workspace 槽、producer 完成关系、唯一输出合并者 |
| 统计精度 | correction/epsilon/p 的规范、特殊值、误差与 count 范围 |
| 多轴/layout | 原始轴到输出组和每个输入坐标的可逆映射 |

最小验证覆盖 R=0/1、非整除 chunk、所有轴归约、非尾轴、多轴交替、最大 count、A0 尾片、特殊值、arg tie、方差小扰动与多核覆盖；不能只比最终 shape 或正常随机数。完整正确性通过后才在统一端到端协议下比较候选。

来源事实是 AR/ARA、分载与数值状态分类；通用真实 stride 基线、互斥分派与成本账为工程推导。A3/910C 与 950 的 API/dtype/临时区范围分别核实；未执行 NPU 性能验证，未把来源样例的硬件数字提升为通用边界。
