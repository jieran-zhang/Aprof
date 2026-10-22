---
schema_version: aprof.knowledge-record/v1
id: implementation.vector-api.compare_select_tail
kind: recipe
version: 1.0.0
status: active
title: Compare/Select 的整块比较、predicate 与有效尾部
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
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/compare_and_select/Compare.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/compare_and_select/Compare.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 357
  sha256: sha256:353264a38c342ca8b668d0400e48750461820fa743be89ba59d6824eb4764262
  excerpt_sha256: sha256:353264a38c342ca8b668d0400e48750461820fa743be89ba59d6824eb4764262
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/compare_and_select/Select.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/compare_and_select/Select.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 345
  sha256: sha256:615845595e9b6ca5d150548eb27e9e6fd9d0bb972ee1533f933ad6bea8d940b5
  excerpt_sha256: sha256:615845595e9b6ca5d150548eb27e9e6fd9d0bb972ee1533f933ad6bea8d940b5
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/impl/basic_api/dav_c220/kernel_operator_vec_cmp_impl.h
  original_path: impl/basic_api/dav_c220/kernel_operator_vec_cmp_impl.h
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 444
  sha256: sha256:cf6f865a3350eeca13b0dd1355c0275f0085d9e10beaaa8f6e71d1f894d2ac9f
  excerpt_sha256: sha256:cf6f865a3350eeca13b0dd1355c0275f0085d9e10beaaa8f6e71d1f894d2ac9f
- path: skills/ascendc-aprof-optimization/knowledge/sources/selection-v2-optimization/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/basic_arithmetic/Max.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/basic_arithmetic/Max.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 177
  sha256: sha256:3ef8936b5fe5025072d33fa4b79380cd04c73ffbc33786605cadd5dee8b49329
  excerpt_sha256: sha256:3ef8936b5fe5025072d33fa4b79380cd04c73ffbc33786605cadd5dee8b49329
learning: {}
tags:
- compare
- select
- predicate
- tail
- api-overload
seed_reason: 固定修订明确的 API 约束与源码审读；性能收益未测。
parent: implementation.vector-api
references:
- implementation.vector-api.batch
- implementation.precision-boundaries.numeric
- implementation.memory-transfer.strided-pad
- implementation.tiling-tail.valid-length
evidence_status: source_reviewed_not_benchmarked
---

# Compare/Select：把有效元素、执行粒度和 predicate 分开

## 适用范围与来源事实

适用于已由 C2 授权的逐元素条件选择、掩码过滤、广播比较、分段选择等实现；不是只在某个算子出错后才查的修复条目。条件表达式及两个分支已有明确数值语义，输入已在合法 UB 区间，不能借此更改算法、转换精度或跨核 owner。

固定 asc-devkit `d378849...` 的 Compare 文档明确：**Atlas A2/A3 的 count 重载只计算完整 256B 块，未对齐尾部不参与；该产品的高维 Compare mask 参数设置无效。** dav_c220 `CompareCompute` 实现用 `count*sizeof(T)/256` 向下取整得到 repeat 数，直接确认此实现事实。这是固定源码/文档结论，不是从一次硬件失败泛化。A2/A3 Compare 的 T 为 half/float（全部模式）或 int32（仅 EQ）；Select 的 T 为 half/float。不能把 int32 的任意大小比较、BF16 或 int64 选择硬塞入该组合。

950 文档给出的 mask、类型与内部实现不同，不能继承 A2/A3 的截尾规则，也不能把 950 的支持反推到 910C。以下 padding 骨架专用于已核对的 A2/A3 memory-vector half/float 路径；目标 SDK 仍需核对相同重载和 API 临时区。

## 合法构造与预算

设 `n>0` 为本段有效元素数，`s=sizeof(T)` 字节，`E=256/s` 元素，`c=ceil(n/E)*E` 元素。Compare 输入区必须各容纳 `c*s` 字节；输出 predicate 每元素占一 bit，至少容纳 `ceil(c/8)` 字节并按 32B 分配对齐，记 `M=AlignUp(ceil(c/8),32)`。Select 模式2连续消费每个 repeat 对应的不同 predicate；模式0反复使用第一组 `E` 个 bit，不能替代逐元素不同条件。

