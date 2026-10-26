---
schema_version: aprof.knowledge-record/v1
id: implementation.memory-transfer.input-tile-residency
kind: recipe
version: 1.0.0
status: active
title: 同一 owner 保留输入 tile，删除重复 GM 读取
scope:
  platforms:
  - dav-2201
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/00_introduction/01_add/add_tpipe_tque/add_tpipe_tque.asc
  original_path: examples/01_simd_cpp_api/00_introduction/01_add/add_tpipe_tque/add_tpipe_tque.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 20
  - 98
  sha256: sha256:3fd854a223214eec19b03eebf4be3397c81358ebd526d07b17202a5fd522b654
  excerpt_sha256: sha256:2e8f3388725eee71af0c28ccc76c2e01fc7ba01c7b3ca06cf7f89c473efec085
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/resource_management/TPipe/InitBuffer.md
  original_path: docs/zh/api/SIMD-API/basic_api/resource_management/TPipe/InitBuffer.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 34
  - 220
  sha256: sha256:36da88132f7d5f62484bc98896bd99577bcce25d71a84e21220731a557aea34d
  excerpt_sha256: sha256:70619eed307e130c5d64b3936d3c609e096c608ba0b6bba136e773385fe5bd2d
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/resource_management/TBuf/Get.md
  original_path: docs/zh/api/SIMD-API/basic_api/resource_management/TBuf/Get.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 34
  - 98
  sha256: sha256:23ef70d79cf63af9b179082dc436f6fc80c6441a050e3a7600838af3cd94617a
  excerpt_sha256: sha256:7ddd61b3e98c4e594924b5e620a362b82b9ad4fe81310f3956d9afcacd73dded
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_GMToUB.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_GMToUB.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 3
  - 325
  sha256: sha256:8fd9166a39e7ab163695f1d965ad633725afa1c60cff08708b439f58f2a646ee
  excerpt_sha256: sha256:1de0688ad7d6af2b7498f280b3138e462c600af310d93a8008a703dec31ebc55
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_UBToGM.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_UBToGM.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 3
  - 194
  sha256: sha256:23e9b37e62ff5c2fed4b142ad65b346f8987aa6be527e291dae63466dc88f315
  excerpt_sha256: sha256:03dfe694e7045a7cfe836089d6448b60f7811fded4d4f6a8d6fad6021b119fc8
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/mmad_gelu.asc
  original_path: examples/01_simd_cpp_api/05_best_practices/03_fusion_compute/matmul_gelu_high_performance/mmad_gelu.asc
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 21
  - 746
  sha256: sha256:2fb232c81805420c88755d9bc41ea3561c3f4107946306425d1a43b48c31dd1d
  excerpt_sha256: sha256:a430742ce4ff9786a78aaf637c1c34b666d95bbe612208a901710fca16e894f7
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/data_structures/GlobalTensor/SetL2CacheHint.md
  original_path: docs/zh/api/SIMD-API/basic_api/data_structures/GlobalTensor/SetL2CacheHint.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 3
  - 112
  sha256: sha256:62807570650c1a69ab2bf0ba2bce606a4a3141d5d9d976fdbf3bdaf1d4df1092
  excerpt_sha256: sha256:8b3a062e7527c371f256ed15a82ae19d75e97d7d618d7381aa07605d627ce6ee
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/sync_control/intra_core_sync/PipeBarrier_ISASI.md
  original_path: docs/zh/api/SIMD-API/basic_api/sync_control/intra_core_sync/PipeBarrier_ISASI.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 3
  - 97
  sha256: sha256:730571f5039906830624ccba76cff76d318305831f96538d7821be7c7c737773
  excerpt_sha256: sha256:a81403695033181d574bb850bc5da90c4c1099460919737daea43003df73a38b
learning: {}
tags:
- input-reuse
- ub-residency
- redundant-load
- last-consumer
- arch22
seed_reason: 审读固定修订的 API、Host 分派和 kernel；输入原值保留与删重读方法为工程提炼。未做目标 SDK 编译、NPU 正确性或性能验证。
parent: implementation.memory-transfer
references:
- implementation.buffer-lifetime.reuse
- implementation.memory-transfer.l2-reuse-order
- implementation.memory-transfer.cache-hint
- implementation.memory-transfer.strided-pad
- implementation.fusion-composition.vector_chain_residency
evidence_status: source_reviewed_not_benchmarked
---

