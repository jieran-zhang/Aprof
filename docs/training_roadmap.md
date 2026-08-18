# AProf 后续训练方向与训练方法

本文给出 AProf 从当前 expert-seeded SkillGraph 走向可验证后训练系统的实施路线。它描述工程训练协议，不替代论文 proposal；“已实现”和“后续能力”在文中明确分开。

## 1. 当前基线与边界

当前 `skillgraph/versions/v0001` 是由静态知识确定性编译得到的专家种子，不是从数据中归纳出的完整 taxonomy。runtime 已实现：

- 严格 contract、不可变 graph snapshot、route replay 与 graph/policy 兼容性检查；
- candidate gate、配对 timing 统计、CAS artifact 校验和 append-only EpisodeStore；
- 固定图上的 `fixed_graph_shrunk_edge_bias_v1`，只调整 `problem_to_skill_prior` edge bias；
- 对 graph version/hash、producer/source hash、measurement quality、behavior propensity 和 verdict eligibility 的过滤。

当前算法的语义是“根据机器 gate outcome 做观察性 edge 更新”，不能宣称为 transformation 的因果效果估计。以下能力尚未实现：自动增删或拆合 mechanism node、学习 handler 参数或自由 patch policy、完整 contextual bandit/IPS/DR、外层 graph-edit RL，以及跨 SoC 的性能迁移。

## 2. 后续训练方向

### 2.1 P0：固定图 edge ranking

近期主线是在 graph、skill contract 和基础模型冻结时，学习不同 context 下 transformation 的优先级。训练信号只来自 machine gate：

- `production_safe_gain` 是正向信号；
- `stable_no_gain`、`heldout_regression` 及显式启用的 build/accuracy/runtime failure 是负向或停止信号；
- `measurement_inconclusive`、provenance 不完整和 graph/hash 不兼容的 episode 不进入性能更新；
- simulator-only 记录只能训练 feasibility/proposal，不训练 production performance value。

第一阶段保持线性 edge bias、小更新幅度、support shrinkage 和最小样本约束。只有在 operator-disjoint validation 上稳定获益后，才增加 context interaction 或小型 MLP。

### 2.2 P1：证据质量与采集策略

该方向学习“下一份最值得采集的证据”，而不是直接学习性能结论：

- 根据 mechanism ambiguity 选择最小 metric bundle；
- 在 cheap timing、完整 msprof、simulator proxy 和源码/tiling 证据间做成本敏感选择；
- 缺失 counter 保持 `unknown`，不填成零或负证据；
- 以信息增益、novelty、edge coverage 和硬件预算决定 full profile 候选。

生产收益仍由至少 30 个交错 AB/BA timing pairs 和 runtime gate 裁决。完整 msprof 用于机制指标，不替代配对 timing。

### 2.3 P2：mechanism graph 归纳与版本演化

图结构只在 phase boundary 更新，并与 edge training 分开。候选结构来自 source/tiling、workload/容量、归一化 profiler symptom，以及同一 intervention 在多个 operator/shape 上的 response。

允许 add、split、merge、refine 和 deprecate。LLM 或聚类器只提 proposal；发布新图必须在独立 operator groups 上通过 graph-version gate，满足路由或端到端收益改善、关键 shape 无回退、复杂度受控、bootstrap 稳定且无 operator-name 泄漏。每轮只提交少量高置信编辑，已发布 snapshot 不原地修改。

### 2.4 P3：handler 与参数学习

当前 `handler_attempt` 只是 shape-validated sidecar，不具备 EpisodeStore/CAS attestation，不能作为正式 policy-training input。学习 tile、buffer、blockDim 或 API variant 前，必须补齐：

1. 参数空间与 hard constraint 的版本化 contract；
2. attempt、patch、build、correctness、timing 和 provenance 的统一 attestation；
3. transformation 内部的 parameter behavior probability；
4. 与 edge policy 分离的 offline optimizer 或小型 bandit；
5. held-out shape 与 portability gate。

### 2.5 P4：跨 operator 与跨硬件迁移

先验证 operator-disjoint transfer，再扩展 hardware-disjoint transfer。跨 SoC 训练要显式加入容量、核数、频率、带宽和 toolchain fingerprint，并区分硬件无关 correctness、可归一化 mechanism evidence 和 SoC 专属性能 value。只有单一 SoC 数据时不报告跨硬件泛化。

