---
schema_version: aprof.knowledge-record/v1
id: implementation.scalar-control.hot_loop_address
kind: recipe
version: 1.1.0
status: active
title: 标量热循环地址外提与首主尾分离
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
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/scalar/guide.md
  original_path: ops/ascendc-performance-best-practices/references/common/scalar/guide.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 33
  sha256: sha256:1f9161d4bdd0ed256130213ce0e61598369c869b00ce28d54db38f5860536fdc
  excerpt_sha256: sha256:1f9161d4bdd0ed256130213ce0e61598369c869b00ce28d54db38f5860536fdc
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
- address-arithmetic
- loop-invariant
- scalar
seed_reason: 审读五个固定开源修订中的直接来源，以中文提炼实现契约；保留旧 ID 含义，不承诺目标 SDK 编译结果或 NPU 性能收益。
parent: implementation.scalar-control
references:
- implementation.precision-boundaries.bounds
- implementation.scalar-control.constant_lifetime
- implementation.scalar-control.tilingdata_access
evidence_status: source_reviewed_not_benchmarked
---

# 标量热循环的地址外提与首主尾分离

## 原理与进入条件

地址乘除法、成员重复读取、首尾判断和隐式多维迭代状态机可能消耗 Scalar 发射预算；若编译后仍存在重复工作且延迟了 MTE/Cube/Vector 发射，才可能成为关键路径。包内来源与当前源码中的重复结构可以支持提出优化候选，无需先完成严格性能实验；但源码次数不等于编译指令次数，也不等于实测热点。目标 trace/反汇编用于区分等待其他流水、真实Scalar指令工作、CSE已消除及spill等竞争解释；缺这些资料时写清具体未知与决策影响，不能统一否决候选，也不能将其直接标成已确认瓶颈。Scalar占比高不证明spill，更不授权删除事件。

实施硬条件是原地址/有效域、溢出、数值顺序、控制副作用及buffer/事件生命周期合法。C2必须已确认遍历顺序、每核输出所有权、tile大小和同步关系，本条仅在该计划许可自由度内等价实现同一任务序列。热点证据用于判断试验价值和检验性能预测，不替代上述安全证明。

适合连续 tile、规则 KV 页内段或固定 K 主循环；循环次数很少、路径本来已常量折叠、地址依赖动态 page table/稀疏索引时收益不确定。`head/group/blockSize/stride` 只有在当前循环域内不变才外提；跨 head、跨 batch、prefix 切换或跨页时须重新计算，不能把局部不变量提升到 kernel 全局。

## 实施步骤与代价

1. 写出原地址：例如元素偏移 `base + tileIndex*step`，逐项标注单位、更新维度和所有权。Host 以足够宽整数证明乘加不溢出、最后访问元素小于分配长度，再把不变乘积和公共基址放到最小共同外层。
2. 主循环用地址递增代替每轮重新乘法；输入和输出的 dtype/物理 stride 不同就分别递增，不能共用一个字节偏移。paged KV 应按每页合法片段重启递增，绝不能跨页按物理连续推导。
3. 对 `tileCount=0/1/2` 单独推演，再拆首块、常规块、尾块。首块初始化一次，尾块的有效长度和 final flag 只执行一次；既是首块又是尾块的单块必须同时满足两种语义。
4. 周期搬运可以外层按段循环、内层处理纯常规块。段边界的 `WaitFlag/SetFlag` 仍按原 producer/consumer 关系执行；不能用“零分支热循环”作为改变同步或 K 累加顺序的理由。
5. 若将 `while(Next())` 改成显式多重 `for`，先列完整的旧 tile 序列与新序列做相等检查，包含各维 tail、空任务和跳过的 tile。编译器对显式循环可能更易优化，但专用循环硬件、展开方式和收益由目标编译结果确认。

假设迭代 `L` 次、每次可外提 `p` 个乘/除与 `q` 个成员 load，理想减少约 `(L−1)×(p+q)` 个标量操作；实际还增加若干递增、首尾代码和额外活跃标量。首尾分离把判断数量由 `O(L)` 缩至边界数量，却可能扩大指令体积。比较反汇编中的乘除/分支/load、栈与 spill，以及 Task 时间；循环短或展开过多导致 ICache 压力时保留原循环。

选择前将该估算与当前case的必要Vector/搬运工作、逐元素地址解码、tile数和其他机会比较。少量字段缓存不能因为容易证明等价就自动优先；若重复load已被编译器消除，相关预测已被削弱，应降低优先级或转向尚未解释的成本。缺反汇编时，可在结构明显、代价有界且比较理由充分的情况下试验，并把“编译后指令是否减少”列为待验证预测。R2应对照R1实际patch与有效结果解释继续本机制能学到什么；单次总时间无收益可能否定优先级，也可能因计时无效而无法判断，均不能直接宣布机制已证伪。

## 地址递增的上下文片段

下例是纯地址调度骨架，`tileCount` 为本核有效 tile 数，`stepElements` 为每 tile 的输入元素跨度，`beginElements` 为输入首元素偏移；三者为 Host 检查过的 `uint64_t`。`body` 是调用处提供的原 tile 操作，签名为 `(tile索引, 元素偏移, 是否首块, 是否尾块)`，内部保留原搬运、计算、事件及有效长度逻辑，不依赖捐赠仓库的私有 helper。

```cpp
template<class Body>
__aicore__ inline void VisitTiles(uint64_t tileCount, uint64_t beginElements,
                                uint64_t stepElements, Body body) {
    if (tileCount == 0) return;
    uint64_t offset = beginElements;
    body(0, offset, true, tileCount == 1);
    if (tileCount == 1) return;
    offset += stepElements;
    for (uint64_t i = 1; i + 1 < tileCount; ++i) {
        body(i, offset, false, false);
        offset += stepElements;
    }
    body(tileCount - 1, offset, false, true);
}
```

这里 offset 单位是输入元素，若原路径接收 byte 地址，应在外层按输入 `sizeof(T)` 转换，检查后再使用；此骨架不授权扩大 GM 搬运、改变尾部 count 或提前释放 buffer。K 循环的首块 `cmatrixInitVal`、尾块 unitFlag 与 Fixpipe 仍依各自 API 契约配置。

## 数值、失败与平台边界

遍历次序保持不变时，本条应保持运算序列和可见舍入；若重排 tile 导致 reduction/atomic 顺序改变，已越过本条范围，回到 C2 与精度边界评审。验证零 tile、单 tile、两 tile、整除/非整除尾、最大地址、跨页和全部 feature 分支；输出区间与访问序列必须一致。第一块重复初始化、最后一块漏发 event、空循环产生 `tileCount−1` 下溢、循环内 `const` 实际随 head 变化都是撤回信号。

来源事实：通用 scalar 编码原则给出主尾分离、显式循环和局部变量的机制；arch22 FA 文档明确允许公共 workspace 前缀、stride 预乘、热点字段和首主尾分离，同时排除 A5 百分比阈值及性能数字。上面的访问序列守恒、操作数估算及安全/性能分层是本次工程提炼；来源没有证明当前任务的Scalar主导或优化收益。适用范围为 arch22/A2/A3 与 arch35/950 上的通用 C++ 等价改写，目标分别编译验证；本条不向 A3 引入 VF、RegBase、SIMT 或 arch35 专属指令。
