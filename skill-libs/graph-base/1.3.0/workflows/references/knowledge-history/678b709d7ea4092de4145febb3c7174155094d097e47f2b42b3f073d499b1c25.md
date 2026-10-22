---
schema_version: aprof.knowledge-record/v1
id: planning.layout.transpose
kind: template
version: 1.1.0
status: active
title: 布局转换、有效宽度与对齐宽度
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
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/index/gather_elements_v2/op_kernel/gather_elements_v2_transpose.h
  original_path: index/gather_elements_v2/op_kernel/gather_elements_v2_transpose.h
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 1
  - 522
  sha256: sha256:cc2ec40a9f9d3cfce1021e356e4e8f2a5f27e1528caaeb2ff1796a6a530c0d75
  excerpt_sha256: sha256:cc2ec40a9f9d3cfce1021e356e4e8f2a5f27e1528caaeb2ff1796a6a530c0d75
learning: {}
tags:
- transpose
- layout
- strides
- ownership
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.layout
references:
- planning.layout.fallback
- planning.indexing.gather_output_owned
- planning.under-fusion.chain
evidence_status: source_reviewed_not_benchmarked
---

# 布局转换、有效宽度与对齐宽度

## 语义与任务所有权

布局转换把输出坐标映射回同一输入元素，本身不作数值归约。先写出输入/输出 shape、每维 stride 的单位（元素或字节）、轴置换、dtype/cast、padding 是否可见及原地别名。只有相邻轴在两端都保持相对次序与连续 stride 时才能合轴。一般置换用 `src_offset=Σ output_coord[j]*src_stride[perm[j]]`；不能直接把非连续 tensor 展平成连续块。

将输出切成互不重叠的矩形/连续条带，每个 task 只写自己的有效区域；为了连续输入搬运，输入 tile 的形状可以不同。任意两个输出 owner 不能因为对齐 DMA 触及同一边界块而形成读改写竞争；尾部使用受支持的非对齐搬运，或为物理块指定同一 owner。原地转置若输入会被另一 task 后续读取，必须有合法环置换或 workspace，不能沿用普通 out-of-place 调度。

## 选择方法

先比较三种合法分解：连续切片可直接批量搬运；规则矩形可用片上 transpose；小通道 `[C,N]→[N,C]` 可比较 `TransDataTo5HD+Gather` 组合。后者在来源中是小 C 的特定实现，绝非全部 permute 的默认算法。大 C、复杂 stride、多个非相邻移动轴使用一般矩形转置或通用索引搬运。若转换只服务一个消费者且该消费者接受原 stride，可比较在消费者内改变地址计算；保留外部可见转换输出的要求。

小通道组合先按 C 个源平面搬入 UB，转换成 API 支持的局部布局，按 offset 表挑出有效 C 通道并可执行声明的 cast/后处理，再连续写回 `[curN,C]`。定义 tileN 为计划的 N 方向长度，tileNA 为 UB 存储跨度，curN 为尾块有效长度；分配、局部行地址和 offset 表用 tileNA，GM 读写和有效 mask 用 curN。不能用 curN 替换已分配行跨度。

## 容量、索引与同步

令 a 为字节对齐、`A(n)=ceil(n/a)*a`，b_x/b_y 为输入/输出字节宽，b_m 为转换中间类型宽，b_o 为 offset 宽，q_x/q_y 为输入输出分配份数，C_pad 为 API 局部布局通道数：

`U_peak=q_x*A(C*tileNA*b_x)+q_y*A(C*tileNA*b_y)+A(C*tileNA*b_m)+A(C_pad*tileNA*b_m)+A(C*tileNA*b_o)+Tmp+F≤U_available`。

这是列全量并存的保守预算；若分时复用必须列出具体存活期。来源的 float→half→uint8 路径在 q_x=q_y=2、b_x=4、b_y=1、b_m=2、b_o=4、C_pad=16 时产生 `tileNA*(16*C+32)` 字节（尚需实际对齐/tmp/保留）；该公式不能给别的 dtype 套用。该特定 API 重载的 repeat 上限、地址对齐和跨度范围须随 SDK 证明；文档里的 255 和 C≤16 不能直接作为全平台硬限制。

offset 表元素若是字节偏移应只乘一次 b_m；若 API 接受元素偏移则不乘。源/目的寄存器地址表同样按其声明单位构造。DMA→转换→Gather/Cast→DMA 有生产消费依赖，队列只解决其管理范围的依赖；临时区复用必须等待所有读者和异步搬运完成。每 task 独立时无需全核 barrier。

```text
task -> 输出 N 条带 [n0,n0+curN)，唯一 owner
按输入 stride 搬入 C×curN；本地每平面跨度固定 tileNA
在合法 repeat/stride 范围转换，尾部 mask 排除 padding
按声明 offset 单位抽取 C 通道；执行明确 cast/后处理
仅写出 curN×C 个有效输出，等待搬出后复用 buffer
```

```cpp
// 规划片段：n0、N、tileN、tileNA 已由 host 给定，均为元素数。
uint64_t curN = (N - n0 < tileN) ? N - n0 : tileN;
uint64_t localPlaneOffset = channel * tileNA; // 不用 curN 作物理跨度
// DataCopy/Transpose 参数按对应 API 的元素、字节或块单位分别生成。
```

本条的通用映射/owner 方法 scope all，不代表任何 SoC 已通过该 API 组合验证。索引决定源地址的 Gather 另见 `planning.indexing.gather_output_owned`；融合边界见 `planning.under-fusion.chain`。验证 C/N 非对齐、非连续 stride、单通道、多个小轴合轴、异 dtype、超大地址、别名和输出边界；当前没有 NPU 性能验证。