## 3. 数据组织与隔离

### 3.1 统计单位

- `task`：固定 operator、baseline、shape 集合、SoC 和预算；
- `candidate transition`：一次 route、一个 atomic transformation 和 gate evidence；
- `episode`：绑定 context、完整 route candidate set、behavior probability、graph/policy、候选、全部 gate evidence 和 terminal outcome 的训练单位。

报告至少同时给出 operator、task、episode、candidate transition 和有效 edge support，不能用 JSONL 行数或 profiler 文件数代替训练规模。

### 3.2 数据来源

训练起点分四类：

- natural：自然存在性能空间且 correctness 已确认的 kernel；
- single-fault injection：单因素、语义保持、已验证 slowdown 的注入 case；
- rewind：从已验证优化回退一个原子变化；
- no-harm control：接近合理实现，用于学习 NOOP 和防回退。

Injection recipe、隐藏 label 和 variant 名只允许离线 dataset adapter 使用，禁止作为在线 diagnosis 或 route evidence。注入 case 仍需独立通过 correctness、slowdown、lineage 和 leakage gate。

### 3.3 数据集划分

按 operator task 划分，所有 shape/case 跟随同一 operator：

- `D_train`：采集 episode、更新固定图 policy、提出结构候选；
- `D_validation`：选 checkpoint、调预算和停止，不进入当轮 policy 更新；
- `D_test`：冻结 graph、policy、prompt、model、seed 和预算后一次性评测。

仓库内的冻结清单位于 `benchmarks/cannbench/{train,validation,test}/`，用
`python3 benchmarks/cannbench/validate_splits.py` 检查成员互斥、覆盖和摘要一致性。
算子源码与小型 correctness summary 可以入库；build、case 二进制和 profiling
树必须留在 Git 之外。

语义近邻算子需要显式标注，不能把相同机制族的近邻误称为严格 OOD。

### 3.4 Episode 准入条件

正式训练只读取完整校验的 SQLite EpisodeStore。每条记录必须满足：

- graph version 与 canonical graph hash 精确匹配；
- behavior checkpoint（如使用）可验证，候选集与 propensity 可 replay；
- baseline、candidate、patch、producer 和 evidence 已进入 CAS 且 hash 可重算；
- append-only chain、episode attestation 和 gate replay 通过；
- runtime build、producer hash、measurement、scope、semantic、portability 和 verdict 满足训练配置。

Legacy flat memory、原始 JSON/JSONL、历史展示数据、未 attested handler attempt 和 Git 中的 msprof dump 都不是 production policy 训练输入。

## 4. 固定图训练方法

### 4.1 Phase A：冻结发布清单

训练前冻结 graph/hash、runtime/schema/gate/skill、model/prompt/toolchain、数据 split、候选与 profiling 预算、探索策略与 seed、policy config 和负样本 utility。任一项变化都产生新的 run manifest。

### 4.2 Phase B：带覆盖约束的采集

route 使用 expert prior 与最小探索概率的混合策略，并记录真实 behavior probability。调度按 operator group 平衡，避免 elementwise、大 shape 或易优化任务主导数据。

```text
schema/precondition
  -> static/capacity review
  -> build
  -> full correctness
  -> runtime safety
  -> paired cheap timing
  -> selective full msprof
  -> held-out shape/scope/portability
  -> episode finalize
```

失败在首个 mandatory gate 处停止，但保存为 typed negative episode。每个 candidate 只承载一个 atomic transformation，避免 reward 无法分配。

### 4.3 Phase C：校验与过滤

训练前验证 episode、artifact 和 policy checkpoint：

```bash
aprofctl episode verify --store <episodes.sqlite>
aprofctl artifact verify --store <episodes.sqlite>
aprofctl policy train --graph skillgraph/versions/v0001 \
  --episodes <episodes.sqlite> --policy-version <pXXXX> \
  --output <checkpoint.json>
aprofctl policy validate --checkpoint <checkpoint.json> \
  --graph skillgraph/versions/v0001
```

具体参数以 `aprofctl --help` 为准。training summary 必须报告输入记录数、有效 episode、实际训练 episode、更新 edge 数和所有 skip reason。

### 4.4 Phase D：保守 edge 更新

当前实现对可训练 edge 聚合经过裁剪的 outcome signal，可选用记录的 propensity 做有上限的重要性加权；低于 `min_support` 时 bias 为零。有效 signal 经 shrinkage 和最大 bias 约束后叠加到 expert prior。