# 同一 owner 保留输入 tile，删除重复 GM 读取

## 方法与相邻知识的区别

同一个 kernel 的同一 task/owner，若多个实际计算消费者需要**同一逻辑版本、同一有效区域的输入原值**，可让首次搬入的 UB tile 一直存活到最后消费者完成，把后续消费者的 GM→UB 重读改成读这个本地 tile。保留原算法、计算次序、dtype/Cast、舍入及每个输出的所有者；不把原本不同版本的数据当成重复输入。典型形态是残差/多分支计算 `tmp=scale*x; y=tmp+x`，或原输入同时供多个冻结计算阶段使用。两处都确实读原 x；单纯 `y=scale*x+bias` 的第二份 x 从未被使用时，应先登记并分析无用搬运，不能据此冒充“两消费者输入复用”的正例。

| 候选 | 实际变换 | 逻辑 GM 读请求 |
| --- | --- | --- |
| 本条输入驻留 | 同一原值在本 owner 的 UB 中保留，后续消费重定向到该值 | 可以删除经证明冗余的重读 |
| `buffer-lifetime.reuse` | 不同时存活的**不同值**共享物理 UB 区 | 单独应用不保证少读输入；可辅助安排本条容量 |
| `l2-reuse-order` / `cache-hint` | 保持所需读取，调整顺序、工作集或 cache 策略 | 有效逻辑读量保持；HBM 命中情况可能改变 |
| `vector_chain_residency` | 合并允许的 Vector 链，让中间结果片上交接 | 省去允许消除的中间 GM 物化；涉及融合边界 |

已经在同一 kernel、同一 owner 中的两处重复载入，不需要仅为应用本条创造新融合 region。反之，原先两个独立 dispatch 的 UB 不连续存在，也不能用本条跨 dispatch“保留输入”；先返回 C2 确定是否允许融合。Cube 的 L1/L0 复用走 `planning.matmul.resident`，这里不替代其层级、Matmul API 或累加生命周期。

## Action 实例、方法门禁与证据

`action.reuse_input_tiles` 仍使用原有四个硬前提：`symptom.source.insufficient_input_reuse=true`、`constraint.reuse_domain=true`、`constraint.semantic_equivalence=true`、`constraint.capacity=true`。实例还需明确目标输入/地址视图、当前实现 hash、workload、stage、实际消费者、重复载入位置、参数与计划身份。带宽饱和、MTE 占比或 Action 名称均不能代替源程序的重复原值证据。

本方法的 router 还核对以下条件；证据必须绑定当前实例、目标、参数和已确认计划，不能沿用其他 tile/目标的 ready 结论。`true` 表示材料已明确证明；缺材料保留 unknown，不能执行 C3。C2 可以在 unknown 下列条件化方案并请求补证。

| 门禁 | 应有证据 |
| --- | --- |
| `constraint.same_input_region` | 各拟合并读取的 GM 地址集合、dtype、layout/物理 stride、有效元素域一致；记录每个消费者读取的 UB 映射。不能仅凭两个变量同名，或两次 byte count 相等判断 |
| `constraint.input_value_preserved` | 从首次载入到最后消费者，原值的 UB 区不被计算/API/scratch/DMA 覆盖；输入 GM 的别名写入、可变 producer、原子或其它 task 的更新不使原算法本该读取更新版本。逐个检查原地重载和隐式 source-reuse API |
| `constraint.reuse_domain` | 所有消费者在同一 task/owner、同一 dispatch、同一输入逻辑版本的允许窗口中；窗口终止条件已声明 |
| `constraint.dependency_lifetime` | 首次 MTE2 完成→每个读者、每个最后读完成→下一写者的合法队列/事件；含异步读者、预取、回卷和结束排空 |
| `constraint.output_ownership` | 输出地址和每个输出唯一写者不变；别名写回不会破坏未来输入读取，也不改变跨任务协议 |
| `constraint.capacity` | 以实际物理槽、独立 TBuf、padding、API 临时区和其它驻留状态形成完整字节账；按本次 tile/精度/深度满足 C2 预算及目标可用容量 |
| `constraint.plan_freedom` | 由 hash 绑定的完整有效计划确认可以调整本次输入存活期/读者映射，且 tile、owner、通路、融合边界和资源在允许范围 |
| `constraint.semantic_equivalence` | 每步运算和 Cast 边界、顺序、别名、异常值与副作用保持；重复读取确为同一原值而非有意观察更新 |

