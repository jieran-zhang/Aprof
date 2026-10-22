---
schema_version: aprof.knowledge-record/v1
id: implementation.tiling-tail.example.exp-tile8192
kind: example
version: 1.1.0
status: active
title: exp 在固定并行划分内将 tile 从4096增至8192
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/wiki/exp-tile8192.md
  original_path: wiki/exp-tile8192.md
  revision: aprof-1.1.0-pre-governance:sha256:90ca5ffa91371300bb62cf53e6b6e6fe8ba73385ea72cd8401d23f39467dde2f
  lines:
  - 1
  - 119
  sha256: sha256:90ca5ffa91371300bb62cf53e6b6e6fe8ba73385ea72cd8401d23f39467dde2f
  excerpt_sha256: sha256:90ca5ffa91371300bb62cf53e6b6e6fe8ba73385ea72cd8401d23f39467dde2f
- path: workflows/migration/archive/wiki/index.json
  original_path: wiki/index.json
  revision: aprof-1.1.0-pre-governance:sha256:dca7200b4542b6e6e54e51d956407a67d3a7b300e255cab77ac97e6932294c0b
  lines:
  - 1
  - 388
  sha256: sha256:dca7200b4542b6e6e54e51d956407a67d3a7b300e255cab77ac97e6932294c0b
  excerpt_sha256: sha256:dca7200b4542b6e6e54e51d956407a67d3a7b300e255cab77ac97e6932294c0b
- path: workflows/migration/archive/wiki/evolution.jsonl
  original_path: wiki/evolution.jsonl
  revision: aprof-1.1.0-pre-governance:sha256:080bde3fc3eb67514d9075453b78f20c1d12dbd48f6db4f48407187da65917f4
  lines:
  - 1
  - 15
  sha256: sha256:080bde3fc3eb67514d9075453b78f20c1d12dbd48f6db4f48407187da65917f4
  excerpt_sha256: sha256:080bde3fc3eb67514d9075453b78f20c1d12dbd48f6db4f48407187da65917f4
learning: {}
tags: []
seed_reason: 从已绑定的包内历史档案、索引和演化记录补足中文案例正文；保留原协议、失败与适用边界，不迁移历史性能资格。
parent: implementation.tiling-tail
references: []
evidence_status: source_reviewed_not_benchmarked
---

# exp 在固定并行划分内将 tile 从4096增至8192

## 方法、范围与资源

本历史实例只改变exp实现的`tileElements`：从4096元素增到8192元素。算法、算术、block数、任务/输出所有权、base/scale/shift、dtype转换与动态尾部均保持原契约。历史验证范围为910C/A3、CANN9.0.0上的非空FP16、BF16、FP32输入；950、其它SDK、其它实现及其它算子不继承此资格。

作用方向是减少同一有效区间的tile次数，从而摊薄逐tile搬运/标量设置；有效读写总量和数学元素数不应减少。原candidate的显式UB为FP16/BF16路径98,304字节、FP32路径65,536字节，且检查了SDK临时区与地址边界。这是该实现的实际资源记录，不是任意exp都可套用的预算公式。新工程必须按真实静态分配、队列物理槽、dtype转换区和API预留重算。

下面是本文归纳的索引检查，L、T和offset均为元素数：`loops=L/T+(L%T!=0)`，每轮`valid=min(T,L-offset)`。只将T改为8192，不增加GM有效长度；UB对齐容量与GM有效count分别计算。原合同为非空输入，零输入是否支持须由当前C2与oracle明确，不能从本例推定。

## 原拒绝和停止记录

2026-10-14首轮中两侧各通过20个声明case和42个额外边界，但同源A/A的case3、9角色偏差为2.4353%、3.6243%，超过原先2%门槛；在候选正式计时前停止，没有正式性能或机制准入。第二轮只做baseline对自身的协议诊断：case9总体偏差16.9615%、两个周期14.2769%与19.5621%，case14第一周期2.7587%，仍未通过。候选验收没有在该轮运行，这两次控制失败不是tile候选回退证据。

2026-10-15首次Task v5在审查预算处停止：累计15,836 token超过原先8,000，实际退出2，未构建、未采硬件数据、未形成审查结论；这是流程拒绝。后续同一候选完成审查、一次构建、完整正确性和正式采集后，原任务又因PMU verifier的stdout/stderr混合解析失败退出2；补采阶段也因证据适配器登记缺陷退出2。原失败和耗时均保留，没有以重建或增加正式计时样本抹去失败。

## 仅限原实例的最终验收

按原授权从已验证中间状态继续，逐一绑定源码、二进制、输入和协议，复用20-case×30对正式Task Duration、完整20-case正确性与42项额外边界及前后A/A/逐周期控制；保留baseline的5次PMU，仅补candidate10次预热和5次采集。修复证据适配器后，另一次只执行门禁的任务退出0，机器结果为`production_safe_gain`。

原协议等case几何平均加速为1.188572×，bootstrap95%下界1.188203×；没有回退case，最小耗时降低约4.184%。指标是完整调用设备Task Duration，Event/Host不参与该判定。预登记PMU case3为BF16、shape=[4096,4096]、base=-1、scale=2、shift=0，五次baseline/candidate MTE2指令计数分别均为87/44，与tile次数减少一致；单个计数不证明其它shape或算子会获益。

历史晋升回执为`sha256:33be3448ee471db6899fa9278dc1524fdf7b073ee6ee44425f93c5752c95095c`，正式报告为`sha256:642649af6a241679362f66039a40e35aef3d49b3adae5685113ccca51a2bfc89`。历史validated仅限上述exp实现/输入合同/910C A3/CANN9.0.0，当前条目继续使用来源审读状态；本次没有新硬件验证。综合tile-amortization、sigmoid等仍未随之晋升，45次validation比较和封存后test sweep未运行。

## 新应用的失败边界

C2必须已允许tile范围；C3只实现该范围内的buffer、循环和尾部。大tile超UB、挤掉已有流水、增加Vector开销或使Task回退时，在许可范围内恢复原tile；需改变算法、核划分或所有权则回C2。验证原全量case和对应边界，不沿用其它候选的旧正确性。8192不是通用最优值，原来20×30对、A/A和置信区间门槛只描述历史协议，新应用使用当前协议独立评价。

[完整历史档案](../../../../../../workflows/migration/archive/wiki/exp-tile8192.md)及绑定索引/evolution保留逐case表、来源哈希、三个进程退出、失败成本和完整适用边界。本页不把这些历史倍率迁移为当前候选性能承诺。