checkpoint 的正确解释是“当前数据和行为策略下，机器 gate outcome 支持的保守排序修正”，不是因果贡献。升级顺序建议为：

1. 增加少量可审计 context interaction；
2. 做 overlap 检查和 group-balanced replay；
3. propensity 可靠时增加 IPS sensitivity；
4. 覆盖充分后评估 doubly robust 或 contextual bandit；
5. 始终保留 expert-prior、uniform、no-learning 和 oracle-budget baseline。

### 4.5 Phase E：验证与发布

operator-disjoint validation 至少评估：

- Correct-Speedup@固定候选/编译/profiling 预算；
- geometric mean speedup 与 log-speedup bootstrap confidence interval；
- accuracy/build/runtime/regression escape rate；
- route top-k recall、MRR、NDCG、NOOP precision；
- full-profile 次数、NPU 时间和提前停止节省；
- edge effective support、policy KL、相邻 checkpoint top-k Jaccard。

只有收益置信下界为正、correctness 不下降、关键 shape 无回退且 policy drift 可控时才发布新 `policy_version`，否则保留上一版并记录失败 run。

## 5. 图结构训练方法

图结构训练采用两时间尺度：phase 内固定图只训练 edge；phase boundary 冻结 edge 再提出结构编辑。

1. 从 verified episodes 构造 missing-view-aware feature table。
2. 用多初始化、operator-group bootstrap 和有限 mixture/consensus clustering 提 proposal。
3. 检查候选是否有可解释 predicate、跨 operator support 和差异化 response。
4. 在 production graph 外执行 targeted disambiguation interventions。
5. 用独立 discovery/acceptance operator groups 运行 graph-version gate。
6. 通过后编译新 immutable snapshot；失败 proposal 不污染生产图。
7. 新图 policy 从 expert prior 或父节点 support 加权 warm-start，再跑固定图训练。

首轮只验证一个有充分 response heterogeneity 的 split，或一个有充分 equivalence evidence 的 merge，不同时开放自由结构搜索。

## 6. 推荐里程碑

### M0：数据可信

- 至少 6 个 training operators、2 个 operator-disjoint validation operators；
- natural、single-fault、rewind、no-harm 均有覆盖；
- 所有训练记录通过 CAS、gate replay、chain 和 provenance 校验；
- raw build/msprof 产物只在 artifact store 或 `<op_dir>/.aprof/`，不进入 Git。

### M1：固定图学习有效

- 核心 trainable edges 至少 80% 达到预设 effective support；
- 同时观察正向、负向或替代结果；
- learned checkpoint 在固定预算下优于 expert-only、uniform 和 no-learning；
- 连续 checkpoint 的 validation 指标和 route 稳定性达到停止条件。

### M2：采集成本下降

- Correct-Speedup 不下降时减少 full msprof 次数或 NPU 时间；
- inconclusive、missing-artifact 和 measurement retry rate 可量化下降。

### M3：发布首个演化图

- 完成一个可复现 split 或 merge；
- discovery、disambiguation、acceptance 数据隔离；
- 新图通过复杂度、泄漏、稳定性和端到端 gate；
- graph lineage、snapshot hash、policy compatibility 和 rollback 完整。

## 7. 每轮训练检查表

- [ ] graph、policy、runtime、schema、skill、model、prompt、toolchain 和 split 已冻结。
- [ ] behavior candidate set、hard masks、selection mode/seed 和 propensity 已记录。
- [ ] baseline 只读，每个 candidate 只有一个 atomic transformation。
- [ ] build 后先跑全量 correctness，再进入 timing/profile。
- [ ] production gain 使用至少 30 个交错配对样本，full msprof 与 timing 分开。
- [ ] simulator、injection label 和 legacy memory 未进入 production reward。
- [ ] EpisodeStore、CAS、hash chain、gate replay 和 provenance 全部通过。
- [ ] train、validation、test 没有 operator task 泄漏。
- [ ] checkpoint 已与上一版比较收益、正确性、回退、成本和 policy drift。
- [ ] 未过门槛的 policy/graph 未覆盖当前稳定版本。

更完整的研究动机、公式和实验设计见根目录 `AProf_DAC_Proposal.md`；当前 decision surface 限制见 `docs/skillgraph_decision_surface.md`。