`same_input_region` 是本条直接消除整段重读的保守条件。两个消费者只部分重叠时，需要先逐段证明公共区与各自独有区、尾部和地址映射，不能把整次第二搬运删除；本条代码只覆盖完全一致的连续 tile。广播小输入跨多个本核输出 tile 的驻留也需明确广播映射、失效代次及窗口内预算，P 的 `planning.elementwise.broadcast` 可供规划，不能直接将输出 tile 的 offset 套在广播源上。

## 实施顺序、所有权与失效

1. 在当前 Host 分派/tiling/kernel 路径中列出每次输入读取：`(dispatch, owner, input_version, GM区间/stride, valid域, UB位置, 消费者)`。确认两个读取都被当前实际分支消费；不把未执行的替代分支相加。
2. 画原值 x 的全部读写链。把首次载入后的 x 标为只读；第一个消费者的结果写到独立 tmp/y 或已证合法的其它区。不能继续先在 x 上原地做 Muls，再把这个已经改写的 x 给需要原值的 Add。
3. 只把内容相同、原值仍有效的后续读者改为该驻留视图；保留其它必需搬运、输出、Cast 和顺序。删除对应重复 DMA 及其专用依赖前，确认事件没有同时为别的 producer/consumer 服务。
4. 输入队列的 x 直到**最后一个消费者实际完成**后才 FreeTensor/允许下一 DMA 覆盖。DeQue、C++ 局部变量离开作用域、发出 Vector 指令都不代表完成。输出槽直到 MTE3 最后读取完成后才可覆盖。
5. 跨 tile 驻留的参数区使用明确 key，例如 `(输入地址,版本,布局,shape,参数代次)`；任何 key 改变立即结束旧窗口并重新搬入。不能仅凭地址没变，跨请求、循环状态更新、专家组切换或下一 dispatch 继续使用旧值。
6. 记录实际删掉的读请求及使用该输入的文档选择。不同方法同时作用于同一物理读取时，只记一次删读量；“reuse_input_tiles + reduce_memory_traffic”不是两份独立流量收益。

输入原值无法保留时，合法替代是继续重读，或在容量和原 API 合同允许时显式保存原值副本，再接消费者。副本的载入/UB 拷贝成本、物理区和同步要重新记账；发生容量或数据流变更时形成新的计划/证据后继，不能把旧 capacity=true 直接当作新实现资格。需要观察新 GM 版本的第二次读取必须保留。

## 容量与流量：分别计算三笔账

所有容量用**字节**，形状/count 用**元素**。令 T 为一个输入 tile 的最大有效元素数，s 为该 UB 表示每元素字节，a 为 API/布局要求的对齐，`A(B)=ceil(B/a)*a`；若物理 stride、padding 或转换扩大区域，使用实际跨度替代 T*s。`d_r` 是同时分配的驻留物理槽数，`B_r=A(T*s)`；`B_other` 含流式输入、各输出槽、独立中间区、workspace、API 预留和 bank padding。

```text
实际静态分配 U_alloc = d_r * B_r + B_other <= C2预算 <= 当前目标可用 UB
活跃字节下界 U_live = max_t Σalive alignedSpan(value)
```

`U_live` 不自动等于 `U_alloc`。删除 x2 的 DMA、甚至不再用 x2 的 C++ 变量，仍不使已独立 InitBuffer 的 x2 区自动消失；必须实际删除该分配或实现合法共享布局，才能扣掉物理字节。双缓冲要按真正分配的两份 x 计账；不能把保留更久的 x 视为“第一消费者结束即释放”。API 若破坏源，保存原值还要加一份独立区。扩大驻留窗口也可能迫使减少预取深度、缩 tile 或增加任务开销。

