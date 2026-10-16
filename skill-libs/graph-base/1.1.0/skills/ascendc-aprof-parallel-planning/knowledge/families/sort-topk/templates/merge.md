---
schema_version: aprof.knowledge-record/v1
id: planning.sort-topk.merge
kind: template
version: 1.0.0
status: active
title: Sort/TopK 分块与层次归并
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/sort/alg-two-level-mrgsort.md
  original_path: ops/ascendc-tiling-design/references/sort/alg-two-level-mrgsort.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 681
  sha256: sha256:031b9829393ccd4f83ca8cd19d8a6ce47d42274e2975c247d487e9d87edcdcf6
  excerpt_sha256: sha256:031b9829393ccd4f83ca8cd19d8a6ce47d42274e2975c247d487e9d87edcdcf6
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.sort-topk
references: []
evidence_status: source_reviewed_not_benchmarked
---

# Sort/TopK 分块与层次归并

## 适用域与算法骨架

排序键、稳定性、相等值顺序、NaN、index 语义已明确。

先核内排序/归并，再按必要层级跨核合并；TopK 只有证明可剪枝时才减小保留集。

## 任务所有权、归约与同步

每轮 merge 对输出区间唯一写；各轮之间建立完成依赖；index 始终绑定原元素。

## 资源与成本公式

UB=data+index+proposal+ConcatTmp+SortTmp；tmp 由当前 API 查询；层数≈ceil(log_fanIn(totalTiles))。

容量、可用核数、API 临时区由当前平台与 SDK 核验。所有容量使用字节，保留对齐和同时存活区间；不得把上游 4KB、固定 tile 或核数当通用约束。

## 参数空间与替代方案

tile、归并 fan-in、每轮保留数、核内轮数。

任务少时单核排序；特殊语义或不支持 dtype 回退基线。

## 伪代码

```text
query tmp sizes; choose feasible tile and merge fan-in
local sort -> local merge while ownership remains within core
for necessary cross-core levels: wait producers -> merge disjoint output intervals
retain stable key/index/NaN semantics and TopK proof
```

## 可复用 Ascend C 关键片段

```cpp
// 任务分配片段；排序和归并 API 的 tmp 需求必须另行查询。
const uint64_t tile = AscendC::GetBlockIdx();
// 仅合法 tile 进入排序；不以示例固定 tile 代替实际 tmp 容量计算。
```

片段省略工程与已声明的张量/变量，不是完整可运行算子；API 重载、作用域、别名和平台支持在 C3 核验。C2 冻结算法、所有权、合并顺序和数值语义；tile、局部 buffer/API 实现只在已声明容量/语义边界内调整。

## 验证与证据状态

来源审读完成，当前没有 NPU 性能验证。验证覆盖空/极小输入、对齐边界、尾块、多 task、特殊值和最大资源需求；完整正确性通过后才用统一计时协议比较。历史模板结果不构成当前性能承诺。