1. 把原有效数据装入输入 UB 的 `[0,n)`，只初始化额外会被 Compare 读取的 `[n,c)`；若 DMA 自带的 padding 已充分初始化此区且数值合法，可以避免重复初始化。DataCopyPad 的 32B 行对齐不自动补足 Compare 的 256B 执行域。
2. padding 的值必须是该 dtype 的已定义值且不产生无效地址；它不进入数学输出。输出有效区域只取 `[0,n)`。不用整 tile 清零来掩盖没有证明的访问范围。
3. 先完成 MTE2→V，再按 `c` 比较；Compare→Select 的 predicate 依赖完成后，以模式2按 `n` 选择；V→MTE3 完成后只搬 `n*s` 有效字节。
4. A2/A3 Select 模式1、2文档要求预留 **8KB UB API 临时区**，不能只计可见 tensor。950 的 count/显式 mask 重载不占该 8KB，而不传 mask 的高维重载占用，分别核验。

三个独立数据区且输出分配到 c 的简单预算为 `3*c*s + M + 8192` 字节，另加队列物理槽、对齐、其他 scratch。若 output 只分配到合法的 n 对齐范围则按实际缩小；不能未经 API alias 证明原地复用。输入、输出、predicate 槽数分别乘其物理份数，API 临时区按真实生命周期计，不能默认每片重复分配也不能漏计。

## 代码上下文

下例 `a,b,out` 为独立、32B对齐的 `LocalTensor<float>`；a/b/out容量各至少 `c` 元素，predicate为32B对齐的 `LocalTensor<uint8_t>`、容量至少M字节。调用前 a/b 的 `[0,n)` 已搬入，`[n,c)` 已合法初始化，MTE2→V 依赖已闭合；Host 证明整数计算不溢出且总 UB 含 8KB 预留。使用 `kernel_operator.h`，示意为原语义 `a_i>b_i ? a_i : b_i`：

```cpp
const uint32_t c = ((n + 63U) / 64U) * 64U; // FP32，元素；n>0且无溢出
AscendC::Compare(predicate, a, b, AscendC::CMPMODE::GT, c);
AscendC::PipeBarrier<PIPE_V>(); // 同一Vector管线的predicate写→读
AscendC::Select(out, predicate, a, b,
               AscendC::SELMODE::VSEL_TENSOR_TENSOR_MODE, n);
// 沿工程已有的 V→MTE3 完成协议，搬出 n*sizeof(float) 字节。
```

这段不是完整可直接启动 kernel。padding 初始化的尾址可能不满足相应 API 对齐，不能无条件写 `Duplicate(a[n],...,c-n)`；可用合法的对齐尾片重建、具体 API 的合法 mask 或逐元素初始化，再核对 Scalar→Vector/搬运依赖。选择成本更小的合法方式；不把保守初始化整片和 PIPE_ALL 永久固化为优化方案。

## 工作量、覆盖和代价怎样影响选择

原逐元素实现可能有 n 次标量比较、分支和地址处理；新方案是 `c/E` 个比较 repeat、有效 n 元素选择，以及至多 `2*(c-n)` 个输入 padding 写入、predicate 读写和必要依赖。逻辑量可用于比较，但不能相加为时间分数。短段 n 远小于 E 时补齐和准备代价可能显著；可与合法 Scalar 尾部、较大段组合或保持原路径比较，不能预设固定长度阈值。

若组合短行，需要保持每行有效长度、predicate位偏移、UB行pitch和输出owner。简单把带padding的多行扁平成有效 `R*n` 个元素会错读行尾；先由 C2 确定连续段/压紧布局。C3若为此改变任务所有权、搬运通路或超出tile自由度，返回C2。

此方法保留的是原条件选择语义，不自动等价于 Max/Min。重点检查 `a=NaN`、`b=NaN`、相等值、±0、±Inf及原oracle的比较规定。固定Max文档的数学名字不足以证明NaN/符号零选择与三元表达式完全一致。浮点比较语义未明确时补查原实现/API定义；不以放宽oracle解决。

## 无硬件审读与后续验证

静态检查 n=0（跳过调用）、1、E−1、E、E+1、多repeat和predicate跨32B边界的地址/容量；核验 Compare 生成的每个有效 bit 都被模式2正确消费，最后 padding 不进入输出。CPU模型可查索引和位映射，不能代替设备语义验证。来源支持合法试验方向，不提供收益保证；硬件尚未测时性能假设保持未测试，不否决已确认的 API 事实。
