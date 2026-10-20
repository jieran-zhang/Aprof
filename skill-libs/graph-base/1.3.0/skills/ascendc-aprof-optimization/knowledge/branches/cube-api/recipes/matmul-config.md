---
schema_version: aprof.knowledge-record/v1
id: implementation.cube-api.matmul_config
kind: recipe
version: 1.0.0
status: active
title: Matmul API 模板与常量 Tiling 配置
scope:
  platforms:
  - Ascend 910B
  - Ascend 910C
  - Ascend 950
  - dav-2201
  - dav-3510
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/adv_api/cube_compute/Matmul_Kernel/MatmulConfig.md
  original_path: docs/zh/api/SIMD-API/adv_api/cube_compute/Matmul_Kernel/MatmulConfig.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 80
  sha256: sha256:8798d6fc3a8185f90abc655bed4a32803b13a7fe32594ab3ec741f82c975d0e7
  excerpt_sha256: sha256:8798d6fc3a8185f90abc655bed4a32803b13a7fe32594ab3ec741f82c975d0e7
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/adv_api/cube_compute/Matmul_Kernel/GetMMConfig.md
  original_path: docs/zh/api/SIMD-API/adv_api/cube_compute/Matmul_Kernel/GetMMConfig.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 147
  sha256: sha256:a4abf361c4081d4d160fd03a2a25e75ffd50b9d06ba06ecfbf5f9fac28850b8e
  excerpt_sha256: sha256:a4abf361c4081d4d160fd03a2a25e75ffd50b9d06ba06ecfbf5f9fac28850b8e
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/adv_api/cube_compute/Matmul_Kernel/GetMatmulApiTiling.md
  original_path: docs/zh/api/SIMD-API/adv_api/cube_compute/Matmul_Kernel/GetMatmulApiTiling.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 87
  sha256: sha256:b87c52b6b8d9cac9fd72b89f80b7fe04f96d78ee79e4d1d5151e82d3ea495fea
  excerpt_sha256: sha256:b87c52b6b8d9cac9fd72b89f80b7fe04f96d78ee79e4d1d5151e82d3ea495fea
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/04_advanced_api/00_matmul/matmul_constant_tiling/matmul_constant_tiling.asc
  original_path: examples/01_simd_cpp_api/04_advanced_api/00_matmul/matmul_constant_tiling/matmul_constant_tiling.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 314
  sha256: sha256:0925f3a2284391c1b090f6f0f0bb75d6afe75e93d8cc013cecd0675ad3e9d8a2
  excerpt_sha256: sha256:0925f3a2284391c1b090f6f0f0bb75d6afe75e93d8cc013cecd0675ad3e9d8a2
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/04_advanced_api/00_matmul/matmul_constant_tiling/README.md
  original_path: examples/01_simd_cpp_api/04_advanced_api/00_matmul/matmul_constant_tiling/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 139
  sha256: sha256:12739dc21b10b733702ed9e6fae8d5c888d156ccb492ca7593387ad606c2f194
  excerpt_sha256: sha256:12739dc21b10b733702ed9e6fae8d5c888d156ccb492ca7593387ad606c2f194
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/01_matrix_compute/matmul_high_performance/README.md
  original_path: examples/01_simd_cpp_api/05_best_practices/01_matrix_compute/matmul_high_performance/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 604
  sha256: sha256:0c92eaf287a50d35b217d4fd2b50d84a787fa9c685cd99cb2ccfbb4d9ae74ac6
  excerpt_sha256: sha256:0c92eaf287a50d35b217d4fd2b50d84a787fa9c685cd99cb2ccfbb4d9ae74ac6
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/01_matrix_compute/matmul_basic_api_high_performance/README.md
  original_path: examples/01_simd_cpp_api/05_best_practices/01_matrix_compute/matmul_basic_api_high_performance/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 532
  sha256: sha256:fe8df2c2792de115f12584e3444941930d39da00174759871ab98e4f48779c3d
  excerpt_sha256: sha256:fe8df2c2792de115f12584e3444941930d39da00174759871ab98e4f48779c3d
learning: {}
tags:
- constant-tiling
- matmul-api
- norm-mdl
- static-dynamic
seed_reason: 审读五个固定开源修订中的直接来源，以中文提炼实现契约；保留旧 ID 含义，不承诺目标 SDK 编译结果或 NPU 性能收益。
parent: implementation.cube-api
references:
- implementation.cube-api.fixpipe_output
- implementation.cube-api.mmad_accumulation
- implementation.precision-boundaries.numeric
- implementation.scalar-control.constant_lifetime
evidence_status: source_reviewed_not_benchmarked
---

# Matmul API 模板与常量 Tiling 配置

## 原理与进入条件

高阶 Matmul API 承担搬运、基本块迭代与结果输出；模板配置决定哪些功能代码存在、哪些参数在编译期确定。Norm 较早发出单基本块 MTE1；MDL 将多个基本块合为 GM→L1 大包，减少发射但可能增加首包等待与占用。常量 Tiling 进一步减少 Scalar 参数计算。候选必须从 C2 已确定的单核 shape、基本块、dtype/format/transpose、bias、输出位置和资源预算出发；不能借配置模板修改任务所有权、核数或 Split-K 合并方式。

适用于目标证据显示 Matmul 头开销、Scalar 参数或细碎搬运值得优化的场景。稳定 shape 或少量常用 shape 可比较全量常量化；动态 shape 但 base 固定可部分常量化；shape/分支跨度大则保留动态 tiling。常量化表达编译知识，不等于删去尾块或把运行时实际值硬写成某个样例值。