下面的有界 FP32 代码使用 x、tmp、y 各一份，`U_data=3*AlignUp(4*T,32)`。T=16384 时仅三块数据为196608 B；这只是字节演算，**不表示目标可用 UB 足够**，其它分配和预留仍须加入。若直接父本已分别静态分配 x1、x2、tmp、y 四块，即使 x2 不再读，也仍是四块，直到代码实际移除 x2 分配。不能因阶段顺序就把全部独立分配取 max。

令 W 为该窗口有效输入字节，R 为**确实消费同一原值**的次数，B_fixed 为其它必须读写流量。已核验原实现每个消费者重读一遍、候选只搬入一遍时：

```text
逻辑 GM 读请求：R*W -> W；理论删去 (R-1)*W
总有效 GM 读写：R*W+B_fixed -> W+B_fixed
```

`tmp=scale*x; y=tmp+x` 且 tmp 已留在 UB、仅 x 读/最终 y 写时，R=2、输入/输出同宽，总流量从3W到2W。这里没有删除数学上的第二个 x 消费，也没有删掉 Vector 的本地读；只删后一次 GM→UB。

**逻辑 GM 请求、HBM 字节、耗时分别记录。** 原重读若已命中 L2，HBM 读未必下降 W；UB 复用仍可减少 GM→UB 请求与发射，但是否缩短关键路径未知。`CACHE_MODE_DISABLE` 不使合法 UB 驻留失效，也不是本条的必改项；NORMAL 不能替代 UB 原值保留证明。不要由逻辑删读量直接计算 HBM 收益或加速比。

## 有界 Ascend C 实现：真实两消费者，含短尾

本例仅实现既定 `tmp=float(scale*x); y=float(tmp+x)` 两步 FP32 语义；**不改成 `(scale+1)*x` 或 FMA**。`scale` 是本 workload 冻结的只读标量。xGm/yGm 绑定 C2 已分配给本核的连续、互不重叠区间，输入与输出无别名，输出唯一归本核，C2 分核起点和非末核终点均为32B边界，最后一个有效 owner 才可写非32B尾部，已核验目标搬出物理粒度不会与邻核冲突；外层任务分配由 P 的 `planning.elementwise.continuous` 给出。该例不覆盖广播、非连续输入、跨核或原地输出。

包含 `kernel_operator.h`，在当前 kernel 的类中增加以下成员与方法；Host 已确认 `ownerLength`、`T` 为 uint32 范围元素数，`T>0`、`4*T<2^21`、`slotBytes=AlignUp(4*T,32)` 且全部分配容量足够。`xBase/yBase` 是已经加上本核起点的合法 GM 指针。空输入由 Host 分支直接返回。Init 在本 kernel 初始化阶段只调用一次，不能放进热循环；使用一个 TPipe 管理这些 buffer，不与工程另一套同址手工分配叠加。

```cpp
AscendC::TPipe pipe;
AscendC::TQue<AscendC::TPosition::VECIN, 1> inQ;
AscendC::TQue<AscendC::TPosition::VECOUT, 1> outQ;
AscendC::TBuf<AscendC::TPosition::VECCALC> tempBuf;
AscendC::GlobalTensor<float> xGm, yGm;
uint32_t ownerLength, tileElements;
float scaleValue;

__aicore__ inline void InitReuse(
    __gm__ float* xBase, __gm__ float* yBase,
    uint32_t length, uint32_t T, uint32_t slotBytes, float scale) {
    ownerLength = length; tileElements = T; scaleValue = scale;
    xGm.SetGlobalBuffer(xBase, length);
    yGm.SetGlobalBuffer(yBase, length);
    pipe.InitBuffer(inQ, 1, slotBytes);      // 每槽字节；一物理槽
    pipe.InitBuffer(outQ, 1, slotBytes);
    pipe.InitBuffer(tempBuf, slotBytes);
}

__aicore__ inline void ProcessReuse() {
    auto tmp = tempBuf.Get<float>(tileElements); // 元素，不是字节
    uint32_t pos = 0;
    while (pos < ownerLength) {
        const uint32_t remain = ownerLength - pos;
        const uint32_t n = remain < tileElements ? remain : tileElements;
        AscendC::DataCopyExtParams cp{};
        cp.blockCount = 1;
        cp.blockLen = n * sizeof(float); // 有效字节；不向上读/写 GM
        cp.srcStride = 0; cp.dstStride = 0; cp.rsv = 0;
        AscendC::DataCopyPadExtParams<float> pad{false, 0, 0, 0.0f};

        auto x = inQ.AllocTensor<float>();
        AscendC::DataCopyPad(x, xGm[pos], cp, pad); // GM -> VECIN
        inQ.EnQue(x);
        x = inQ.DeQue<float>();                    // 输入就绪
        auto y = outQ.AllocTensor<float>();
        AscendC::Muls(tmp, x, scaleValue, n);       // 第一个真实读者；不改 x
        AscendC::PipeBarrier<PIPE_V>();
        AscendC::Add(y, tmp, x, n);                // 第二个真实读者仍用原 x
        AscendC::PipeBarrier<PIPE_ALL>();          // 保守等待最后 Vector 读完成
        inQ.FreeTensor(x);                        // 此后才允许覆盖输入槽
        outQ.EnQue(y);
        y = outQ.DeQue<float>();
        AscendC::DataCopyPad(yGm[pos], y, cp);      // VECOUT -> GM，写 n 个元素
        AscendC::PipeBarrier<PIPE_ALL>();          // 保守等 MTE3 读完 y
        outQ.FreeTensor(y);
        pos += n;
    }
}
```

