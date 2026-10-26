---
schema_version: aprof.knowledge-record/v1
id: implementation.scalar-control.constant_lifetime
kind: recipe
version: 1.0.0
status: active
title: 编译期常量、对象别名与标量存活期
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
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/scalar/coding_principles.md
  original_path: ops/ascendc-performance-best-practices/references/common/scalar/coding_principles.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 478
  sha256: sha256:a387544bac3f38ad940fae2930e75c9f7cda45c8e25324f4cd864bee1ce4827c
  excerpt_sha256: sha256:a387544bac3f38ad940fae2930e75c9f7cda45c8e25324f4cd864bee1ce4827c
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/flash_attention/arch22/scalar_overhead_design.md
  original_path: ops/ascendc-performance-best-practices/references/flash_attention/arch22/scalar_overhead_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 119
  sha256: sha256:5980d08caaca929c00df820df4ef855e52d8574db112d97f57078e9131ed09a1
  excerpt_sha256: sha256:5980d08caaca929c00df820df4ef855e52d8574db112d97f57078e9131ed09a1
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/data_structures/LocalTensor/LocalTensor_constructor.md
  original_path: docs/zh/api/SIMD-API/basic_api/data_structures/LocalTensor/LocalTensor_constructor.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 296
  sha256: sha256:103ec2d4324f59620a49df8b4ddaec36c81552c1a5a850233177ecec77a34946
  excerpt_sha256: sha256:103ec2d4324f59620a49df8b4ddaec36c81552c1a5a850233177ecec77a34946
learning: {}
tags:
- alias-analysis
- constexpr
- liveness
- static-layout
seed_reason: 审读五个固定开源修订中的直接来源，以中文提炼实现契约；保留旧 ID 含义，不承诺目标 SDK 编译结果或 NPU 性能收益。
parent: implementation.scalar-control
references:
- implementation.buffer-lifetime.reuse
- implementation.precision-boundaries.bounds
- implementation.scalar-control.hot_loop_address
- implementation.scalar-control.tilingdata_access
evidence_status: source_reviewed_not_benchmarked
---

# 编译期常量、对象别名与标量存活期

## 原理与边界

给编译器明确的常量和值生命周期，可减少参数 load、对象初始化、地址逃逸和 spill。`const` 只说明不能经该名称修改，并不必然把运行时 tiling 变成编译期常量；可在编译期确定的有限配置才适合 `constexpr` 或模板参数。反过来，编译器有时也能传播普通 `const`，因此必须看最终汇编，而非只根据 C++ 写法认定收益。

C2 已确定实际 tile 与功能分支，本条只优化其参数表达与对象作用域。未知动态 shape、运行时 stride、动态 TQue 或可变 feature 的 buffer 不允许硬编码。需要修改 tiling ABI、删掉 queue/event、跨核重新分工时回到对应规划，不借“常量化”越界。

## 改写顺序与资源公式

1. 按值分类：编译期固定值、launch 固定值、tile 变化值。第一类可进入小规模模板或 `constexpr`；第二类用局部 `const`；第三类在最短使用范围内定义。不要把一个 case 测到的 shape 当所有输入的编译常量。
2. 将仅当前函数频繁使用的成员转局部值；避免把这些值的地址交给可修改它们的函数。不能通过错误 `restrict`、强制 const 或删掉真实别名制造“无别名”假设；必须传地址的合法 API 保留其契约。
3. 对象在热循环中反复构造且其 buffer 身份不变时，可外提 tensor 视图；若每轮 `AllocTensor/FreeTensor` 管理不同队列槽，不能把循环外视图绑定到某个旧槽。复用对象时仍按每轮更新其真实偏移和有效 size。
4. 临时值在首次需要时定义，在最后使用后结束作用域。缓存热点与缩短存活期共同权衡：把所有字段都外提到入口可能增加 spill。对象含动态索引数组时，可局部分离不变参数与事件/索引状态，保持索引语义；不必为了编译器假设重写公开 ABI 或全部类层次。
5. 模板特化只保留 C2 已允许且常用的有限组合，动态路径保留通用实现。若有 `a` 个 tile、`b` 个 dtype、`c` 个 feature 选择，最坏编译体数量为 `a×b×c`，并可能增加 binary/ICache 和编译时间；减少 Scalar 指令不保证 Task 时间下降。

定义 `live(t)` 为时刻 t 仍可能再用的标量/对象集合，峰值寄存器压力约随 `max_t sum(registerNeed(x), x∈live(t))` 增长，这只是估算，真实分配以报告为准。一次外提省去 `(L−1)` 次构造，但延长对象整个循环的活跃范围；一组临时变量若本来不跨阶段使用，就不应为省几条初始化强行驻留。

## 编译期值与运行时值的上下文

```cpp
template<uint32_t TileElements>
__aicore__ inline uint64_t TileOffset(uint64_t tileIndex,
                                    uint64_t baseElements) {
    static_assert(TileElements > 0, "nonempty tile");
    constexpr uint32_t tileElements = TileElements;
    // Host 已证明乘加与最终访问不溢出；结果单位为输入元素。
    return baseElements + tileIndex * static_cast<uint64_t>(tileElements);
}
```

`TileElements` 是调用处已选特化的编译常量；`tileIndex/baseElements` 仍为运行时 `uint64_t`，没有因为模板而冻结它们。上面的函数没有 tensor 分配、副作用或别名承诺，可以独立对比生成代码；在 kernel 中调用时仍保留原 count、tail 和数据依赖。

固定 LocalTensor 是另一条更严格的选择：仅当位置、偏移、容量和所有 feature/dtype/layout 分支都编译期确定，并已证明静态地址区间，才可用 SDK 公共构造形式 `LocalTensor<T>(TPosition::A1, offsetBytes, sizeElements)`。这里 `offsetBytes` 为该物理存储位置内字节偏移，`sizeElements` 为 T 元素数；用 `[offsetBytes, offsetBytes+sizeElements*sizeof(T))` 列全量区间表，包含对齐、padding、ping/pong 与同时存活关系。交叠区间必须在先前读写完成后才能复用，且现有硬件事件覆盖其生命周期。动态队列、运行时 tile 或未覆盖 feature 分支保留 TPipe 管理，不能只按单一路径“地址看着不同”删管理器。

## 数值与验证

常量化与作用域变化应保持全部数学操作、Cast 舍入和特殊值模式；浮点表达式的折叠、FMA 合并或运算重排可能改变数值，必须按原精度标准审查，不能把“都是常量”当作等价证明。验证所有特化命中/未命中、空输入、尾部、别名允许/禁止与固定布局的全部分支。检查 binary 大小、栈、spill、对象初始化指令和 Task 时间；spill 增长、ICache 恶化、tensor 绑定旧槽、事件被错误常量化时回退到原动态实现。

来源事实：通用 scalar 文档给出动态数组别名、局部值、贴近使用、避免多级指针、constexpr 和对象构造/地址逃逸的机制；arch22 FA 文档把静态 LocalTensor 限定为固定布局并要求区间证明。上述有限特化乘积、活跃集合模型与区间核验为工程提炼。通用改写可用于 910B/910C 与 950，具体构造与架构 guard 由目标 SDK 确认；没有引入 3510 的 VF/SIMT，也没有任何跨代阈值或速度保证。
