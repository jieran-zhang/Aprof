---
schema_version: aprof.knowledge-record/v1
id: implementation.fusion-composition.cube_vector_epilogue
kind: recipe
version: 1.0.0
status: active
title: Cube 输出最终化后的 Vector epilogue 融合
scope:
  platforms:
  - dav-2201
  - dav-3510
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/00_introduction/03_fusion_operation/matmul_leakyrelu_advanced_api/matmul_leakyrelu_advanced_api.asc
  original_path: examples/01_simd_cpp_api/00_introduction/03_fusion_operation/matmul_leakyrelu_advanced_api/matmul_leakyrelu_advanced_api.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 24
  - 188
  sha256: sha256:50399b2e9cd19fe656777c2245c8e599f5b8ed159d16c6687caa9ca9b272a9fa
  excerpt_sha256: sha256:7f68ed19c2f76ff461be3265ef9d516961f93c50d15240f9e1b78a44c3032c0f
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/00_introduction/03_fusion_operation/matmul_leakyrelu_basic_api/matmul_leakyrelu_basic_api.asc
  original_path: examples/01_simd_cpp_api/00_introduction/03_fusion_operation/matmul_leakyrelu_basic_api/matmul_leakyrelu_basic_api.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 48
  - 195
  sha256: sha256:64086c964d5df9daf2dd0b81ba07b9352564ee06ede372423b58fea8a46b05e6
  excerpt_sha256: sha256:81c4437d75f7642307a9f02749f3af0761cf1b928cbf6df7899dee357c70ae13
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/mmad_gelu.asc
  original_path: examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/mmad_gelu.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 21
  - 613
  sha256: sha256:2fb232c81805420c88755d9bc41ea3561c3f4107946306425d1a43b48c31dd1d
  excerpt_sha256: sha256:a9dc9e4064f9198bc1a959600b5ec80e454c71f38ac2681b7cbe3e0a8d5d9728
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/README.md
  original_path: examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 31
  - 157
  sha256: sha256:f455633ee4affaed0ad5591c0acc1d47c2d7099c3bc25a8a87a3f2259783008e
  excerpt_sha256: sha256:cce28e26891a94ea183739fcf3345e32edd588c63c48de46dbc427b2878e36cd
- path: skills/ascendc-aprof-optimization/knowledge/sources/cann-samples/17c948bb961fc6a660e4fcab45f6bf217c9c6239/Samples/1_Features/hardware_features/cv_datapath/README.md
  original_path: Samples/1_Features/hardware_features/cv_datapath/README.md
  revision: 17c948bb961fc6a660e4fcab45f6bf217c9c6239
  lines:
  - 1
  - 200
  sha256: sha256:75fd879ecc4bf94dd4c72e40bdc1b1a343c250292430cb6c0b5c566144fd2283
  excerpt_sha256: sha256:7011f96f11ead5fed7515f5e1295dbe7c24de55cfeecbc6b60e67690409b3e5d
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md
  original_path: docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 28
  - 151
  sha256: sha256:69845e8fa794040e321959eaa57105a79cdf880c2d9460b7bf65a53f3c644827
  excerpt_sha256: sha256:02edbe3918b020be18c5b07b81c9bc18153e3f3ab7ba41a9962391c7173aa399
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md
  original_path: docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 28
  - 151
  sha256: sha256:fb6098e64301d056e53eb0f083dcc96083075fc8da78409492f905653c311f96
  excerpt_sha256: sha256:c5145c71c4361eef7d3e7a5597dfa8bc235c92153767ab8322ebee5109ed0b5d
learning: {}
tags:
- fusion
- source-reviewed
- not-benchmarked
seed_reason: 固定开源修订审读并以中文提炼；未做性能训练或硬件收益验证。
parent: implementation.fusion-composition
references:
- implementation.fusion-composition.vector_chain_residency
- implementation.pipeline-sync.pipeline
- implementation.pipeline-sync.slots
- implementation.buffer-lifetime.reuse
evidence_status: source_reviewed_not_benchmarked
---

# Cube 输出最终化后的 Vector epilogue 融合

## 原理、适用shape与计划边界

