---
schema_version: aprof.knowledge-record/v1
id: planning.reduction.statistics
kind: template
version: 1.1.0
status: active
title: 方差、Norm 与 Softmax 数值状态
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/reduction/alg-welford.md
  original_path: ops/ascendc-tiling-design/references/reduction/alg-welford.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 74
  sha256: sha256:6c8e784dad546cb1caa07867596721b3d1c8ecc746396df5392054f44d84eb28
  excerpt_sha256: sha256:6c8e784dad546cb1caa07867596721b3d1c8ecc746396df5392054f44d84eb28
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/alg-welford.md
  original_path: ops/ascendc-tiling-design/references/reduction/alg-welford.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 74
  sha256: sha256:6c8e784dad546cb1caa07867596721b3d1c8ecc746396df5392054f44d84eb28
  excerpt_sha256: sha256:6c8e784dad546cb1caa07867596721b3d1c8ecc746396df5392054f44d84eb28
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/alg-dichotomy.md
  original_path: ops/ascendc-tiling-design/references/reduction/alg-dichotomy.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 56
  sha256: sha256:86baec84fd2fef8a4ac897755ed3181855c6e33973bc9368f51e89548b2a0737
  excerpt_sha256: sha256:86baec84fd2fef8a4ac897755ed3181855c6e33973bc9368f51e89548b2a0737
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/alg-group-reduce.md
  original_path: ops/ascendc-tiling-design/references/reduction/alg-group-reduce.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 101
  sha256: sha256:a093e609d217b38db7b739ff2f924e977d1b0abd6c5f18023623625cfebff5d5
  excerpt_sha256: sha256:a093e609d217b38db7b739ff2f924e977d1b0abd6c5f18023623625cfebff5d5
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/multi-output-buffer.md
  original_path: ops/ascendc-tiling-design/references/reduction/multi-output-buffer.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 115
  sha256: sha256:e9d2991c887971a49b9cec263cb50ec94d6a0b731daed3ff10488d0106fb6d88
  excerpt_sha256: sha256:e9d2991c887971a49b9cec263cb50ec94d6a0b731daed3ff10488d0106fb6d88
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/norm/layer_norm_v3/op_host/arch35/layer_norm_v3_regbase_two_pass_tiling.cpp
  original_path: norm/layer_norm_v3/op_host/arch35/layer_norm_v3_regbase_two_pass_tiling.cpp
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 23
  - 112
  sha256: sha256:44fdba38a6477aa00ce0694cead536be08394bbdd4128adb5b92c428c43416af
  excerpt_sha256: sha256:faca3f9ac2da908e3ea213b4586bdc50e0377b93aed66ef409adc4bdd24e2930
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/norm/layer_norm_v3/op_host/arch35/layer_norm_v3_welford_tiling.cpp
  original_path: norm/layer_norm_v3/op_host/arch35/layer_norm_v3_welford_tiling.cpp
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 25
  - 136
  sha256: sha256:f0e6bbcb0e6f4ac7fc98968d0148eaac663712d64c29ae78833fb9aff194f9e6
  excerpt_sha256: sha256:f1e2243ed4c7734c1ea9a00e303d9e54cb9c184e3cadfe9343110093884e954f
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/norm/lp_norm_v2/op_kernel/arch35/lp_norm_v2_dag.h
  original_path: norm/lp_norm_v2/op_kernel/arch35/lp_norm_v2_dag.h
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 1
  - 492
  sha256: sha256:a0a7f6aff3c150a4d49b7d1f415d53f450537064c2439069bdfbc734b3ff7692
  excerpt_sha256: sha256:a0a7f6aff3c150a4d49b7d1f415d53f450537064c2439069bdfbc734b3ff7692
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/norm/lp_norm_v2/op_api/aclnn_linalg_vector_norm.cpp
  original_path: norm/lp_norm_v2/op_api/aclnn_linalg_vector_norm.cpp
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 177
  - 267
  sha256: sha256:91c629cbe324e4f1c7c393952fff6d0aa6e3488b5ef80f5bc2bd0230f83909b7
  excerpt_sha256: sha256:eebae40979f9d31c7e05b04b1c2287474a7db61561c6c5b328621ff6d7d7d6fb
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/activation/softmax_v2/op_kernel/arch35/softmax_v2_ar_recompute.h
  original_path: activation/softmax_v2/op_kernel/arch35/softmax_v2_ar_recompute.h
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 115
  - 263
  sha256: sha256:cd5a4eae89a871904ab27e83727930b12f59ff939a5a06810c9701f34a907524
  excerpt_sha256: sha256:a173c1752cb85a9d75844500a058d294f7760085ef1b760b4bc140323e6521ba
learning: {}
tags:
- numerical-state
- reduction
seed_reason: 固定开源修订审读并补全中文算法、所有权、字节容量与选择边界；保留原 ID/主归属/数值合同，未做 NPU 性能验证。
parent: planning.reduction
references:
- planning.reduction.fullload
- planning.reduction.split
- planning.reduction.fallback
evidence_status: source_reviewed_not_benchmarked
---

