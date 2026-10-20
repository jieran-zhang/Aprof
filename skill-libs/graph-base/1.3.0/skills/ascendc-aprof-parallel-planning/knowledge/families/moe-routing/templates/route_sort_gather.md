---
schema_version: aprof.knowledge-record/v1
id: planning.moe-routing.route_sort_gather
kind: template
version: 1.0.0
status: active
title: MoE 路由：全载或 Sort/Merge/Gather 阶段组合
scope:
  platforms:
  - dav-2201
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_init_routing/README.md
  original_path: moe/moe_init_routing/README.md
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 108
  sha256: sha256:57645238a1824c52955ac13a4e802a573c29a248c65855c3358a49aa4bb60345
  excerpt_sha256: sha256:57645238a1824c52955ac13a4e802a573c29a248c65855c3358a49aa4bb60345
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_init_routing/op_host/moe_init_routing_tiling.cpp
  original_path: moe/moe_init_routing/op_host/moe_init_routing_tiling.cpp
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 725
  sha256: sha256:7b19206e826dedefc6b37d6b959f0f46585089302a59678db1943e6b915a52cd
  excerpt_sha256: sha256:7b19206e826dedefc6b37d6b959f0f46585089302a59678db1943e6b915a52cd
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_init_routing/op_kernel/moe_init_routing.cpp
  original_path: moe/moe_init_routing/op_kernel/moe_init_routing.cpp
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 102
  sha256: sha256:6dde2573f9c6c561e00a0f255b0626804cec0518945d16ab38c32ea30cf6adb8
  excerpt_sha256: sha256:6dde2573f9c6c561e00a0f255b0626804cec0518945d16ab38c32ea30cf6adb8
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_init_routing/op_kernel/moe_init_routing_fullload.h
  original_path: moe/moe_init_routing/op_kernel/moe_init_routing_fullload.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 266
  sha256: sha256:1dabec182acc8dbdf6b990ffc14fb1c2a96b79c73091705f19fefa0a4f38eb1b
  excerpt_sha256: sha256:1dabec182acc8dbdf6b990ffc14fb1c2a96b79c73091705f19fefa0a4f38eb1b
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_init_routing/op_kernel/moe_sort_multi_core.h
  original_path: moe/moe_init_routing/op_kernel/moe_sort_multi_core.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 341
  sha256: sha256:ef674f6e8a3128b3ef4c75b798f2a0bde421dcf100511faf7ef984309edec3c7
  excerpt_sha256: sha256:ef674f6e8a3128b3ef4c75b798f2a0bde421dcf100511faf7ef984309edec3c7
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_init_routing/op_kernel/moe_gather_out.h
  original_path: moe/moe_init_routing/op_kernel/moe_gather_out.h
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 1
  - 257
  sha256: sha256:45be7d567f118eeddf823dbc0bc713f027de10d78098338443bf0765d0362bf9
  excerpt_sha256: sha256:45be7d567f118eeddf823dbc0bc713f027de10d78098338443bf0765d0362bf9
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/moe/moe_init_routing/tests/assets/golden.py
  original_path: moe/moe_init_routing/tests/assets/golden.py
  revision: d7e6a7c6c1450c040049486845336c77f3100406
  lines:
  - 35
  - 111
  sha256: sha256:56d9bb3edf5810822145097e0e8d40a4293e9bf28a1342a1b1c3e13c86a9e020
  excerpt_sha256: sha256:0e3795e1fe2b57d74d0e327d172807a9cdb69c1d8be9cf1d367fceef9555cce2
learning: {}
tags:
- moe
- routing
- sort
- gather
- inverse-permutation
seed_reason: 固定开源修订审读并以中文提炼；未做性能训练或硬件收益验证。
parent: planning.moe-routing
references:
- planning.sort-topk.merge
- planning.indexing.gather_output_owned
- planning.indexing.indexed_write_reduce
- planning.moe-routing.finalize_weighted_reduce
evidence_status: source_reviewed_not_benchmarked
---

# MoE 初始路由：排序、逆映射与特征 Gather

## 语义与索引域

设 token 特征 X 为 `[N,H]`，每 token 的路由分支数 K，专家索引 expert 为 `[N,K]`，L=N*K。将 expert 按实际 `[N,K]` 存储顺序展平为 key[p]，p=t*K+k；配对值是 rowIdx[p]。常见 rowIdx[t,k]=t+k*N，表示原 token/分支的列优先编号，**与展平位置 p 不同**。rowIdx 必须满足接口的排列约束，若存在重复/越界则不能把逆映射当作唯一写。