把矩阵乘的完整输出tile交给Vector，在同一kernel内执行bias、逐元素激活、scale或其它已批准epilogue，形成`Y=phi(AB+b)`。适合M/N可切独立输出块、K累加与必要归并能明确最终化、epilogue对每个最终元素局部的shape。若epilogue包含整行归约、跨tile归一化、多输出外部消费者或Split-K跨核partial，C2必须先定义更大region与最终所有者。

融合（一次kernel组合）、通路（结果经GM还是UB）、排程（C(t+1)与V(t)能否重叠）是三项独立选择。dav-2201的实用基线是源码明确支持的GM中转；它仍是CV融合。950直通路径只作独立能力分支，不能成为910C实施先决条件。

C2冻结融合区间、matmul切分、C:V配比、layout、累加/中间/输出dtype、bias施加位置、K归并所有者、GM/UB通路及buffer额度。C3落实允许范围内的Matmul API调用、ready/free、UB epilogue、tail和搬出。如果希望改变核配比、增加环形workspace、从GM改直通或将epilogue跨越原region，返回C2。

## 不可越过的全K最终化

设`C_partial(r)=Σ_{k∈Kr} A[:,k]B[k,:]`，最终`C=Σ_r C_partial(r)`；非线性通常满足`phi(Σ_r partial_r) != Σ_r phi(partial_r)`。bias只能按既定语义加一次，不能每个K块都加。分K局部累加、分核partial、量化反标定或跨核归并未结束时，不发布为epilogue输入。UnitFlag、Mmad完成一次或Fixpipe可搬出，不单独证明逻辑全K已最终化。

S1高级API样例设`M=512,N=128,K=128`，固定`baseM=128,baseN=64,baseK=128`，两个AIV逻辑核按N分片，每个逻辑核四次Iterate；这是一个完整K基础块例。推广到更大K时需证明每个GetTensorC拿到的是该输出tile完成全K后的值；Split-K则要等原计划的最终归并。不能沿用“四次Iterate”或仅沿M写回的offset用于其它tiling。

S2基础API样例在Fixpipe时float→half，随后LeakyRelu在half上执行；S1则是float结果加float bias后做float LeakyRelu。两者展示不同实现层次与通路，不是数值上可无条件互换的两个模板。

## 生产者、字节与生命周期

令输出tile为m×n、累加类型eAcc字节，Vector分片有v个且每片行数m_v；`B_C=align(m*n*eAcc,a)`，每个AIV的显式UB预算至少包括`dIn*align(m_v*n*eMid,aIn)+dOut*align(m_v*n*eOut,aOut)+scratch+API预留`。Matmul高级API内部UB/系统workspace另计，Host tiling必须为epilogue预留容量。

| 对象 | 生产者 | 消费者 | 发布时刻 | 回收/复用时刻 |
|---|---|---|---|---|
| L0C累加tile | Cube所有K块 | Fixpipe | 全K完成且M→FIX依赖满足 | Fixpipe读完 |
| GM中间tile | Fixpipe | 对应两个AIV的MTE2 | FIX完成后的CrossCore ready | 所有AIV搬入完成后才可覆盖 |
| AIV输入UB | MTE2或Matmul API | Vector epilogue | MTE2→V/输入队列ready | Vector最后读完成 |
| AIV输出UB | Vector | MTE3 | V→MTE3/输出队列ready | MTE3读完 |
| 最终GM tile | MTE3 | 下游kernel | 该tile完整输出完成 | 按外部图生命周期 |

Scenario1若将GM中间值写到最终输出同一地址，必须证明外部消费者不会在激活前读取，且C/V分片互不覆盖；否则用单独中间区。独立中间区若为全矩阵，至少`M*N*eMid`；若C2批准每逻辑core深d的环形tile区，至少`logicalCores*d*align(m*n*eMid,a)`，另需free回传。不能仅把全矩阵地址取模就宣称可缩workspace。

经GM中转的一次融合仍有Fixpipe写中间、MTE2读中间、MTE3写最终值。相对两次launch可能省启动及获得更细粒度调度，并不自动省掉中间的`2*m*n*eMid`字节；只有合法改变通路才可计为消除该往返。高级API的C位置为VECIN只证明调用方拿到Vector可读LocalTensor，不独立证明底层没有GM中转。

## 两条实施路线