# 方差、Norm 与 Softmax 数值状态

## 适用域与算法选择

输入沿已确认的归约轴分成输出组，每组 R 个有效样本；AR/ARA 仅决定访问布局，统计量的数学语义必须独立定义。先确定输出是 mean/variance/std、L_p norm、LayerNorm/RMSNorm 还是 softmax；明确 correction、epsilon 的位置、p 的允许值、累加/输出 dtype、特殊值与允许误差。输出变换相似不代表同一统计状态能互换。

一个完整输出组能驻留 UB 时，TwoPass 可在已加载输入上先求 mean，再求 centered square 的和，无需两遍 GM。若需要分块且 mean 与 M2 相关，Welford 可以用一遍输入统计并可合并 partial。sum(x²)/n−mean² 会有大均值小方差抵消，除非精度合同已证明满足，不作为 Welford/centered TwoPass 的等价快捷替换。Welford 也有舍入误差，其稳定性不是无条件的精度保证。

固定 ops-nn 的 arch35 LayerNorm 分别实现 TwoPass 容量判定和 Welford tile 预算，并查询对应高级 API 临时区；这证明这些是实际候选路径，不证明它们的常数/指令可直接移植到 910C/A3。

## Welford：更新、合并与唯一 finalization

每个输出 lane 保存 `(n,μ,M2)`，其中 n 是有效样本数，μ 为均值，`M2=Σ(x−μ)²`。空状态 n=0。读入一个有效 x：

`n'=n+1; δ1=x−μ; μ'=μ+δ1/n'; δ2=x−μ'; M2'=M2+δ1*δ2`。

第二个偏差必须使用新均值，不可写成 δ1²。合并两个非空状态 a,b 时：

`n=na+nb; δ=μb−μa; μ=μa+δ*(nb/n); M2=M2a+M2b+δ²*(na*nb/n)`。

若任一状态 count=0，直接返回另一状态，避免空段除以 0。n 用足够范围的整数保存；比例计算时选择合同规定的计算 dtype，并避免整数 na*nb 在转换前溢出。FP32 比例转换在很大 n 时不再精确，不能把 count 本身存 float 后假设任意 R 都能逐一加 1。

所有段完成后由唯一 owner finalize：`variance=M2/(n−correction)`，std 再开方。n≤correction、空组、M2 因舍入略负时的处理由 oracle 决定；不能擅自截为 0 或给分母加 epsilon。LayerNorm 常用 `rsqrt(var+eps)`，RMSNorm 常用 `rsqrt(mean(x²)+eps)`；norm 的 clamp 与它们不同。

同组每个状态只有一个核内 owner；跨核使用 `(group,split)` 独立槽，merge owner 按固定次序合并后只写一次。不可由每段分别减 correction、开平方，再平均结果。来源“每 8 个 chunk 合并”是其启发式分组，不是数值正确性条件；分组数和合并树纳入精度验证。

## Norm：p 特例、变换与范围

| p | 分段统计与合并 | 最后还原 |
| --- | --- | --- |
| 0 | 精确计数 x≠0，按合同定义 NaN 等 | 计数转输出 dtype；不是逐元素 x^0 |
| 1 | Σabs(x)，partial 求和 | 原统计值 |
| 2 | Σ(x*x)，partial 求和 | sqrt 一次 |
| 3 | Σabs(x)^3，partial 求和 | 1/3 次幂一次 |
| +∞ / −∞ | max/min(abs(x)) | 极值 |
| 其他允许的有限 p | Σabs(x)^p，partial 求和 | 1/p 次幂一次 |

表中公式的直接计算可能溢出/下溢；p<0、x=0、NaN/Inf 和空组需遵循算子规范。p 特化必须按实际属性判定，不得把接近 1/2/3 的任意 float 无声当相等。若用 scaled sum-of-squares 等更稳的替代法，需要单独证明语义和误差，不能仅凭代数等价跨过原合同。

固定 ops-nn `lp_norm_v2` DAG 有独立的 NonZero/Abs/Square/Cube/Inf 路径，并在后置链使用 `max(norm,eps)`；其 LinalgVectorNorm API 路径传 epsilon=0，不能由此给任意 norm 添加一个正 epsilon。该 API 的固定实现中 regbase 支持更广 p，非 regbase 的检查只列 {0,1,2,3,±∞}；这是该实现的接口限制，不是数学定义或所有 A3 算子的普遍限制。

## Softmax：统计与输出必须分离

有限非空输入组的稳定写法：`m=max(x)`、`l=Σexp(x−m)`、`y_i=exp(x_i−m)/l`。FullLoad 可保留 x 或 exp(x−m)，在 UB 完成多个步骤后输出；分载的直接重算路径通常先扫描 max，再扫描 exp-sum，再扫描输入生成 y，必要输入交通约 `3*N*s_in` 加输出字节。固定 ops-nn arch35 AR recompute kernel 实际采用这三个阶段，并有分层求和缓存。

