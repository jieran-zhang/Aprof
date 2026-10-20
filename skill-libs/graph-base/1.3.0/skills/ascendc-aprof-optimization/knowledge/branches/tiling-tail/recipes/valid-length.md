---
schema_version: aprof.knowledge-record/v1
id: implementation.tiling-tail.valid-length
kind: recipe
version: 1.1.0
status: active
title: 有效长度、对齐长度与动态尾块
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 151
  sha256: sha256:c74ad927867806d42723213292831e22c84a2e84d75230e5aa615dee1500782a
  excerpt_sha256: sha256:c74ad927867806d42723213292831e22c84a2e84d75230e5aa615dee1500782a
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_GMToUB.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_GMToUB.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 3
  - 320
  sha256: sha256:8fd9166a39e7ab163695f1d965ad633725afa1c60cff08708b439f58f2a646ee
  excerpt_sha256: sha256:643aefa2bdb90c4fa26a228d9f36b5d487f11b9ebbcc80c4d7d3f52273abf98c
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_UBToGM.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_UBToGM.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 58
  - 148
  sha256: sha256:23e9b37e62ff5c2fed4b142ad65b346f8987aa6be527e291dae63466dc88f315
  excerpt_sha256: sha256:e4fc628736c5c7870254ce95b9ef24afb65e80df4762615190a2b173e22cb01d
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 31
  - 144
  sha256: sha256:a41ac2ff57f181c342d823a1b453bfabfb20c56bf840e31f4dff7232cefdc80a
  excerpt_sha256: sha256:9b82f521bfc25b8c16cea361e35e230d057580630377745c5a4a099d56a39447
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/00_vector_compute/add_high_performance/add.asc
  original_path: examples/01_simd_cpp_api/05_best_practices/00_vector_compute/add_high_performance/add.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 27
  - 345
  sha256: sha256:f7d075958365a8fc1af9879e90ab6494573f8869d3a538832c537d8e0f905042
  excerpt_sha256: sha256:d2b85d269202c81ba81366f010df36bf3c512f17f84bd0b145c0dd1425e49cda
learning: {}
tags:
- aligned-stride
- byte-element-units
- tail
- valid-count
seed_reason: 审读固定开源修订并提炼中文实现配方，保留既有 ID 语义；API 单位以实际 API 文档为准；未做目标 SDK 编译或 NPU 性能验证。
parent: implementation.tiling-tail
references:
- implementation.buffer-lifetime.reuse
- implementation.memory-transfer.strided-pad
- implementation.tiling-tail.fallback
evidence_status: source_reviewed_not_benchmarked
---

# 有效元素、对齐存储与动态尾块各自计数

## 原理与输入契约

同一个tile有三种不同长度：GM中的有效数学元素、UB中满足对齐的物理行跨度、API结构体里的字节/块计数。把它们合为一个`size`会造成越界读写、把dummy送入归约或多行错位。输入是C2已经分好的本核`taskBase/taskElements`、合法tile元素范围、输入/输出dtype和物理stride；本条实现其尾部，不重新分核、不改变输出所有者，也不把某个历史tile8192当默认值。

设本任务有效长度`L`元素、tile容量`T>0`元素、起点`B`元素，每元素输入字节`sIn`。循环数 `Q=L/T+(L%T!=0)`；第i轮`off=iT`，有效量`v=min(T,L-off)`，GM输入起点`B+off`，有效字节`v*sIn`，本地所需字节`AlignUp(v*sIn,32)`。若`L=0`，`Q=0`且不进入循环，不执行依赖一次有效生产的EnQue/Wait；空任务的整体行为沿用C2和原接口约定。

所有乘法/加法在足够宽的整数中预检，再转换SDK字段。`L+T-1`形式在极大长度下可能溢出，除法+余数写法避免这次加法；`B+L`和tile字节本身仍须检查。kernel计数只在范围已证实可表示时窄化，不能把强制cast当边界检查。

## 一维float尾块搬运片段