**高级Matmul API路线（优先复用现有工程）**：按SDK能力设置A/B/C/Bias类型与TCubeTiling，注册Matmul对象，预留epilogue UB。每次完整输出tile用GetTensorC交给VECIN队列，执行epilogue后从VECOUT搬出。API内部的跨核调度与workspace不要自行覆盖或重复分配事件。

下面按S1截取核心真实API并补齐变量契约：`pipe`为本entry的TPipe；`tiling`为Host生成且C类型VECIN/float、Bias GM/float的TCubeTiling；aGm/bGm/biasGm已绑定当前AIV逻辑核的合法分片。片段位于mix entry内，`GetSysWorkSpacePtr()`是SDK系统workspace入口；系统workspace由Host按目标平台查询分配，不是可省略的repo私有helper。

```cpp
#include "kernel_operator.h"
#include "lib/matmul_intf.h"
using namespace AscendC;
matmul::Matmul<
    matmul::MatmulType<TPosition::GM, CubeFormat::ND, half>,
    matmul::MatmulType<TPosition::GM, CubeFormat::ND, half>,
    matmul::MatmulType<TPosition::VECIN, CubeFormat::ND, float>,
    matmul::MatmulType<TPosition::GM, CubeFormat::ND, float>> mm;
// 上下文变量：TPipe pipe; TCubeTiling tiling;
// GlobalTensor<half> aGm,bGm; GlobalTensor<float> biasGm,cGm;
// 该搬出片段限定S1固定shape：baseN==singleCoreN，M/N均无尾块；
// cGm已经偏移到当前N方向逻辑核的首列，后续只沿M遍历。
REGIST_MATMUL_OBJ(&pipe, GetSysWorkSpacePtr(), mm, &tiling);
TQue<TPosition::VECIN,1> cQ;
TQue<TPosition::VECOUT,1> yQ;
const uint32_t tileElems = tiling.baseM * tiling.baseN;
pipe.InitBuffer(cQ,1,tileElems*sizeof(float));
pipe.InitBuffer(yQ,1,tileElems*sizeof(float));
uint64_t computeRound = 0;
mm.SetTensorA(aGm);
mm.SetTensorB(bGm);
mm.SetBias(biasGm); // Host tiling同时EnableBias(true)，不要再重复加bias。
while (mm.template Iterate<true>()) {
    auto c = cQ.AllocTensor<float>();
    mm.template GetTensorC<true>(c,false,true);
    cQ.EnQue(c);
    c = cQ.DeQue<float>();
    auto y = yQ.AllocTensor<float>();
    LeakyRelu(y,c,0.001f,tileElems);
    yQ.EnQue(y);
    cQ.FreeTensor(c);
    y = yQ.DeQue<float>();
    const uint64_t cOffset = computeRound * tiling.baseM * tiling.N;
    DataCopy(cGm[cOffset],y,DataCopyParams{
        static_cast<uint16_t>(tiling.baseM),
        static_cast<uint16_t>(tiling.baseN*sizeof(float)/32),0,
        static_cast<uint16_t>((tiling.N-tiling.baseN)*sizeof(float)/32)});
    yQ.FreeTensor(y);
    ++computeRound;
}
mm.End();
```

这是API上下文片段，不是独立可构建算子；实际搬出代码仅限S1固定shape及32B对齐行宽。其它tiling的M/N坐标、validM/validN、stride与tail须重新实现，不可沿用该computeRound公式。没有repo私有header前置依赖。若原工程已有Matmul服务，应在其允许接口后接epilogue，不能再注册一套争用系统资源的对象。

**基础API GM路线（dav-2201独立可行）**：Cube先完成所有K累加，M→FIX后Fixpipe写GM；AIC在PIPE_FIX上发布ready，AIV等待后DataCopyPad到本核UB，MTE2→V后激活，V→MTE3后写回。双AIV按C2指定的行片分工；S2用AIV blockIdx/2映射回AIC输出区，用blockIdx%2确定半块，S1的高级API却按AIV逻辑核N分片，不能混用两套ID口径。

```cpp
#include "kernel_operator.h"
// flagId由工程统一分配，须避开Matmul等API内部占用；生产者已发合法Fixpipe。
if ASCEND_IS_AIC {
    AscendC::CrossCoreSetFlag<0x2, PIPE_FIX>(flagId);
}
if ASCEND_IS_AIV {
    AscendC::CrossCoreWaitFlag<0x2>(flagId);
    // 此后发本AIV独占行片的GM->UB，等待MTE2_V，再做激活及V_MTE3搬出。
}
```

