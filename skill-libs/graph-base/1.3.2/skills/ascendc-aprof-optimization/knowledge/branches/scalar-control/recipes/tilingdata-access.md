---
schema_version: aprof.knowledge-record/v1
id: implementation.scalar-control.tilingdata_access
kind: recipe
version: 1.1.0
status: active
title: TilingData GM 直读与热点字段局部缓存
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
learning: {}
tags:
- abi-preservation
- scalar-load
- tilingdata
seed_reason: 审读五个固定开源修订中的直接来源，以中文提炼实现契约；保留旧 ID 含义，不承诺目标 SDK 编译结果或 NPU 性能收益。
parent: implementation.scalar-control
references:
- implementation.precision-boundaries.bounds
- implementation.scalar-control.constant_lifetime
- implementation.scalar-control.hot_loop_address
evidence_status: source_reviewed_not_benchmarked
---

# TilingData 的 GM 直读与热点字段局部缓存

## 解决的问题与适用条件

若大TilingData的整块栈复制或通过对象成员的重复字段读取在编译后仍保留，可能产生额外读写、依赖load或别名分析限制；编译器也可能已经消除这些工作。包内来源及当前源码形态足以支持提出“入口局部GM指针＋少量重复使用字段缓存”的优化候选，不要求先完成严格性能实验。结构体字节数、实际读取字段、每字段使用次数可由源码确认；栈大小、重复load、CSE和spill则由编译产物帮助判别。两类证据不能相互冒充。

实施安全条件是Host/Kernel ABI、字段类型/解释、地址空间/对齐、输入生命周期、数值顺序和C2分支保持合法；缓存字段所需活跃资源也要计入预算。编译热点证据属于试验价值与预测检验，缺失时准确记录其影响；安全不能从“减少load可能更快”推出，性能也不能从“字段只读、改写等价”推出。

适用于 launch 期间只读、布局已由同一版本 Host 和 Kernel 共同定义的 tiling；运行中会被更新的工作队列、跨核信号或动态状态不能缓存为常量。本条也不把所有 `GET_TILING_DATA_WITH_STRUCT` 都判为问题：小结构体、只访问一次或编译器已消除拷贝时，保留原方式通常更简单。

## 具体步骤与取舍

1. 固定原结构定义，记录 `sizeof`、各读取字段的 offset/类型/对齐，核对版本与 tiling key。缓存只使用原字段，不删字段、不重排、不修改 pack、不改变 Host 序列化长度和调用 ABI。
2. 入口取得局部 `const __gm__ TilingData*`；只读一次的冷字段可在分支内按需读取，热循环反复使用的 `stride/loopCount/tileSize` 读入未取地址的局部值。确保 tiling 在 launch 到最后读完期间不可被释放或写入。
3. 缓存时使用与原字段相同的整数/浮点类型。地址乘积需要拓宽就在乘之前转换；不能先以 32 位相乘后转成 64 位。浮点 scale 原样读取，不经过额外 float→half，也不移动 epsilon/correction 的计算次序。
4. 将局部标量或小的按值聚合体传给热函数，避免再次把 tiling 指针存到大对象。冷路径才需要的字段在相应路径内读取，减少寄存器活跃范围。
5. 用编译结果比较整块拷贝是否消失、重复 load 是否减少，检查栈/spill。缓存太多字段使寄存器压力增加时缩小缓存集合；不以减少 GM 访问数为理由强制复制整个结构到 UB 或改变同步。

设结构体 `S` 字节、热点字段总大小 `H`、循环 `L` 次、每次重复读取热点次数合计 `r`，整块拷栈需要处理约 `S` 的初始数据并可能读写栈；直接读取热点可把逻辑字段读取从约 `L×r` 次降为入口 `r` 次。实际 cache、编译器 CSE 和别名分析会改变 load 数，不能把 `S−H` 直接当作 DRAM 节省量。局部缓存的代价是同时活跃的字段寄存器和可能的 spill；优先缓存有明确重复规模且影响预测的字段；已有热点证据时按其范围收窄，没有热点证据时按源码工作量与资源代价比较，并保持性能假设身份。

## 选择与后继反馈

先比较字段读取/控制的工作规模与当前实现的主要数据路径。例如逐元素Scalar解码或大量分散搬运仍占据源码主循环时，缓存几个每tile字段未必是最值得试的一项。将读取的相关P/O知识实际用于排除不适用方案、计算容量或形成不同成本预测，不能以找到本配方就停止机会比较。若编译报告已确认原字段读取被CSE消除，应降低或放弃该缓存预测，而不是继续以源码多次出现同一字段作为独立支持。

R1没有有效收益时，R2可继续同Action，但需要新的可检验对象、参数或证据，并说明为何仍优于其他主要成本机会；再缓存相似字段本身不是新依据。计时无效仅表示无法判断，不允许把无效结果当支持；实际patch、字段/循环范围与解释必须一致。

## 保持 ABI 的最小上下文

以下 `TilingData` 必须是工程已有的 ABI 类型。为了说明读法，示例假定它已定义 `uint64_t inputStrideElements`、`uint32_t fullTiles`、`uint32_t tileElements`；这些名称只是本例字段，迁移时使用实际已有字段，不向 ABI 增加同名成员。`tilingGm` 是 Host 传入、正确对齐且至少 `sizeof(TilingData)` 字节的只读 GM 地址。

```cpp
const __gm__ TilingData* const tilingPtr =
    reinterpret_cast<const __gm__ TilingData*>(tilingGm);
const uint64_t strideElements = tilingPtr->inputStrideElements;
const uint32_t fullTiles = tilingPtr->fullTiles;
const uint32_t tileElements = tilingPtr->tileElements;
for (uint32_t i = 0; i < fullTiles; ++i) {
    const uint64_t inputOffset = static_cast<uint64_t>(i) * strideElements;
    // 原 tile 路径使用 inputOffset（输入元素）、tileElements（有效元素上限）。
    // 原事件/队列/尾块约束继续生效，不从 tilingPtr 重读相同字段。
}
```

示例没有 `auto local = *tilingPtr` 的整结构体拷贝；也没有把 pointer 强制去除 `__gm__` 后按本地内存访问。若 SDK/结构体封装要求 getter 或宏读取，保留合法地址空间接口，不能为了套用片段破坏编译契约。`fullTiles` 不含尾块时，原尾块仍在独立路径读取其有效长度。

## 验证、失败与证据边界

核验所有 tiling key、版本、dtype/layout、paged/non-paged、prefix 和 mask 分支，至少包含无任务、单 tile、动态尾和最大 stride。ABI 的原始字段字节和读出的值应逐项一致，oracle 全 case 通过后再计时。单一 feature 错误常来自缓存漏初始化、错误拓宽或冷字段遗漏；随机错须检查 tiling 生命周期和 Host 覆写。保留正确的宏/整结构读取作为 fallback，不通过缩减 case 或调整字段布局绕过失败。

来源事实：arch22 FA scalar 文档报告 regular FA 使用 GM TilingData 指针直读与局部热点缓存，另一 FIA v3 分支使用宏读取，明确不能全局机械替换；通用 scalar 原则提供局部变量、多级解引用和结构体大小的优化动机。正文缓存选择、`S/H/L` 代价模型、ABI检查及安全/性能分层为本次工程提炼，不是当前任务收益证明。arch22/A2/A3 与 arch35 的普通 GM 字段访问按各 SDK 支持编译；不迁移 arch35 `__ssbuf__` 转发或固定 cacheline batch 参数到 A3，没有目标硬件收益数据。