`xGm/yGm`分别是完整输入/输出`GlobalTensor<float>`；`xLocal/yLocal`是32B对齐、互不重叠的`LocalTensor<float>`，各自分配至少`AlignUp(T*4,32)`字节，dtype和位置为所用重载支持。`taskBase/taskElements/T`来自C2，且输入输出拥有相同的本任务有效区间。Host已验证整个GM范围和A2/A3无mode重载，单块`valid*4<2^21`，T及计算API的count合法。实际计算保持C2冻结内容。

```cpp
const uint64_t loops = taskElements / T + (taskElements % T != 0);
for (uint64_t i = 0; i < loops; ++i) {
    const uint64_t localOffset = i * T; // 元素，在本任务内
    const uint64_t remain = taskElements - localOffset;
    const uint32_t valid = static_cast<uint32_t>(remain < T ? remain : T);
    const uint64_t gmOffset = taskBase + localOffset; // float元素偏移
    const uint32_t validBytes = valid * sizeof(float); // 预检后可表示的字节
    AscendC::DataCopyExtParams cp{1, validBytes, 0, 0, 0};
    AscendC::DataCopyPadExtParams<float> pad{false, 0, 0, 0.0f};
    AscendC::DataCopyPad(xLocal, xGm[gmOffset], cp, pad);
    // 在既有MTE2->Vector完成边后，只对valid个元素执行C2的计算，生成yLocal。
    // 在既有Vector->MTE3完成边后：
    AscendC::DataCopyPad(yGm[gmOffset], yLocal, cp); // 无pad参数，只写validBytes
    // 下一轮覆盖同槽前，仍须完成既有最后消费者等待；双槽按真实slot执行。
}
```

这是调度/搬运片段，注释位置是本项目的真实计算和同步，不能直接删除后当作完整算子。换成转换算子时，输入块长`valid*sIn`、输出块长`valid*sOut`必须分别构造，不能复用float示例的cp；GM偏移也分别按对应tensor元素和物理stride解释。无需每轮重分配UB，所有槽按最大T分配，尾轮只缩有效count。

## 多行与归约的额外边界

对R列的float行，`rowBytes=R*4`、`rowElems=AlignUp(rowBytes,32)/4`。DataCopyPad多块正常模式会逐行对齐，UB第r行偏移为`r*rowElems`元素；数学归约count取`R`，分配和行stride取`rowElems`。无显式左右padding时`isPad=false`仍可能填dummy，它不是Sum/Max/Mean的通用单位元。Max尤其不能默认补0；R个负数会被0改变结果，NaN和符号零行为也须保持原oracle。优先使用支持有效count的API；需要对齐count才显式填合适单位元并核验API语义。

同一行分块归约时，局部tile尾与整条归约尾是两层边界，最后一tile不能重新初始化全局accumulator；Mean分母使用原有效长度，不能使用对齐长度。多行搬运的padding容量按每行计算，`rows*AlignUp(rowBytes,32)`不能替换为`AlignUp(rows*rowBytes,32)`。其他布局的行跨度来自其真实API，不能沿用本条ND普通模式。

## 成本、验证与失败回退

一维每任务最后至多一个短tile；总有效字节不变为`L*s`，填充/额外指令开销在尾部集中。若过度缩T导致大量短块，虽然合法也可能恶化MTE和标量开销。所有输入/输出/转换槽和workspace按最大对齐T与真实槽数计入UB预算；最后异步消费者完成前不能把空闲C++视图当可复用物理区。

验证`L=0,1,T-1,T,T+1,2T`及32B边界前后、最后核、非零taskBase、不同dtype和非连续行。检查所有任务区间的并集恰为C2有效域、互斥输出未相交、最后写入未超过分配。整齐shape通过、奇数shape失败时先查blockLen单位、rowOffset和dummy；恢复既有合法尾路径，字段/容量不满足则按C2允许范围拆更小tile或返回重规划，不扩大GM分配假设。

来源事实：API文档说明有效字节与逐行对齐、dummy及双端stride；AR全载笔记区分rLength与rLengthAlign；Add实现用当前剩余量裁剪curLen。宽整数循环式、跨dtype双cp和边界测试集合是提炼；来源AR笔记的临时区经验公式不作为所有reduce API的空间查询替代。尚无目标SDK编译或硬件收益验证。