代码使用 A2/A3 API 文档明确支持的无 mode DataCopyPad，输入位置为 VECIN，输出位置为 VECOUT；没有使用 950 Compact、NDDMA、RegBase/VF 或 GM→VECCALC 扩展。`blockCount=1`，无行间 stride，尾块 `cp.blockLen` 仍为有效 n*4，UB 槽按最大 T 对齐分配。`isPad=false` 不保证 dummy 是0；这里只对 n 个有效元素计算，不能让其它算子把 dummy 当作归约单位元。

这是与既有 kernel 接口拼接的实现片段，未提供 Host 注册/tiling/启动框架，也未在目标 SDK 编译。S8 的第56/66行明确 PIPE_ALL 阻塞全部流水，等待本核所有先前提交的接口完成；不是只插一个 PIPE_V 顺序点，也不是核间栅栏。两处 PIPE_ALL 故意给出保守完成顺序，不展示双缓冲或流水重叠，不证明最终性能；实际工程可沿用已有合法队列/事件协议缩小同步范围，但必须保留“输入最后读完成→下次 MTE2 写输入槽”和“MTE3 读输出完成→下次 Vector 写输出槽”两条依赖。不能直接删 barrier 就声称有 overlap。实际 API 重载/目标 SoC/SDK 不匹配则保留原实现并补证。

## P_KEEP、重规划和组合边界

P_KEEP 只在已有完整计划许可本次 owner 内输入原值存活期、tile、现有通路和资源内的实现选择时成立；必须引用原计划身份和自由度。它不表示“P 没有可用文档”。同 owner 两消费者可在已有 continuous 计划下保留 x；原计划没有输入延长驻留许可或容量未知时，先由 C2 条件化分析，不能自己构造 KEEP。

以下任一超出原自由度就返回 C2：把分离消费者迁到一个 owner、改任务/dispatch 域、改变归并或同步拓扑、扩大融合 region、跨核/跨 C/V 通路、增加 workspace 所有者、改变 tile/常驻额度或预取槽数。C2 可重选 continuous/broadcast/under-fusion 等现有模板；需要 Cube 小侧驻留则选 matmul resident，C3 不拿本 UB recipe 改其存储层。

可与 buffer-lifetime 配合：先保证 x 仍活，再让已经结束的其它临时值共享空间，不能把 x 本身提前覆写以凑容量。与连续合并配合时，先保留访问几何边界，合并相邻请求只减少发射，删重复原值才减少逻辑读；分别记账。L2 策略可以用于仍然必须读取的其它输入/跨 owner 的共享副本，本 owner 消除的那次重读不能再计一份 L2 命中收益。Vector 链组合先由 C2 确认数学边界；本条既不自动授权融合，也不自动改变 Cast。

## 无硬件审阅与未来验证点