对 key/value 进行规定次序的排序，得到 `sortedExpert[r]` 与 `s[r]=sortedRowIdx[r]`；构造逆映射 `expandedRowIdx[s[r]]=r`；特征输出 `expandedX[r,h]=X[s[r]%N,h]`。固定来源 golden 对 expert 原始展平序列采用 stable 排序，故相等专家保留原 p 次序，不能改成按 rowIdx 数值打破平局。源的 fp32 key 转换要求 expert 值严格大于 `-2^24` 且不超过 `2^24`，不能把任意 int32 转 float 后排序视为精确。feature 重排本身只复制数据位模式，不改变 X 数值。

activeNum 在源接口中是 token 数上限：有效 expandedX 行数为 `A=min(activeNum,N)*K`，输出排序与逆映射仍覆盖 L 个路由。activeNum=0、大于 N、被丢弃路由及后续 finalize 的映射域必须联合核验，不能把 A 错写为 min(activeNum,L)，也不能假定少复制特征就可省略完整索引输出。

## 全载路径与分阶段路径

全载：每个参与 gather 的核在 UB 保存整份 L 的排序/映射状态以及其负责的源特征行，核内完成排序、逆映射和复制；仅指定核写完整索引结果，其余核只利用本地副本。优点是省去跨核排序依赖，代价是重复排序/索引读取和较大常驻 UB。来源 `IsFullLoad` 先检查其实现限制，再以排序空间+本核 gather 数据能否共存判断；不是只检查 feature 或只检查 key 能否入 UB。

分阶段：先各核局部 Sort（VBS），本核归并，再必要的跨核 MrgSort（VMS），最后 Extract 排序 key/value；接着构造 source→destination 逆映射，再按所有权复制 feature。普通分支按 token N 或分支 K 分核，使每个 `(t,k)` 只产生一次目标路由写；小 active 分支可按有效目的行 r 分核，只读取 s[r] 后 gather X。前者利用一行 X 的 K 次复用，后者避免读取不再输出的路由；选择应比较 A、N、K、H、重复读和容量，而不把上游固定比例或最大列阈值当作通用规则。

排序方法复用 `planning.sort-topk.merge`，特征取数复用 `planning.indexing.gather_output_owned`；本条关注阶段编排与三种索引域。若源写路径使用 inverse map，唯一目标来自 rowIdx 是排列的证明；不需要为相等专家上原子，因为相等 expert 仍有不同路由行 r。

## 容量、workspace 与同步

令 `A_b(z)=ceil(z/a)*a` 为字节对齐，b_x 为特征字节宽，b_i=4 为本源 INT32 索引宽，b_p 为排序 proposal 宽，r 为本核驻留 token 行数，h 为特征片长。全载保守预算 `U_full=U_sort_state(L)+A_b(r*H*b_x)+U_inverse(L)+U_out_index(L)+Tmp+F≤U_available`，其中排序状态和索引副本必须依实际队列存活期计算；不能将同一物理区重复计费，也不能省掉并存的两份状态。H 太大可改成 h 片，但反复排序是否可保留也要计入。

阶段路径每核分别满足 `U_sort(T)` 和 `U_gather≈q_x*A_b(r*h*b_x)+q_i*A_b(r*k_tile*b_i)+Tmp_gather+F`；不同 TPipe 阶段销毁/重建后可分时使用 UB，跨阶段仍存活的数据须在 GM 保留。全局 workspace 包含排序各代 proposal、dst→src 排列、逆映射临时区和同步元数据；按同时存活布局相加。源 host 的排序预留为 `sizeof(float)*L*2*3` 加同步、索引和额外固定区，这是该实现的分配，不能用“两份最小 proposal”替代，也不能将其固定预留推广到别的实现。

局部排序完成后才进入跨核合并，每轮只写自己的 run；逆映射在排列完成后才能读取，feature 复制也须等其依赖索引。源包含核间同步并在 host 设置独占调度模式，移植时不可只复制 kernel 而丢失 host/schedule 约束。使用全核同步时无有效数据的参与核仍要参加协议；不能在 barrier 之前提前返回。各阶段 workspace 覆写必须等待旧读者完成。

```text
expert[p] 与 rowIdx[p] 配对，stable sort（平局按原 p）
得到 sortedExpert[r], s[r]；对每个 r：inverse[s[r]]=r
等待逆映射/排序输出按协议完成
if 按源 token/分支分区:
    本核读取 X[t,:]，对拥有 k：r=inverse[t+k*N]
    若 r<A，则复制到 expandedX[r,:]
else:
    对拥有的目的行 r<A：复制 X[s[r]%N,:] 到 expandedX[r,:]
索引输出始终覆盖接口规定的 L 个元素
```

本模板 scope dav-2201，依据固定源 A3 支持与具体旧架构分支，未上板；A2、950/arch35 配置存在不等于本模板已对其核验。验证相等专家的稳定次序、rowIdx 与 p 区别、K=1、N<核数、全同专家、activeNum 各边界、H 尾片、跨核归并尾 run、key 可精确范围和 inverse 双向一致性。后续加权合并见 `planning.moe-routing.finalize_weighted_reduce`。
