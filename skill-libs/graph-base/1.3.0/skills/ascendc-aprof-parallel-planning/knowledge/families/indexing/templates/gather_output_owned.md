---
schema_version: aprof.knowledge-record/v1
id: planning.indexing.gather_output_owned
kind: template
version: 1.0.0
status: active
title: Gather 输出所有权、行列分区与尾轴路径
scope:
  platforms:
  - dav-2201
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/index/gather_elements_v2/README.md
  original_path: index/gather_elements_v2/README.md
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 1
  - 106
  sha256: sha256:c8df45df36e823c8531e2e64a7d396d53f04c7e75ddc223dfb476c3910ffc43e
  excerpt_sha256: sha256:c8df45df36e823c8531e2e64a7d396d53f04c7e75ddc223dfb476c3910ffc43e
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/index/gather_elements_v2/op_host/gather_elements_v2_tiling.cpp
  original_path: index/gather_elements_v2/op_host/gather_elements_v2_tiling.cpp
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 105
  - 273
  sha256: sha256:c7bb8d76d1741b5c3212a8de9f28bf6f9de5fe2f7d012bfa90780b25e6f12793
  excerpt_sha256: sha256:e80d0fcbd0b582c83e9a37fb8fd61dcff95d5c1b98af493630cba1ff467fb9c8
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/index/gather_elements_v2/op_host/gather_elements_v2_last_dim_tiling.h
  original_path: index/gather_elements_v2/op_host/gather_elements_v2_last_dim_tiling.h
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 1
  - 369
  sha256: sha256:c5c10605e8e2621e3c8fec9e8844b5c541b65877b2037d5c3991689e4f31ec5c
  excerpt_sha256: sha256:c5c10605e8e2621e3c8fec9e8844b5c541b65877b2037d5c3991689e4f31ec5c
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/index/gather_elements_v2/op_kernel/gather_elements_v2_scalar.h
  original_path: index/gather_elements_v2/op_kernel/gather_elements_v2_scalar.h
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 35
  - 187
  sha256: sha256:d7038ab1282e3a89aaecc2123a5b5c6bd3e6ce041703dfcbc63c34a0fbace77f
  excerpt_sha256: sha256:27c6ffe9981fd02e7bf51e3722407a0bbe0b2ec0a73904fb0162e78f43843ab3
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/index/gather_elements_v2/op_kernel/gather_elements_v2_transpose.h
  original_path: index/gather_elements_v2/op_kernel/gather_elements_v2_transpose.h
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 1
  - 522
  sha256: sha256:cc2ec40a9f9d3cfce1021e356e4e8f2a5f27e1528caaeb2ff1796a6a530c0d75
  excerpt_sha256: sha256:cc2ec40a9f9d3cfce1021e356e4e8f2a5f27e1528caaeb2ff1796a6a530c0d75
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/index/gather_elements_v2/op_kernel/gather_elements_v2_last_dim.h
  original_path: index/gather_elements_v2/op_kernel/gather_elements_v2_last_dim.h
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 1
  - 523
  sha256: sha256:caf8774a67ba31a55ef29be6b785545a877eea0eb856777d588f00f6f94a858c
  excerpt_sha256: sha256:caf8774a67ba31a55ef29be6b785545a877eea0eb856777d588f00f6f94a858c
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/index/gather.md
  original_path: ops/ascendc-tiling-design/references/index/gather.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 25
  - 184
  sha256: sha256:0f63900de53cd6e704572f14fc896b4e477b47b74ebf1371c130db2810992c63
  excerpt_sha256: sha256:08be2c49bafe17407829de0a4e1d8bd47f7aef8216d7f499d8a589ced28c61a1
learning: {}
tags:
- gather
- indexing
- ownership
- last-dimension
seed_reason: 固定开源修订审读并以中文提炼；未做性能训练或硬件收益验证。
parent: planning.indexing
references:
- planning.layout.transpose
- planning.indexing.indexed_write_reduce
evidence_status: source_reviewed_not_benchmarked
---

# Gather：按输出所有权划分的取数

## 语义、形状与平台边界

用于 GatherElements 类逐元素取数，index 与输出同形，每个输出坐标独立选择源 tensor 的 gather 轴位置。冻结 d 的归一化、源/索引 shape 与 stride、负索引和越界行为，不能混同“一个一维 index 供整行共享”的 IndexSelect。设 `g=normalize(index[o],X_dim[d])`，则 `src_coord[d]=g`，其余轴 `src_coord[j]=out_coord[j]`，`y[o]=x[Σ src_coord[j]*x_stride[j]]`。只搬运位模式，不进行算术 cast；BF16/INT32 用同宽类型作搬运时必须证明只是 reinterpret。