这个单向ready只够描述本tile可读；若C2选择复用GM环形槽，还需AIV消费者完成后的反向free协议，两个AIV均参与时AIC不可只等一方。S6官方文档指出2201的Wait会阻塞后续全部流水，放置过早会损失可并行发射机会。

## 950特定扩展及SDK门禁

S3在`__NPU_ARCH__==2201`处`static_assert(scenarioNum==1)`；其2201路线是L0C→GM→UB，并用MemBase GELU。`__NPU_ARCH__==3510`才实现Scenario2的L0C→UB、`FixpipeParamsArch3510`、`dualDstCtl=0b01`及RegBase。工程可依照相同的编译期guard隔离能力；不能在2201编译路径里保留3510类型并希望运行时if避开。

S5 cann-samples cv_datapath虽然提供separate/GM/UB三种对照，但README明示仅950PR/950DT、dav-3510、CANN>=9.1.0。它可用于理解融合/通路的区别，不能用作910C编译或性能证据。主线在不读取、不安装该950样例的情况下，仍可按S1/S2/S3的2201路径实施。

## 失败、验证与回退

重点覆盖K>baseK、K尾块、Split-K若存在、bias广播、M/N尾块、双AIV的奇数M分工、多次tile回卷及特殊值。检查非线性恰执行一次、bias恰施加一次、数值转换发生在原契约位置。更换LeakyRelu为GELU近似属于语义变化，不是epilogue接口替换；S3的近似公式不得替代任意GELU要求。

若只单tile正确而多tile失败，核对GM/UB复用和跨核free；若结果整体偏置，检查bias重复或K未完成；若无提速，区分launch减少、GM流量与真实C/V重叠的贡献。回退到原GM中转、串行epilogue或分离kernel基线；跨region或通路变化交回C2。

## 固定来源与证据级别

- S1：[examples/01_simd_cpp_api/00_introduction/03_fusion_operation/matmul_leakyrelu_advanced_api/matmul_leakyrelu_advanced_api.asc](../../../sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/00_introduction/03_fusion_operation/matmul_leakyrelu_advanced_api/matmul_leakyrelu_advanced_api.asc)，行 24–188；修订 `d378849769f9ee610af9d0ac38db2b3b6bed3209`。
- S2：[examples/01_simd_cpp_api/00_introduction/03_fusion_operation/matmul_leakyrelu_basic_api/matmul_leakyrelu_basic_api.asc](../../../sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/00_introduction/03_fusion_operation/matmul_leakyrelu_basic_api/matmul_leakyrelu_basic_api.asc)，行 48–195；修订 `d378849769f9ee610af9d0ac38db2b3b6bed3209`。
- S3：[examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/mmad_gelu.asc](../../../sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/mmad_gelu.asc)，行 21–613；修订 `d378849769f9ee610af9d0ac38db2b3b6bed3209`。
- S4：[examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/README.md](../../../sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/README.md)，行 31–157；修订 `d378849769f9ee610af9d0ac38db2b3b6bed3209`。
- S5：[Samples/1_Features/hardware_features/cv_datapath/README.md](../../../sources/cann-samples/17c948bb961fc6a660e4fcab45f6bf217c9c6239/Samples/1_Features/hardware_features/cv_datapath/README.md)，行 1–200；修订 `17c948bb961fc6a660e4fcab45f6bf217c9c6239`。
- S6：[docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md](../../../sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreWaitFlag_ISASI.md)，行 28–151；修订 `d378849769f9ee610af9d0ac38db2b3b6bed3209`。
- S7：[docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md](../../../sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/inter_core_sync/CrossCoreSetFlag_ISASI.md)，行 28–151；修订 `d378849769f9ee610af9d0ac38db2b3b6bed3209`。

来源事实、本文推导与待验证项在正文分别标注。冻结源码及仓库许可证随包保存；本次仅完成审读，未在目标 SDK 构建，未运行 NPU 正确性或性能测量。源码存在不代表当前 shape 已分派到该路径，任何收益都须由当前候选的完整正确性、Task Duration 与针对性 timeline 证明。
