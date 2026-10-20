---
schema_version: aprof.knowledge-record/v1
id: planning.sort-topk.fallback
kind: strategy
version: 1.1.0
status: active
title: Sort / TopK 通用回退
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/sort/alg-two-level-mrgsort.md
  original_path: ops/ascendc-tiling-design/references/sort/alg-two-level-mrgsort.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 681
  sha256: sha256:031b9829393ccd4f83ca8cd19d8a6ce47d42274e2975c247d487e9d87edcdcf6
  excerpt_sha256: sha256:031b9829393ccd4f83ca8cd19d8a6ce47d42274e2975c247d487e9d87edcdcf6
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/sort/patterns.md
  original_path: ops/ascendc-tiling-design/references/sort/patterns.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 67
  - 200
  sha256: sha256:915e5ca3f7c163d43b7c6d7c592ab8d45edd0776c6864a89bd8b0758395e2851
  excerpt_sha256: sha256:4b3f156e4294fdb7a3b6f22a44970e81d4507704d9aa55d004b515d1e248d05f
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.sort-topk
references:
- planning.sort-topk.merge
evidence_status: source_reviewed_not_benchmarked
---

# Sort / TopK 通用回退

退回当前任务已验证的排序/TopK 基线；若任务尚无基线，先用接口参考计算确认比较关系和输出，不将回退条目当作一个可直接运行的 kernel。记录排序轴、N/K、稳定性、相等值 index 次序、NaN/±0、输出 dtype/index 基准和非法参数行为。

可执行的保守分解是：每行独立，由一个 owner 完整排序；超过核内容量时按 `planning.sort-topk.merge` 分块并保存 value/index 配对，不能以多个局部 TopK 的无序拼接代替全局结果。只有同一比较关系下的合法剪枝证明成立才减少候选。稳定性未证明、整数键 fp32 转换不精确、API 不支持 dtype 或资源计算缺项时，保留已验证实现并明确缺口。

容量按 `UB_peak=max_t Σ live_aligned_buffer_bytes(t)+API_tmp(t)`，workspace 按同时存活的两代 runs、索引及同步元数据之和计；字节宽和对齐来自当前 dtype/API。跨轮合并输出区间唯一写，生产完成后消费，消费结束后覆写。该数学分解可作全平台规划候选，未确认目标硬件或性能。

C2 写出实际 fallback entry/key、命中原因及与专用分支互斥的条件；验证相等键跨 tile、尾块、K 边界和最大索引。不得用来源示例固定核数、固定 tile 或历史收益填补当前容量与语义证据。