若需要跨段融合统计，可将每段写成 `(m_s,l_s)`，对两个有限非空段合并：

`m=max(ma,mb); l=la*exp(ma−m)+lb*exp(mb−m)`。

这是由稳定 softmax 定义推导的可合并状态，并非这里引用的 recompute kernel 已执行的路径。得到全组 m,l 后，还需再次读取原输入或保存的未归一化数据才能生成所有 y；不能把每段先 softmax 的输出直接拼接。空状态用显式 valid/count 标志；全 −∞、含 +∞、全 mask、NaN 使差分出现非有限值时，不能机械使用 `−∞−(−∞)`，应走明确的特殊值规则。

softmax 的输出拥有者可按输入输出 tile 分片，但统计必须先对同组完成合并；用执行流中独立 kernel 或已证明合法的全局完成协议建立依赖。核内 barrier 不能保证其他核的 m/l 已发布。

## 字节工作集、状态与重读成本

令 L 为一个 tile 的有效元素，V 为同时处理的输出 lanes；s_in/s_acc/s_out 为字节，d_in/d_out 为实际 buffer 份数，A_a 为按字节对齐。流式统计的通用账为：

`B_UB=d_in*A_a(L*s_in)+K_cast*A_a(L*s_acc)+B_states(V)+B_scratch(L,V)+d_out*A_a(L_out*s_out)+T_api+B_params ≤ B_available`。

Welford 若每个 lane 的 count 相同，可将 n 作为共享整数，mean/M2 两向量是必要状态；逐样本更新的 delta1/delta2/tmp 是额外工作区，不能只按“两输出”计容量。若 count 按 lane 不同则另分配 V 个 count。多输出、gamma/beta、残差、量化状态均分别计入，不随主输入 chunk 自动消失。

跨核 S 份 partial、P 个输出组时，workspace 为 `P*S*A_aws(serialized_state_bytes)`；Welford 的序列化至少含两份累加值及精确 count，softmax 至少 m/l 和空状态标志。二阶段写读流量约 2W。TwoPass 分载统计需要约两遍输入，Welford 统计一遍；需要归一化输出时还要额外读输入，不能把“一遍统计”写成“整个 LayerNorm 一遍 GM”。

比较候选时列完整读遍数、保存中间数据的 workspace、Exp/Sqrt/Pow 调用数、状态合并量和 launch。FullLoad 的 TwoPass 虽两次向量归约却可能只有一次 GM；因此不能仅比较算法名称或扫描次数。

## 有界 Ascend C：ARA 逐样本 Welford 更新

用于 `[rCount,vAlign]` 的 FP32 计算区，rCount>0，vValid>0；mean/M2/delta1/delta2/tmp 为容量足够、互不覆盖的 `LocalTensor<float>`，mean/M2 初始化为 0，valid lanes 的 count 在进入片段前为 n。每个 r 是 V 个独立输出的一次新样本；该片段不是 AR 向量的直接横向 Welford。

```cpp
for (uint32_t r = 0; r < rCount; ++r) {
    ++n; // 用经过范围证明的整数；转 FP32 形成 invN 的精度另行验证。
    const float invN = 1.0f / static_cast<float>(n);
    AscendC::Sub(delta1, xFp32[r * vAlign], mean, vValid);
    AscendC::Muls(tmp, delta1, invN, vValid);
    AscendC::Add(mean, mean, tmp, vValid);
    AscendC::Sub(delta2, xFp32[r * vAlign], mean, vValid);
    AscendC::Mul(tmp, delta1, delta2, vValid);
    AscendC::Add(M2, M2, tmp, vValid);
}
```

该标量转换是否受目标编译器限制须在 C3 核验；不支持时从 host/tiling 或已核验的标量转换路径提供 invN，保持相同 n 的语义。输入队列需在开始前 DeQue，输出与跨流水依赖由工程管理；不能看到局部片段顺序就省略异步搬入完成关系。

## 验证、回退与来源证据

方差覆盖常量输入、大均值小扰动、n=0/1、correction 边界、不同 chunk/合并树；norm 覆盖所有允许 p、负数、零、接近但不等于特化 p、空组及溢出；softmax 覆盖极大/极小差值、全相等、全 −∞、+∞/NaN、mask 全空，以及不同分片的总和与逐元素输出。所有验证均对照当前 oracle 的 dtype/舍入/特殊值规则。

若数值/容量/平台证据缺失，回退已验证的原始统计实现并保留实际 entry/key；不能以性能动机减少 count 精度、删除 correction 或改变 epsilon 位置。cannbot 提供 Welford/Group Reduce 算法事实，ops-nn 提供 arch35 实现候选；softmax 状态合并与完整字节模型是显式工程推导。未执行 NPU 正确性或性能验证；A3/910C 与 950 能力、临时区查询及指令必须分别核实。

> 文档适配说明：本页已规范代码文字格式；来源和历史回放使用[保留的证据原文](../../../../../../sources/document-originals/19c5b1113ee43393664c25dd4684b3763f6764e409b013cfe69be05563503e38.txt)。
