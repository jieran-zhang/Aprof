---
schema_version: aprof.knowledge-record/v1
id: planning.layout.fallback
kind: strategy
version: 1.1.0
status: active
title: 布局转换 通用回退
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/conversion/patterns.md
  original_path: ops/ascendc-tiling-design/references/conversion/patterns.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 261
  sha256: sha256:3b11c42fec83631ee8b2c26eefd3ac7b16b2606b6a09ea7ad15991c0b806e306
  excerpt_sha256: sha256:3b11c42fec83631ee8b2c26eefd3ac7b16b2606b6a09ea7ad15991c0b806e306
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.layout
references:
- planning.layout.transpose
evidence_status: source_reviewed_not_benchmarked
---

# 布局转换通用回退

先冻结逐元素的输出→输入坐标映射与实际 stride；以该映射建立可审查的参考，回退当前任务已验证的通用布局转换。每个输出有效元素或输出物理块只有一个 owner，读地址按源 stride 计算，写地址按目的 stride 计算；纯搬运不得引入计算 cast。若需要 dtype 变化，则单独冻结舍入、饱和与特殊值规则。

连续切片使用批量搬运；规则矩形采用 `planning.layout.transpose`；其他 stride 使用坐标解码的一般转换。小通道来源的 `TransDataTo5HD+Gather`、repeat 和对齐约束只属于其 API 组合，证据不足时不能强套。原地置换或相邻 owner 的非对齐物理块相交时，改用 workspace 或重新指定块 owner。

`UB_peak=max_t Σ A(bytes_of_live_buffer,t)+Tmp_API(t)`，A 为当前 API 字节对齐；workspace 按实际保存的有效元素与额外 padding 计，不因数学上元素数不变而忽略存储。阶段内队列/事件保证数据已就绪；跨 kernel 使用流依赖，不能以 PipeBarrier 代替跨核完成。

C2 记录真实 fallback entry/key、未满足的 stride/dtype/API/容量项和路由互斥条件。验证尾块、所有轴置换、非连续输入、别名和大偏移。这里只给通用数学方法和来源审读，无硬件资格或收益结论。