## 配置步骤与静动态契约

1. 固定 A/B/C/Bias 的 MatmulType、GM/L1/UB 位置、ND/NZ、transpose、累加类型和原数学语义。Host 计算出的 `baseM/N/K`、`singleCoreM/N/K` 与 Kernel 配置必须一致；别把全局 M/N/K 当单核 shape。
2. 先只比较 Norm 与 C2 允许的 MDL。Norm 搬一个基本块即可推进 MTE1；MDL 大包可摊薄 MTE2 发射，适合较大 shape，但 L1 深度与 `stepKa/stepKb/stepM/stepN` 须按 dtype 和 padding 重新预算。K 全载、M/N 双缓冲等前置不满足时不启用 MDL preload；不把所有开关同时打开。
3. 按 API 文档选择常量化范围：仅 base 三元组为常量是部分常量化，singleCore 三元组保留默认 0，注册对象仍需运行时 tiling；base 与 singleCore 六个值都常量是全量常量化，普通 Matmul 可在规定情况下用空 Tiling 指针。Batch Matmul 即使全量常量化也不能把注册参数 Tiling 换成 nullptr。
4. 当常量配置表达运行时最大单核 shape 时，实际计算必须在支持边界内，原 shape 和 SetTail 仍需正确设置；可用 `SetSingleShape` 的语义以具体 SDK 为准。不把样例中的 MAX 值看作 API 自动保护或全输入支持证明。对于动态尾，保留尾配置；无尾 BasicBlock/SpecialBasicBlock 仅在全部被路由 shape 真正无尾时使用。
5. 可按实际调用关闭未用功能、限定 iterateMode；例如只调用 IterateAll 才能将其余 Iterate 代码裁剪。仍调用 SetTail/SetBias/End 的代码不能相应关闭 enable 开关；异步 End、消息与 workspace 需遵循当前 API，不为消 Scalar 删除资源释放与同步。
6. 一次只改变一个机制：动态 Norm、动态 MDL、常量 MDL、UnitFlag 分别留可编译候选。把参数变化和 C2 符合性写入 C3；若需要改变 tiling 方案或 reduction 顺序，返回重规划。

## 有上下文的常量配置

下例使用公共 `kernel_operator.h` 和 `lib/matmul_intf.h`，固定 half×half→float、GM ND、无 batch 的单核 128×128×128，base 为 64×64×64。数字只是解释模板参数的例子，必须已由 C2 与目标 Tiling API 证实，所有长度单位为元素；没有 donor 私有 helper。

```cpp
using A = AscendC::MatmulType<AscendC::TPosition::GM, CubeFormat::ND, half>;
using B = AscendC::MatmulType<AscendC::TPosition::GM, CubeFormat::ND, half>;
using C = AscendC::MatmulType<AscendC::TPosition::GM, CubeFormat::ND, float>;
using Bias = AscendC::MatmulType<AscendC::TPosition::GM, CubeFormat::ND, float>;
constexpr MatmulShapeParams shape{128, 128, 128, 64, 64, 64};
constexpr auto cfg = GetMMConfig<MatmulConfigMode::CONFIG_NORM>(shape);
constexpr auto staticTiling = AscendC::GetMatmulApiTiling<A, B, C, Bias>(cfg);
AscendC::Matmul<A, B, C, Bias, staticTiling> mm;
```

注册、设置 A/B、OrgShape/Tail、实际 bias、IterateAll 和 End 按工程原路径执行；这个片段只替换配置与对象定义。若将 `shape` 前三项设为 0 而只常量化后三项，必须保留 TCubeTiling 注册，不能照抄全量示例的 nullptr。目标可用 L1 不是 API 默认值时，向 `GetMatmulApiTiling` 传入实际可用字节数，和其他同时存活数据共同预算。

## 资源、数值与失败边界

记对齐后 base 为 `Mb/Nb/Kb`，输入字节 `a/b`、累加字节 `c`，最小 L0A/B/C 占用分别约 `MbKb×a`、`KbNb×b`、`MbNb×c`；双缓冲分别乘槽数，再计硬件格式 padding/对齐与 bias。L1 的 A/B 大包近似为 `depthA1×MbKb×a` 与 `depthB1×KbNb×b`，最终以实际 tiling/布局而非简单公式判容量。常量化有 `shape×dtype×feature` 特化膨胀和 ICache 代价；大包有首包延迟和 L1 占用代价；UnitFlag 改并行而不是提高单条 Mmad 算力。

精度保持原输入/累加/输出 dtype、bias 次数、scale 和舍入；切模板后浮点累加次序仍需全 oracle 验证，FP32 累加不是等价证明。覆盖无尾/各维尾、动态 shape 边界、transpose/bias、单核最大 shape、空维及 batch 旁路。常量与 runtime 不一致、尾部旧数据污染、未用功能误裁剪、workspace 未初始化、L1/L0 超限应回退动态模板。性能比较使用同样 case/计时协议，不转述来源样例加速比为目标收益。

来源事实：MatmulConfig、GetMMConfig、GetMatmulApiTiling 明确模板、支持与部分/全量边界；constant_tiling 与高阶 high_performance 样例展示具体调用；basic high_performance 提供 L0/L1 和常量循环实例。流程与资源模型为工程提炼。dav-2201 对应 A2/910B、A3/910C，示例要求 CANN≥9.0.0；dav-3510/950 示例要求≥9.1.0。A2/A3 常量化支持 Norm/MDL，不能从 950 的 IBShare 常量化或 3510 专属 API 推广；最终以安装 SDK 的逐项支持和编译为准，未做目标板验证。