纸面回放应覆盖以下不同结论，不能只验证一条成功路径：

- 两消费者同区间、同原值、同 owner 且容量闭合：可给出本条及计划/代码范围；记录删哪一次搬运、保留哪两个计算消费者。
- 只有两个 DataCopy、第二份从未被计算消费：登记无用搬运；不能把它当成输入多消费者驻留的实现证据。
- 第一消费者原地破坏 x、API 隐式 source-reuse、别名 DMA 或并发写改 GM：当前 `input_value_preserved` 不成立或 unknown，保留重读/请求新计划和保存方案。
- 地址相同但第二阶段本应看新版本；地址相异但计数字节相同；一边读尾有效 n、另一边读补齐长度：不能直接删除第二读。
- 复用跨 owner、不同 dispatch、不同 expert/shape/布局代次：本地 UB 不共享或旧值失效；先由 C2 明确边界。
- 容量未知/不足、输入保留使原 ping-pong 被覆盖、静态 x2 分配未删除：不能授权实施；C2 分析缩窗口、保留重读或其它合法计划。
- 原读量已是必要最小值、R=1：本方法没有删读依据；带宽高也不生成重复输入事实。
- `CACHE_MODE_DISABLE`、NORMAL 高命中、未知 HBM 数据：只说明相应缓存条件；不能阻止合法 UB 原值复用，也不能凭逻辑 GM 删读断言 HBM 和时延变化。
- 长度为0、1、T−1、T、T+1、多 tile、最大偏移，保留每个输出唯一写者；数值按当前 oracle 的 NaN/Inf/±0、舍入和溢出合同检查。

后续若做硬件验证，观察实际走到的分派分支、输出正确性、GM 请求字节与次数、HBM/L2、UB 静态分配及 Task/timeline；本条不提供未经测量的性能收益、通用阈值或瓶颈定论。Action 可实施性与 Problem 成立与否分开记录，容量不合法不反证“原输入重复载入”机制。

## 固定来源与知识声明

以上操作方法、八项门禁、容量/流量推导和两消费者残差片段是**本次工程归纳**；其合法性仍需当前实现和目标 SDK 证明。来源只支撑下列有界事实：

- S1（sources 第1项）Add 的 Host 固定核数/整除输入及 kernel 队列代码，证明 VECIN/VECOUT 的初始化、搬入→计算→搬出编程形态；本条的核内 tile/短尾和双消费者是新增归纳，不把该样例全载/8核当作当前规划。
- S2/S3（第2/3项）InitBuffer/Get 明确每槽分配长度单位为字节、队列物理 num、Get 长度为元素且不得超分配；它们不证明当前 UB 容量足够。
- S4/S5（第4/5项）DataCopyPad 的 A2/A3 产品表、无 mode 原型、GM→VECIN/VECOUT 和 VECIN/VECOUT→GM 通路、有效字节与对齐/stride 约定，是本条短尾搬运依据。GM→VECCALC 文档仅对950列支持，本条不采用。
- S6（第6项）GELU kernel 的2201分支在246–274行多次只读 xLocal，并将原值保留到最后 Div；562–613行展示搬入、V读者及反向完成边；691–746行 Host 的 NPU_ARCH 分派说明其实际 shape/核数。它只直接确认“源数据多消费者和最后读者”的实现事实，不把其 GELU 近似改成当前业务公式，不迁入3510路径。该样例手工 VECCALC 视图与 DataCopyPad 通路标注存在差异；本文遵从 S4/S5 的明确通路，不能以样例替代 API 核验。
- S7（第7项）SetL2CacheHint 说明 NORMAL/DISABLE 和产品边界；不支持把 cache hint 解释为 UB 驻留或保证命中。
- S8（第8项）PipeBarrier 文档的 A2/A3 支持表及第56/66行，明确 PIPE_ALL 阻塞所有流水并等待已提交接口完成。本文仅将其用作本核保守完成边，不作为跨核同步或可重叠发射的证据。

所有 source 的固定修订、完整文件 hash、行区间及摘录 hash 见 frontmatter；源码与原许可已随包保留，无需读取上游仓库或外部目录才能使用本条正文。当前状态为来源审读，未进行目标 SDK 编译或 NPU 实测。