本模板的具体分支来源是 ops-nn GatherElementsV2 的 host 与 scalar/transpose/last_dim 实现，scope 保守限 dav-2201；README 列 A2/A3 支持，但本次没有构建或硬件验证。输出所有权的数学方法可以迁移到别的平台，迁移需重新核验 API、对齐、索引宽度和内存路径；不能视为硬件资格。

## 非尾轴：按行或行列共同分核

把 d 前后的索引维展为 `P=prod(index_shape[:d])`、`J=index_shape[d]`、`Q=prod(index_shape[d+1:])`，源 gather 长 G、源后轴长 Qx。逻辑输出 `[P,J,Q]`。P 足够供核时，每核处理若干完整前置行和该行全部后轴列；P 较少时，每前置行一个核组，组内再分后轴 Q 列。两者均让某个 `(p,q)` 的整个 J 取数序列只有一个 owner，无需输出原子。用商余分配：给 M 个 owner 分 L 个任务时，第 c 个 owner 有 `floor(L/M)+(c<L%M)` 个，起点 `c*floor(L/M)+min(c,L%M)`；只启用有有效工作者。

前后各维 shape 相同且连续时，可写简化地址 `x_base(p)+g*Qx+q`。若 index 的非 gather 维比 X 小，必须逐维分解 index 的 p/q 坐标并使用 X stride，不能用展平 p 或 index 的 Q 直接替代源跨度。host 与 kernel 应共享这一映射口径。

比较两条实现：scalar 路径批量搬 index、逐输出在 GM 取源值、批量写 y，容量小但标量寻址多；transpose 路径把 X 和 index 在本核负责的后轴列片转成 gather 轴连续的局部行，在 UB 进行 Gather，结果反转置写回。来源 transpose 分支使用每核独立 GM workspace 作中转，不能写成仅片上转换。需比较该额外写读与标量访问代价；转置/offset 单位规则复用 `planning.layout.transpose`。

## 尾轴：直接行 gather 与双轴分片

d 为末轴时 Q=1，源行沿 G 连续，不需要非尾轴 transpose workspace。能容纳源整行及索引/输出片时，可批量处理多行；索引 J 很长则切索引片，每片独占输出区间。G 很大时，切源轴窗口并为每个索引判断它属于哪个源窗口，按相对偏移 Gather，再只合入命中结果；不能把所有未命中的默认值覆盖已命中输出。索引负值应先按接口合法范围修正，超范围行为不能用无条件模 G 悄悄改变。来源 scalar 的修正式只能在已确认合法域内复用。

当源窗口数过大或没有合法/划算的向量路径，可退到按输出元素均分的 scalar 取数。尾轴行不足时也可沿一行的索引 J 切分以增加 task；每个 task 可重复读源行，但必须只写自己的索引片。非尾轴“分后轴 Q 列”与尾轴“分索引 J 片”是不同的所有权划分，不能共用错误的偏移公式。

## 容量与代价

`A(z)=ceil(z/a)*a` 为 a 字节对齐，b_x/b_i/b_o 为值、索引和偏移字节宽，r 为批行数，g/j 为源/索引片长，q_* 为实际分配份数。直接尾轴 gather 的保守预算是 `U=q_x*A(r*g*b_x)+q_i*A(r*j*b_i)+A(r*j*b_o)+q_y*A(r*j*b_x)+U_mask+Tmp+F`。负索引修正若另需 scratch，再加对应索引片；若将它复用在 index 的另一半，仍须计完整分配。scalar 路径至少计 `q_i*A(j*b_i)+q_y*A(j*b_x)+F`，不需要为整个 G 分配 UB。

非尾轴转置路径 `U=max(U_transpose,U_gather)` 仅在两个阶段确实复用同一缓冲且无重叠流水时成立，否则按存活峰值求和；每核 workspace 按被保留的 X/index/结果转置块逐项分配并按生存期复用，总 `W=Σ_active_core W_core+W_system`。源片×索引片的循环有重复读放大，必须计实际源读取次数；不能只按输出总元素数推定带宽成本。

```text
冻结坐标/stride/合法 index；建立输出互斥分区
if 非尾轴且转置路径容量/API 可行:
    本核源/索引列片转置 -> gather 轴连续取数 -> 反转置有效输出
else if 尾轴且向量路径可行:
    每行/索引片读取 index，修正合法负索引
    整源行或逐源窗口 gather，命中 mask 合入输出
else:
    每个拥有的输出 o：解码坐标；读取 x[src_coord]；写 y[o]
等待 DMA/Vector/标量读者完成后才复用其 buffer
```

Gather 重复读取同一源无需归约，也无需原子；索引改变写目标的操作另见 `planning.indexing.indexed_write_reduce`。验证多维非等长非 gather 轴、负/边界索引、空 shape 的接口处理、非尾/尾轴、同一源多次命中、G/J 不对齐、极长索引、64 位地址与分片边界。具体 API 的 byte offset 只乘一次 sizeof；当前来源审读不包含 NPU 性能结论。
