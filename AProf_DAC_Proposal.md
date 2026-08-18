# AProf DAC 论文 Proposal

## 暂定题目

**AProf for Profile-Grounded Post-Training of Versioned Skill Graphs in Ascend C Kernel Optimization**

中文工作题目可写成《面向 Ascend C 算子优化的 Profile-Grounded 版本化 SkillGraph 后训练》

## 一句话概括

AProf 冻结基础大模型，把六个重叠的人工性能 family 降为 routing anchors，从多视图证据和已验证干预中归纳可演化的 mechanism nodes，在固定图版本内训练上下文边权，并让每次结构修改通过独立 profile validation 后再发布。

## 摘要草案

Ascend C 算子优化依赖硬件结构、workload shape、片上存储容量、数据搬运粒度和流水调度等多种因素。现有大模型可以生成代码和优化建议，却很难在资料稀缺的 Ascend C 生态中持续积累可靠经验。自由文本 memory 容易膨胀，静态 skill library 无法从执行结果中调整路由，直接依靠另一个大模型判断 skill 好坏又缺少可复现的证据。

本项目提出 AProf，一套面向 Ascend C kernel 的 profile-grounded 外部后训练系统。AProf 将性能优化知识表示为版本化 SkillGraph。现有六类性能问题只保留为非互斥的人工 routing anchors，不再被声明为完备且互斥的根因分类。图中的底层 mechanism problem nodes 从源码结构、workload 与容量关系、归一化 profiler 指标和已验证干预效果四类证据中形成。一个 mechanism 可以连接多个 anchor，无法由现有节点解释的记录进入 unknown buffer。在一个固定图版本内，AProf 只训练图的上下文相关决策边权，基础大模型、节点和 skill 内容保持冻结。每次候选优化都会经过隔离构建、正确性测试、交错配对 benchmark、profiling 机制校验和 held-out shape 回归。通过验证的成功与失败轨迹会被写成可追溯的 verified episodes。阶段结束后，系统根据累计证据提出节点新增、拆分、合并、细化和退役方案。结构修改只有在独立 shadow validation 中改善路由或优化结果，且通过稳定性与复杂度约束后，才会形成新的不可变图版本。

针对低资源数据问题，AProf 结合自然低效 kernel、单因素性能问题注入、已验证优化的 rewind，以及无故障 no-harm control，构造带 ground truth 和硬件证据的 Ascend C 优化数据。训练和图演化只使用内部 operator-disjoint 数据。外部评测使用 CANNBench 的公开算子规格和 evaluator，并为每个测试算子冻结一份所有方法共享的正确 seed implementation，使评测对象保持为 kernel optimization。论文将评估 AProf 在固定编译、profiling 和模型预算下找到正确且稳定加速方案的能力，并测量路由准确性、误接受率、回归逃逸率、硬件采集成本和图版本稳定性。

## 研究范围

DAC 版本只聚焦 Ascend C 和单一 Ascend SoC 测试环境。论文不声称完成跨硬件迁移，也不训练一个复杂的外层 LLM edit policy。当前目标有四项。

1. 建立由 anchors、evidence predicates 和可演化 mechanism nodes 组成的版本化 SkillGraph。
2. 在固定图上训练小型、上下文相关的可微边权模型。
3. 把 profile validation gate 实现为机器执行的状态机。
4. 用低资源 verified episode generation 支撑训练和评测。

Tenstorrent、SDA、跨硬件正迁移与负迁移，以及完整的 graph edit policy 留到后续工作。这个范围能保证 DAC 版本围绕一个完整系统问题展开，也能控制硬件实验成本。

# 1 研究动机与问题定义

## 1.1 现有 AProf 已经证明了什么

本 proposal 的代码判断基于 2026 年 8 月 11 日读取的 GitHub `main` 分支，commit 为 `3af2318`。

当前仓库已经形成一条可用的 agent workflow。`aprof-performance-workflow` 依次编排 diagnosis、profiling 和 optimization 三个阶段。系统目前用 tiling、data movement、pipeline parallelism、on-chip memory、AI Core utilization 和 API/algorithm inefficiency 六个宽泛 family 组织知识。它们之间存在明确交叉，例如 tiny-copy overhead 同时涉及 tiling 与 data movement，冗余 GM round trip 同时涉及 data movement 与 on-chip memory，低 blockDim 也可能同时涉及 tiling 与 AI Core utilization。因而这六个 family 适合作为工程导航入口，不能直接当成互斥根因标签。现有 contract 还能记录源码假设、profiling 计划、硬件 metric、候选优化策略、构建与精度状态、重复测量结果和成功失败 memory。

当前 candidate gate 也具备较好的安全边界。baseline 工程保持只读，每个 candidate 位于隔离目录，每次只应用一个 strategy。候选依次经过 static review、build、accuracy、repeated profile、measurement stability 和 correctness/generality gate。只有 `production_safe`、语义保持、测量稳定并且性能改善的候选，才允许进入 `best_op`。

仓库还提供 21 个性能问题注入 recipe，覆盖六类问题，并有 blind diagnosis input、deploy manifest、case validation 和 label alignment 工具。这些资产说明 AProf 已经拥有诊断知识、候选生成和硬件验证的基本流程。

## 1.2 当前缺口

现有 workflow 的主要控制逻辑仍写在 Markdown contract 中。三个 wrapper agent 负责输入输出规范化，尚无通用 runtime 负责 schema validation、profiling parser、gate 判定、episode 落盘、图版本管理和训练。`selected_as_best` 等关键字段仍可能由 agent 直接填写，缺少机器侧的最终裁决。

现有 memory 也较扁平。`optimization_memory.jsonl` 主要记录 operator、shape、SoC、problem family、strategy、before/after metric 和状态。它还不能回答一个训练系统必须回答的问题，包括当时使用了哪版图、走过哪些边、使用了哪个 skill 版本、行为概率是多少、候选 patch 和硬件产物如何复现。

数据规模同样有限。仓库中实体注入 case 主要来自 FastGELU、Mish 和 SwiGLU。FastGELU 的旧注入审计里，七个 baseline 与变体只有三个被标记为 active，另外四个存在弱标签或非单因素修改。现有 FastGELU 三轮优化展示了 258 倍加速，但最大收益来自 blockDim 等于 1 的病态 baseline。它可以证明系统能完整完成一次优化流程，不能单独支撑广泛的性能结论。

此外，部分旧文档和 `scripts/run_closed_loop.py` 仍引用已经移除的 `src/aprof` Python 包。marketplace、plugin manifest 和 `init.sh` 对 skills 与 agents 的声明也有漂移。这些问题应在训练系统开发前清理，否则同一 workflow 会因安装路径不同而获得不同能力。

## 1.3 核心研究问题

论文围绕四个问题展开。

**RQ1** 版本化、可训练的 SkillGraph 能否在相同候选、编译和 profiling 预算下，比当前扁平 skill library 更快找到正确且稳定的 Ascend C 优化方案。

**RQ2** 弱监督多视图证据与 profile-verified intervention response，能否形成比固定六类标签更稳定、更可行动的 mechanism problem nodes。

**RQ3** 真实 profiling 与候选验证形成的 verified episodes，能否训练出可泛化到未见 operator 的 symptom 到 problem、problem 到 action 路由。

**RQ4** profile validation gate 能否控制错误候选、偶然加速、benchmark specialization 和跨 shape 回归进入 skill library 的概率，并通过分层验证减少完整 msprof 次数。

# 2 核心设计原则

## 2.1 软参数和硬结构分开训练

SkillGraph 包含两类状态。

软参数包括图边 bias、上下文相关路由权重、skill 可靠性和不确定性。它们可以使用梯度训练。

硬结构包括节点、边、applicability predicate、skill contract、容量约束、验证规则和回滚策略。它们通过离散修改产生，并由 validation gate 决定是否发布。

因此，论文不会声称梯度直接修改自然语言。更准确的说法是，AProf 对外部 SkillGraph 的决策参数进行可微后训练，并对图结构执行验证后提交的离散演化。

## 2.2 Agent 提案，系统裁决

LLM 可以生成 diagnosis hypothesis、候选 patch、skill contract 或 graph edit proposal。最终裁决只能来自机器可执行的规则，包括 schema、capacity、build、correctness、runtime、repeated timing、profile metric、generality 和 portability。

一条候选即便 latency 下降，只要精度失败、测量不稳定、适用范围缩窄或 held-out shape 回退，就不能成为 production-positive episode。

## 2.3 Flow 和调用频率不等于贡献

一个 skill 经常出现在成功轨迹中，只能说明它获得了较多 reward-weighted support。AProf 不把调用次数或 flow mass 直接称为因果贡献。边的训练使用同一上下文中的相对决策价值，skill 的结构贡献使用 leave-one-edge、leave-one-skill replay 和硬件实测的条件效用。

## 2.4 每个版本都能复现和回滚

每次 episode 必须绑定 `graph_version`、`policy_version`、skill contract 版本、代码 hash、patch hash、模型与 prompt hash、CANN 版本、SoC fingerprint 和 profiling 产物 hash。旧节点不物理删除，只进入 deprecated 或 inactive 状态。结构变化和权重更新分别维护版本号。

# 3 系统总览

对一次 Ascend C 优化任务，定义上下文

\[
c=(o,\mathcal W,\mathcal H,\mathcal E_0,\mathcal B)
\]

其中 (o) 是 kernel 和 host tiling 源码，\(\mathcal W\) 是 shape、dtype、layout 和边界范围，\(\mathcal H\) 是 SoC、CANN 与片上资源信息，\(\mathcal E_0\) 是 baseline 的源码、workload model 与 profile 证据，\(\mathcal B\) 是剩余的候选、编译和 profiling 预算。

一次 candidate episode 形成如下路径。

\[
\text{context}
\rightarrow \text{observed symptom}
\rightarrow \text{problem hypothesis}
\rightarrow \text{optimization skill}
\rightarrow \text{parameterized candidate}
\rightarrow \text{gate outcome}
\]

这条图只描述一次候选计划的构造。候选执行后得到的新 profiling 结果会进入下一次 episode。这样可以保持单次候选图分层、有限且无环，避免把多轮 edit、profile、rollback 强行解释成一个 GFlowNet DAG。

# 4 Method I 版本化 SkillGraph

## 4.1 图结构

第 (k) 个图版本定义为

\[
\mathcal G^{(k)}=(V^{(k)},E^{(k)},M^{(k)},P^{(k)})
\]

其中 (V) 是 typed nodes，(E) 是 typed edges，(M) 是 hard masks 与 compatibility rules，(P) 保存 provenance、版本、状态和迁移记录。

图版本不可变。结构变化产生新的 `graph_version`。同一结构上的参数训练只增加 `policy_version` 或 `weight_revision`。

## 4.2 节点类型

### Context 节点

记录 operator family、shape、dtype、layout、SoC、CANN、源码摘要、workload model、baseline profile 和剩余预算。

### Symptom 节点

由证据谓词激活，例如 `blockDim` 远小于可用 AIV 核数、单次 DataCopy 粒度过小、MTE 时间占比过高、scalar instruction ratio 过高、tail efficiency 低。Symptom 是 observation，不能被训练策略主动选择。

### Problem 节点

描述可由证据检验、可由干预区分的性能机制，例如 `underused_blockdim`、`tiny_tile_setup_amplification`、`redundant_gm_round_trip`、`pipeline_serialization`、`ub_lifetime_conflict` 和 `scalar_hot_loop`。problem node 不要求互斥，一个 episode 可以对多个节点保留 posterior。

### Anchor facet 节点

现有六类 family 改称 anchor facets。它们提供稳定的人类入口和 expert prior，不参与自动删除，也不充当训练标签。一个 mechanism problem node 可以连接多个 anchors。例如 `tiny_copy_setup_amplification` 同时连接 tiling 与 data movement，`redundant_gm_round_trip` 同时连接 data movement 与 on-chip memory。图因此是多父 typed DAG，不是六棵互斥的分类树。

图中始终保留 `unknown_unresolved`。当现有 problem nodes 对一条记录的最大 posterior 过低，或所有节点的 likelihood 都较低时，系统不强行分类，而是把它送入 novelty buffer。

### Skill 节点

每个 skill 是一个 typed transformation contract。最少包含以下字段。

```yaml
skill_id: ascend.vector.increase_task_parallelism
skill_version: 1.0.0
status: active
problem_family: ai_core_utilization
applicability:
  soc: [Ascend910B1]
  operator_families: [elementwise]
  dtype: [float16, float32]
  shape_predicates: []
required_evidence: []
parameter_schema: {}
transformation_ir: {}
capacity_constraints: []
semantic_invariants: []
expected_profile_delta: []
contraindications: []
gate_spec: {}
rollback_spec: {}
provenance: {}
```

例如 `increase_task_parallelism` 不能只写“增大 blockDim”。它还要说明参数域、每核最小工作量、DataCopy 的字节边界要求、tail 和 dynamic tiling 不变量、核数来源、预期 active-core 与 duration 变化，以及 tiny workload 的禁用条件。

### Instantiation 节点

记录具体 candidate 的参数和 patch，例如 blockDim、tileLength、queue depth、buffer 数、循环改写和 Host Tiling 变化。

### Gate outcome 节点

终态至少区分 static rejected、build failed、accuracy failed、runtime failed、measurement unstable、stable no-gain、benchmark-specialized gain 和 production-safe verified gain。

## 4.3 边类型

图中包含以下边。

- `observes` 连接 context 与 symptom，由证据规则激活，不训练。
- `supports` 与 `refutes` 连接 symptom 和 problem，可以训练。
- `selects` 连接 problem 和 skill，可以训练。
- `instantiates` 连接 skill 和参数化 candidate，可以训练或由小型搜索器选择。
- `terminates` 连接 candidate 和 gate outcome，由执行环境产生，不训练。

每条可训练边记录稳定 `edge_id`、context predicate、hard preconditions、行为概率、verified episode count、effective sample size、效用均值与不确定性、失败类型、最近验证版本和 provenance。

## 4.4 从当前 AProf 编译 seed graph

现有 repository 已经提供初始图所需的知识来源。

- symptom 节点来自 `diagnosis/references/*-diagnosis-metrics.md`、`source-hypothesis-routing.md` 和 profiling metric bundles。
- anchor facet 来自当前六个宽泛 family。
- provisional problem 节点来自具体 injection recipe、bound deep routing 和可执行证据谓词，不直接继承六类标签。
- skill 节点来自 `optimization/references/*-optimization-strategies.md` 与四个 operator playbook。
- symptom 到 problem 的边来自 diagnosis matrix。
- problem 到 skill 的边来自 `optimization-strategy-routing.md`。
- action contract 可以从现有 `optimization_plan.json` 的 required evidence、capacity model、structural edits、expected metric delta、abort conditions 和 failure handoff 迁移。

初始图由一个 deterministic compiler 从现有 Markdown references 生成。编译结果只是 expert-seeded provisional graph，随后还要经过多视图归纳、bootstrap 稳定性检查和开发集干预验证，才能发布为 `v0001`。论文应公开编译规则、labeling functions、特征 schema 和最终 graph manifest，避免让图初始化成为不可复现的人工步骤。

## 4.5 Evidence-grounded graph induction

对第 (i) 条 diagnosis 与 optimization record，定义

\[
r_i=(c_i,x_i^{src},x_i^{work},x_i^{prof},x_i^{patch},a_i,\delta_i,g_i)
\]

其中 (c_i) 保存 operator、shape、dtype、layout、SoC 和 CANN version。四个 evidence view 分别描述源码与 IR 结构、workload 与硬件容量关系、归一化 profile signature，以及 patch 的 transformation pattern。 (a_i) 是实际执行的 skill，(\delta_i) 是配对 profile effect vector，(g_i) 是 build、accuracy、runtime、measurement 和 scope gate outcome。

源码 view 只抽取可审计的结构特征，例如 DataCopy 位置、tile loop、tail branch、blockDim、TQue 或 TBuf depth、SetFlag 与 WaitFlag、GM 到 UB 的生命周期和 hot-loop 控制流。workload view 使用 tile bytes 相对 UB capacity、elements per core、tail efficiency、active cores 相对 attainable cores、arithmetic intensity 和理论最小 traffic 等归一化量。profile view 使用 MTE、Scalar、Vector 和 Cube ratio、useful bytes per MTE instruction、actual traffic 相对 minimum traffic、per-core imbalance 与 wait bubble。自然语言 embedding 只作辅助，不作为 cluster 成立的主要依据。

当前 diagnosis rules 被改写为允许多标签和 abstain 的 labeling functions

\[
\lambda_j(r_i)\in\{A_1,\ldots,A_6,\bot\}
\]

它们只给六个 anchors 提供 weak prior。随后在 anchors 内部和跨 anchors 执行 missing-view-aware 的 constrained mixture 或 consensus clustering。第一版使用手工结构特征、robust scaling、有限 overcomplete mixture、多个随机初始化和 group bootstrap，不训练大型多视图 encoder。

设潜在 mechanism 为 (z_i)，其结构目标可以写成

\[
\begin{aligned}
\mathcal L_{struct}
=&-\sum_i\log\sum_k\pi_k
\prod_m p_m(\widetilde x_i^{(m)}\mid z_i=k)^{\rho_i^{(m)}\omega_m}\\
&\quad\cdot p(\lambda_i\mid z_i=k)
\cdot p(\delta_i,g_i\mid z_i=k,a_i,c_i)^\gamma\\
&+\Omega_{sparse}+\Omega_{complexity}+\Omega_{domain}
\end{aligned}
\]

(\rho_i^{(m)}) 是 view availability mask。三个 regularizer 分别控制空节点和重复节点、无必要的结构复杂度，以及 cluster 被单一 operator、shape 或 SoC identity 主导的风险。

observational clustering 只负责提出 provisional nodes。正式 problem node 还需要干预证据。对 mechanism (k) 和 skill (s)，定义条件响应

\[
R_{k,s}=\mathbb E[(\delta,g)\mid z=k,do(s),c]
\]

若两个表面相似的 cluster 对同一 skill 产生稳定不同的 profile delta 或 gate outcome，它们应保留为不同 problem nodes。若共同 interventions 下的 effect vector、失败分布和适用条件都落入预注册的等价区间，它们才有资格合并。这里的 (do(s)) 表示受控地执行某类 transformation，不表示仅凭 observational episode 已经获得完整因果识别。

由于 production policy 不会均匀尝试所有 skills，系统保留 behavior propensity，并在 response estimation 中使用 overlap check 与 IPS 或 doubly robust sensitivity analysis。两个节点没有足够共同 intervention support 时，不执行 merge，也不把缺失 response 填成 no-gain。

provisional node 至少要满足四项条件。它需要达到最小 effective support，覆盖多个独立 operator 或 injection lineages，得到两个 evidence views 或一个 evidence view 加干预证据的支持，并在 operator-level bootstrap 下保持稳定。未满足条件的模式继续留在 unknown buffer。LLM 可以给 cluster prototype 命名和起草 contract，不能决定节点是否成立。

# 5 Method II 可微边权

## 5.1 参数化

对上下文 (x) 和合法边 (e)，定义 edge score

\[
\ell_e(x)=b_e+u_e^\top\phi(x)
\]

其中 (b_e) 是 edge bias，(u_e) 是低维边向量，\(\phi(x)\) 编码 operator family、shape class、dtype、profile signature、workload class、SoC 和预算。数据规模较小时，\(\phi\) 使用离散特征和小型 MLP，不微调大模型。

对不满足 applicability、capacity、evidence 或 safety 条件的边使用 hard mask

\[
m(x,e)\in\{0,1\}
\]

路由概率为

\[
\pi_\theta(e\mid x)=
\frac{m(x,e)\pi_0(e\mid x)\exp(\ell_e(x)/\alpha)}
{\sum_{e'}m(x,e')\pi_0(e'\mid x)\exp(\ell_{e'}(x)/\alpha)}
\]

\(\pi_0\) 是当前 AProf 的专家路由规则。KL 或 prior regularization 可以防止小数据阶段的策略偏离已验证知识。

## 5.2 训练目标

固定图版本内，AProf 优化经过 validation gate 的成本敏感收益

\[
J(\pi)=
\mathbb E_{\tau\sim\pi}
\left[
U(y)-C(\tau)
-\alpha\sum_t\log\frac{\pi_\theta(e_t\mid x_t)}
{\pi_0(e_t\mid x_t)}
\right]
\]

其中 (U(y)) 是机器 gate 产生的 bounded utility，(C(\tau)) 包含编译、profile、token、wall-clock 和风险成本。

DAC 第一版采用上下文 bandit 或 entropy-regularized policy gradient。对 verified episode (i)，可使用

\[
\mathcal L_{policy}
=
-q_i\bigl(U_i-b(x_i)\bigr)
\sum_{e\in\tau_i}\log\pi_\theta(e\mid x_i)
+\lambda_{KL}\operatorname{KL}(\pi_\theta\|\pi_0)
\]

\(q_i\) 是 measurement-quality weight。稳定硬件证据取 1，机制 metric 不完整但 timing 稳定的 episode 可以降权。simulator-only episode 只训练 feasibility 或 proposal model，不训练 production performance value。measurement inconclusive 不进入性能梯度，稳定 regression 则是有效负样本。

如果训练数据足够，可以进一步在固定有限 DAG 上做 fitted soft Bellman regression。proposal 不把 TTB 和 learned backward policy 设为必需项，因为它们不能自动提供性能因果归因。

## 5.3 三类 credit

AProf 明确区分三种量。Selection mass 表示某条边在当前策略下被访问的概率，只用于 coverage 和 exploration。Decision credit 使用同一上下文中的 advantage

\[
A(x,e)=Q(x,e)-\sum_{e'}\pi(e'\mid x)Q(x,e')
\]

它用于路由和 edge ranking。Structural credit 使用删除边或删除 skill 后的图价值变化

\[
D_s(c)=V_{\mathcal G}(c)-V_{\mathcal G\setminus s}(c)
\]

它用于检查 skill 是否提供独立价值。结构提交还要结合 verified empirical utility 的置信区间，不能只依靠模型预测。

# 6 Method III Profile Validation Gate

## 6.1 Gate 状态机

现有 AProf 已经规定了合理顺序。DAC 实现需要把这些 Markdown 规则变成不可绕过的 runtime 状态机。

1. SchemaAndPrecondition
2. CapacityAndStaticReview
3. Build
4. AccuracyAndSemantic
5. RuntimeSafety
6. CheapDirectTiming
7. PairedHardwareProfile
8. MeasurementStability
9. MechanismConsistency
10. GeneralityAndPortability

Agent 只能提交 draft candidate。`selected_as_best`、`evidence_status`、`scope_status` 和最终 reward 只能由 gate runtime 计算。

## 6.2 配对性能测量

baseline 和 candidate 在同一测量 epoch 内随机交错，或采用 ABBA 顺序。对第 (j) 个配对样本定义

\[
d_j=\log T_j^{base}-\log T_j^{cand}
\]

主实验至少收集 30 个 paired samples。每个 sample 内循环执行 kernel，直到总时长达到预设下限，再折算到单次 launch，减小计时分辨率影响。记录频率、温度、并发任务和 device 状态，候选在同一设备队列串行执行。

候选的主接受条件如下。

- 所有 correctness、numerical、tail、boundary 和 dynamic shape 测试通过。
- baseline 与 candidate 的 CV 均不超过 5%。
- paired bootstrap 的 95% speedup 下界大于 1.03。
- held-out shapes 没有显著超过 3% 的回退。
- semantic status 为 preserved。
- scope status 为 production safe。
- portability risk 不为 high。

若需要 early stopping，应采用 anytime-valid confidence sequence 或显式 alpha spending，不能在普通 bootstrap 区间上反复查看并提前停止。

## 6.3 机制一致性

skill contract 会预测 profiler metric 的变化方向，例如 GM traffic 下降、MTE 指令减少、active core 增加或 scalar ratio 下降。定义机制一致性

\[
A_{profile}(s,i)=
\frac{\sum_m w_m\mathbf 1[
\operatorname{sign}(\Delta z_{i,m})
=\operatorname{sign}(\widehat{\Delta}_{s,m})]}
{\sum_m w_m}
\]

如果 duration 稳定改善，但预期 counter 没有按方向变化，候选可以保留为性能成功，episode 标记为 `attribution_uncertain`。它不能提高 skill 的机制置信度，也不能直接触发 problem 到 skill 边的强化。

## 6.4 Terminal utility

使用配对 log-duration 的保守下界作为性能收益

\[
\widehat\Delta_i^{safe}=LCB_{0.95}(\mathbb E[d])
\]

终局 utility 定义为

\[
U_i=
\begin{cases}
\operatorname{clip}(
\widehat\Delta_i^{safe}
-\lambda_p C_i^{profile}
-\lambda_b C_i^{build}
-\lambda_r Risk_i
-\lambda_g GeneralityPenalty_i),
& \text{all mandatory gates pass}\\
-u_{accuracy},&\text{accuracy or semantic failure}\\
-u_{runtime},&\text{runtime or crash failure}\\
-u_{build},&\text{build failure}\\
-u_{unstable},&\text{measurement unstable}\\
-u_{nogain},&\text{stable but no gain}
\end{cases}
\]

失败 episode 全部保存。编译失败、精度失败、稳定性能回退和 benchmark specialization 对 mask、risk model 和后续 candidate selection 都有价值。

## 6.5 Candidate gate 与 graph-version gate

系统设置两层 gate。

Candidate gate 判断单个 patch 是否能成为 verified episode。

Graph-version gate 在 shadow dev set 上比较旧图与候选新图。只有 aggregate log-speedup 的置信下界为正、Correct-Speedup@B 不下降、关键 shape 无回退，而且图复杂度增长可控时，才发布新版本。

# 7 Method IV 低资源 Verified Episode Generation

## 7.1 四类 episode 来源

### 自然低效 kernel

从真实 reference、开源 sample 和已有工程中选择可以复现的低效实现。它们用于主结果和真实性评估。

### 单因素问题注入

利用当前 21 个 recipe 注入 correctness-preserving 性能反模式。每个 case 只有在 build、全 shape correctness 和真实硬件 slowdown 均通过后，才能标记为 active。主判定建议使用 slowdown 的 95% 置信下界超过 3%。weak、unverified 和非单因素 case 不进入主表。

### Rewind

从已验证的优化 child 向前恢复一个性能较差的 parent。每次 accepted optimization 保存 parent、child、inverse patch、profile before/after 和适用范围。当前 FastGELU 三轮优化可以产生第一批 rewind pairs，但论文仍需扩展到更多 operator family。

### No-harm control

选择已经合理优化的 kernel 或不满足某个 skill precondition 的 context。系统应学会 NOOP 或拒绝不适用的 transformation，防止 skill 过度触发。

## 7.2 分层验证漏斗

每个候选依次进入不同成本层级。

- Tier 0 检查 schema、precondition、source pattern 和容量公式。
- Tier 1 生成 patch，执行 static review 和 build。
- Tier 2 执行 multi-shape accuracy、simulator 或 cheap timing。
- Tier 3 对有希望、信息量高或不确定性高的候选执行少量真实硬件 profile。
- Tier 4 只对最终候选执行完整配对 profile、机制 metric 和 held-out regression。

失败后立即停止后续昂贵验证，并保存 typed negative episode。编译可以在 CPU 上并行，NPU timing 与 msprof 进入单设备串行队列。相同 source、patch、build、profile 由 content hash 去重和缓存。

## 7.3 主动选择完整 profiling 候选

对候选 (z) 维护预测收益 \(\mu(z)\)、不确定性 \(\sigma(z)\)、gate 通过概率 \(p_{valid}(z)\) 和预计验证成本 \(\widehat C(z)\)。采集优先级为

\[
a(z)=
\frac{p_{valid}(z)
[EI(z)+\kappa\sigma(z)+\lambda IG(z)]}
{\widehat C(z)+\varepsilon}
\]

其中 EI 偏向可能带来收益的候选，\(\sigma\) 探索未验证边，IG 补齐低覆盖的 problem、operator 和 shape 区间。另加 stratified quota，避免训练数据被容易优化的 elementwise case 占满。

## 7.4 Verified episode schema

每条 episode 至少保存以下信息。

```text
episode_id
parent_episode_id
origin
graph_version
policy_version
skill_contract_versions
context_hash
hardware_fingerprint
cann_compiler_version
model_prompt_agent_hashes
selected_node_ids
selected_edge_ids
behavior_probabilities
action_parameters
baseline_source_hash
candidate_source_hash
patch_hash
all_gate_outcomes
baseline_candidate_samples
profiling_metric_deltas
mechanism_alignment
evidence_status
candidate_decision
terminal_utility
artifact_hashes
failure_handoff
timestamps
```

建议将运行数据放入 `<op_dir>/.aprof/`，metadata 使用 append-only SQLite，raw artifacts 使用 content-addressed store，训练导出为 JSONL 或 Parquet。运行产物不直接提交到 Git。

# 8 两时间尺度的图结构演化

允许 problem nodes 增删改会增加训练难度，但主要风险来自结构和边权在同一批数据上同步变化。若 policy 当前偏好某个 skill，它会采集更多相关 episode；这些 episode 又可能让 cluster 更像该 skill 有效，随后进一步提高对应边权。这个反馈回路会造成 label drift、selection bias 和版本间不可比较。

DAC 版本采用两时间尺度训练。一个 phase 内固定图结构和 skill contracts，只训练边权。结构学习只在 phase boundary 发生，频率远低于 edge update。结构候选先进入 shadow graph，再通过独立 operator groups 上的 graph-version gate。第一版不训练外层 edit RL，因而无需从少量 episode 中学习高方差的 ADD、SPLIT、MERGE 和 DELETE policy。

## 8.1 Node add

设现有节点对记录 (i) 的最大 posterior 为

\[
p_i^{max}=\max_k p(z_i=k\mid r_i)
\]

posterior 过低或 likelihood 过低的记录进入 novelty buffer。新增 shadow node 需要满足下面的条件。

- 样本形成 bootstrap-stable cluster，不是几个离散 outliers。
- effective sample size 达到预注册下限。
- 至少跨两个独立 operator 或 injection lineages。只在单一 operator 出现时保持 provisional。
- 至少两个 evidence views 与现有节点有稳定差异，或干预响应明显不同。
- 节点能形成可执行的 evidence predicate、skill route 或 disambiguation probe。
- 在 held-out data 上改善 problem-to-skill ranking、effect prediction 或端到端 reward，并且收益超过结构复杂度惩罚。

## 8.2 Node split

内部方差大不足以触发 split。有效 split 需要发现两个可重复、可行动、干预响应不同的子群。候选拆分 (k\rightarrow k_1,k_2) 首先要改善 held-out likelihood

\[
\Delta NLL_{heldout}=NLL(k)-NLL(k_1,k_2)>\epsilon_{split}
\]

两个 child 还要分别达到 minimum support，并在 operator-level bootstrap 下稳定。最关键的判据是共同 skill 下的 response heterogeneity 在 split 后下降

\[
H_{k_1}+H_{k_2}<H_k-\epsilon_H
\]

例如，同样观察到 active cores 偏低，一组通过增大 blockDim 获得稳定收益，另一组属于 tiny workload，增大 blockDim 后更慢。它们的表面 symptom 接近，优化响应相反，应当拆成不同 mechanism nodes。

## 8.3 Node merge

Merge 使用 equivalence test，不能把普通显著性检验中的未拒绝差异误当成等价。两个节点需要同时满足 evidence equivalence、intervention equivalence、gate-outcome equivalence 和 schema compatibility。

对共同 skills，要求 response distance 落入预注册等价区间

\[
d_{int}(k,l)=
\sum_{s\in\mathcal S_{common}}w_sD(R_{k,s},R_{l,s})
<\epsilon_{merge}
\]

若共同 interventions 太少，只能将它们标记为 evidence-similar，不能宣称 mechanism-equivalent。合并后保留旧 node IDs 作为 aliases，不重写历史 episodes。

## 8.4 Refine、cold 与 deprecate

若一个节点仍有独特机制，但 applicability predicate 过宽，系统执行 refine，收紧 shape、dtype、capacity 或 workload 范围。支持不足的节点先进入 `cold`，避免把缺数据误判为无价值。只有当节点没有独特 evidence signature、没有独特 intervention response、被新节点完全支配，或连续多个 graph versions 都没有新增支持时，才进入 `deprecated`。因 CANN、SoC 或 API 变化失效的节点进入 `incompatible`。所有状态都保留 lineage 和旧版本引用，不做物理删除。

## 8.5 Phase-wise alternating algorithm

每个 graph phase 包含六步。

1. Evidence collection 固定图结构，使用带最小探索概率的 edge policy，记录 behavior propensity，并用 group-balanced replay 防止近期 operator 主导数据。
2. Structure proposal 冻结边权，在数据快照上执行多视图归纳，生成 add、split、merge、refine 和 deprecate proposal。
3. Disambiguation intervention 继续冻结生产图，只执行最能区分候选结构的 probes。采集函数可以优先选择预期信息增益 (I(z;\delta,g\mid do(s))) 较大的 skill。
4. Graph commit 在独立 operator groups 上运行 graph-version gate。通过后发布不可变的 (\mathcal G^{(k+1)})。
5. Edge training 固定新结构。split children 从 parent warm-start，merged node 按 effective support 合并参数，new node 使用 anchor prior，deprecated node 使用 hard mask。
6. Minimum dwell 新版本达到最小 episode 数、operator coverage 和 profile budget 后，才允许下一次结构编辑。

## 8.6 结构稳定性与防抖

bootstrap 的抽样单位是 operator 或 injection lineage，不能把同一 kernel 的 shapes 和 candidates 当作独立样本。系统报告 cluster co-assignment、per-node Jaccard stability、adjusted Rand index 和跨版本 lineage matching。跨版本 node identity 结合 record overlap、anchor membership、evidence distribution 和 intervention signature，再用 Hungarian matching 确定。

每个版本设置 churn budget，例如最多修改 20% 的 active problem nodes，并限制 add、split 和 merge 数量。候选结构的 discovery split 与 acceptance split 按 operator group 分开。系统还训练一个只读取 operator name、shape 和 SoC 的 leakage probe。若它能高准确率预测 cluster，而这些 cluster 又没有一致的 intervention response，说明结构学到了数据来源，不能提交。

## 8.7 训练与发布算法

```text
Algorithm AProf Two-Timescale SkillGraph Evolution

Input
    expert-seeded provisional graph G0
    routing prior pi0
    operator and workload pool C
    build, timing and profile budgets B

Initialize
    graph version k = 0
    verified episode store D
    edge policy theta from pi0
    unknown buffer U

while budget remains
    freeze graph structure and contracts of Gk
    collect version-compatible verified episodes with logged propensity
    update only differentiable edge parameters theta

    if minimum dwell and coverage conditions pass
        freeze theta and snapshot D
        induce provisional mechanism clusters from multi-view evidence
        propose add, split, merge, refine and deprecate edits
        run targeted disambiguation interventions
        evaluate candidate graph on held-out operator groups

        if graph-version gate passes
            publish immutable G(k+1)
            match node lineage and warm-start compatible parameters
            k = k + 1
        else
            retain Gk and move unresolved records to U

Return
    immutable graph versions
    edge-policy checkpoints
    verified episode and artifact index
```

# 9 具体工程实施

## 9.1 Runtime 目录

建议恢复一个小型、强类型的 Python runtime。它与 Markdown plugin 分工明确。Plugin 负责 agent 交互和候选提案，runtime 负责状态、验证、统计、版本和训练。

```text
Aprof/
  pyproject.toml
  src/aprof_runtime/
    cli.py
    contracts/
      models.py
      validate.py
    skillgraph/
      models.py
      compiler.py
      store.py
      migrations.py
    policy/
      edge_model.py
      selector.py
      trainer.py
      checkpoint.py
    profiling/
      collector.py
      manifest.py
      statistics.py
      parsers/
        hw_op.py
        hw_msprof.py
        sim.py
    validation/
      gate.py
      correctness.py
      generality.py
      performance.py
    episodes/
      models.py
      store.py
      artifacts.py
      export.py
    workflow/
      runner.py
      state_machine.py
      events.py
    adapters/
      direct_invoke.py
      cann_bench.py
  schemas/
  skillgraph/
    seed/v0001/
    contracts/
    versions/
  tests/
    unit/
    integration/
    fixtures/
```

## 9.2 Runtime 命令

建议提供统一入口 `aprofctl`。

```text
aprofctl install verify
aprofctl contract validate
aprofctl profile collect
aprofctl profile parse
aprofctl candidate gate
aprofctl episode finalize
aprofctl graph compile-seed
aprofctl graph propose
aprofctl graph validate
aprofctl graph publish
aprofctl policy train
aprofctl policy evaluate
aprofctl benchmark freeze-seed
aprofctl benchmark seal
aprofctl benchmark submit
```

Agent 生成的 JSON 都是 draft。只有 runtime validate 后才能进入正式 store。

## 9.3 实施优先级

### P0 统一安装和清理旧入口

- 统一 marketplace、plugin manifest 和 `init.sh` 的 skills 与 agents 声明。
- 把 optimization skill 和总 workflow agent 纳入原生安装路径。
- 增加 install smoke test 和 submodule revision 检查。
- 删除或修复引用已移除 `src/aprof` 的旧脚本与文档。
- 明确当前 `configs/architectures/ascend910b1.yaml` 中 assumed 或 placeholder 字段不能作为绝对硬件分母。

### P1 机器可执行的 contract 与 gate

- 为现有 JSON contract 编写 JSON Schema 或 Pydantic models。
- 实现通用 hw-op、hw-msprof 和 sim parser。
- 实现 paired statistics、artifact completeness、measurement status 和 gate state machine。
- 把 FastGELU 专用 profiling 脚本转成 integration fixture。

### P2 Episode 与 artifact store

- 实现 verified episode schema、append-only index 和 content-addressed artifacts。
- 旧的 optimization memory 与三轮 summary 导入为 `legacy_unverified`。
- 缺少 behavior probability、graph version 或 artifact hash 的历史数据不直接训练 edge policy。

### P3 Seed SkillGraph

- 从现有 diagnosis 和 optimization references 编译 v0001。
- 手工审核 symptom predicate、problem subtype、skill contract 和边。
- 增加 graph schema、migration、tombstone、diff 和 rollback 测试。

### P4 可微路由

- 先在 shadow mode 运行，只记录新策略会选什么，不控制候选生成。
- 记录 behavior propensity，完成离线 replay 与 calibration。
- shadow 指标稳定后，再让 learned policy 在固定预算内控制候选优先级。

### P5 图版本更新

- 生成 candidate graph。
- 执行 schema、contract、held-out replay 和 profile validation。
- 通过 graph-version gate 后原子发布。
- 失败时保持旧版本并保存拒绝证据。

### P6 CANNBench frozen-seed track

- 为单 operator seed 实现 build、calibration correctness、calibration timing 和 final submission adapter。
- 生成 sanitized agent package 和 sealed evaluator package。
- 冻结 benchmark commit、operator list、seed hashes、case split 和 hardware metadata。
- 在 agent 容器中检查 `golden.py`、sealed cases 与 final reports 均不可见。

# 10 数据集计划

## 10.1 三种统计单位

训练数据不能只按题目数或 JSONL 行数报告。论文区分三个单位。

**Task instance** 是统计和划分单位，由 operator、starting implementation hash、workload suite 和 hardware fingerprint 共同确定。同一 seed 的注入版本、rewind descendants、不同 shapes 和候选修改属于同一 lineage cluster，不能跨 train、dev 和 test。

**Episode** 是训练单位。它从固定 baseline、graph version 和预算开始，包含若干 symptom 到 problem、problem 到 skill 的选择以及候选验证，最后得到 machine-generated terminal utility。

**Candidate transition** 是 episode 内的一次 route、patch 和 gate outcome。它可以进入 edge loss 和 validity model，但不能被当作独立 task，也不能在统计检验中伪装成独立样本。

## 10.2 四层数据隔离

数据划分为四层。

1. `D_train` 只使用内部训练 operators 的 natural、injection、rewind 和 no-harm episodes，用于 edge training 与 structure proposal。
2. `D_dev` 使用 operator-disjoint 的内部 operators，用于 early stopping、threshold calibration、graph-version commit 和超参数选择。
3. `D_test_public` 使用冻结版本的 CANNBench 公开 tasks，在 sealed harness 中进行外部测试。它不能参与节点聚类、边权训练、prompt 修改和阈值校准。
4. `D_test_private` 在相同算子支持域内增加未公开 cases 或未公开 seed implementations，用来补强真正 blind 的证据。若没有 private extension，论文只能称其为公开 benchmark 上的 sealed evaluation，不能称为 model-unseen test。

## 10.3 训练 episode 的来源

训练集按 task lineage 分层采样。目标版本可让四种 episode 来源接近下面的比例，最低版本按实际可验证数据报告，不为了满足比例复制样本。

- 40% correctness-preserving single-fault tasks，用于覆盖明确机制和图边。
- 30% verified rewind tasks，从真实 accepted optimization 的 parent 与 child 恢复高质量正例。
- 20% natural search tasks，从没有人工降速的正确 seed 开始，降低 synthetic bias。
- 10% no-op 与 hard-negative tasks，覆盖无真实瓶颈、错误诊断、build failure、accuracy failure 和稳定回退。

每个 task 至少运行三条 episodes，包括一条 expert-seeded 路径、一条带探索的路径，以及一条 counterfactual 或失败路径。每条 episode 最多执行三到四个 candidate transitions。no-op 与 hard-negative episodes 可以从 natural starting state 产生，不另算独立 source lineage。最终 candidate outcome 应维持足够的 informative negatives。最低版本要求至少 30 个 verified positive improvements，并获得同量级的 build、correctness、no-gain 或 regression negatives。

## 10.4 数据质量规则

一个 injected case 只有同时满足以下条件才能成为 active。

- 只改变一个主要性能因素。
- build 通过。
- 全部声明 shape 的 correctness 通过。
- 真实硬件 slowdown 的 95% 置信下界超过 3%。
- ground truth 对 diagnosis agent 完全盲化。
- variant 名、metadata、inject manifest 和维护者报告不进入模型输入。

所有 split 以 operator 和 normalized source lineage 分组。论文对 train 与 test 做 AST hash、token MinHash、关键 helper 和 magic constant 扫描，并人工审计相似对。recipe-template-disjoint split 作为额外 stress test，检查 agent 是否只记住注入模板。

## 10.5 最低规模与目标规模

最低可行训练集包含 6 个 training operators。每个 operator 构造 4 个 starting states，包括 1 个 natural state、2 个 active single-fault states 和 1 个 rewind state，共 24 个 task instances。每个 task 运行 3 条 episodes，得到 72 条 verified episodes 和约 200 到 280 个 candidate transitions。开发集另外使用 2 个未见 operators 和 8 个 task instances。

目标训练集扩展到 10 个 operators 和 60 个 task instances，每个 task 运行 3 条 episodes，得到 180 条 verified episodes 和约 540 到 720 个 candidate transitions。开发集使用 3 个未见 operators 和 12 个 task instances。

这两个规模不是普适样本复杂度结论。它们来自第一版 core graph 的覆盖预算。DAC 版本先把可训练 problem-to-skill edges 限制在约 25 到 40 条。最低验收要求至少 80% core edges 的 effective sample size 达到 8，并同时观察到正向和负向或替代结果。rare edges 保留 expert prior，不宣称已经学会。72 episodes 只足以验证少量 add 或 split，若要系统评价完整动态图演化，应以 180 episodes 的目标版本为准。

训练 operators 可以从现有 FastGELU、Mish、SwiGLU、ReduceSum、Vector Add 和 Cast 起步，再加入与外部测试不重合的 reduction、normalization 或 layout tasks。若把 LayerNorm 放入训练，RMSNorm 就不能继续被描述为严格未见机制，只能放入 semantic-neighbor transfer 组。

## 10.6 Learning curve 与停止条件

learning curve 按完整 task lineage 做分层 subsampling。最低版本使用 18、36 和 72 episodes 三个累计点，目标版本增加 120 和 180 episodes。每个点运行三个 cluster-level sampling seeds，并同时以 candidate transitions 与 NPU-hours 作为第二横轴。

每增加 20 条 verified episodes 或发布一个 graph version，系统在固定开发集上重新训练和评估。停止需要同时满足下面的条件。

- 连续两个 tranche 的 Correct-Speedup@B 提升低于 1 个百分点，mean log-speedup 提升低于 0.01，配对 bootstrap 没有稳定正增益。
- 相邻 policy 的 top-k path Jaccard 高于 0.9，或 mean policy KL 低于 0.02。
- 至少 80% core edges 的 effective sample size 达到 8，关键 mechanisms 同时有成功和失败证据。
- gate 指标不恶化，开发集 regression escape rate 不高于 5%。

达到预注册硬件或模型预算也可以停止。若最低规模结束时 learning curve 仍在上升，论文应写成 budget-limited，不声称已经收敛。

## 10.7 CANNBench 外部测试协议

本 proposal 对 CANNBench 的判断基于 2026 年 8 月 11 日读取的 commit `001163e`。仓库包含 53 个 operators，其中 L1、L2、L3 和 L4 分别为 8、16、21 和 8 个。每个 operator 有 20 个公开 cases，共 1060 个 cases。每个 task 提供 `desc.md`、`proto.yaml`、`golden.py`、`cases.yaml` 与 `cases.csv`，并由 evaluator 检查编译、正确性和性能。

CANNBench 原生评估从规格生成算子，不提供一份待优化的 Ascend C seed kernel。AProf 的主张是 profile-guided optimization，因此需要建立 Frozen-Seed Optimization Track。

1. 使用一个不含 AProf 的固定 generator、模型快照和 prompt，为每个测试 operator 最多生成三份实现。
2. 按预注册顺序选择第一份通过完整 correctness suite 的实现，不按性能挑选，避免 headroom selection bias。
3. 冻结 seed source hash。所有 baselines 和 AProf variants 从同一份 seed 开始，使用相同 calibration information 和优化预算。
4. curator 可以用完整 20 cases 检查 seed eligibility。agent 只读取 sanitized `desc`、`proto`、seed source 和 4 个按 dtype、size、alignment 与 attrs 分层选出的 calibration cases。
5. 剩余 16 个公开 cases 只由 sealed evaluator 执行。若条件允许，每个 operator 再生成 5 个未公开 private cases。
6. 无法生成正确 seed 的 operator 记为 coverage failure，不在看到性能后替换题目。

DAC 最低 Blind-Core 使用 6 个 L1 与 L2 operators，包括 Exp、MaskedScale、ForeachNorm、Gather、DynamicQuant 和 RMSNorm。它们覆盖 elementwise、list reduction、irregular access、quantization 和 normalization。目标版本增加 Softmax、ArgMax、Transpose 和 TopK，共 10 个 operators。Softmax 若已经使用现有 operator-specific playbook，应单列为 known-mechanism transfer，不能与严格 unseen-op 结果混合。L4 只作为资源充足时的 stretch test。

CANNBench 公开的 HAP 使用 hardware anchor。当前完整 metadata 面向 910B2 与 950PR。若 DAC 实验运行在 910B1，不能静默使用 910B2 fallback。论文需要在 910B1 重新采集 baseline anchor，或将 HAP 降为不报告。主指标始终使用相对同一 frozen seed 的 correctness-constrained speedup，HAP 只作为硬件和 metadata 匹配时的 secondary metric。

## 10.8 Sealed harness 与适配器

新增 `CannBenchOptimizationAdapter`，把每个 frozen seed 暴露成统一 contract。

```text
source_root
read_only_baseline_hash
build_command
calibration_correctness_command
calibration_timing_command
final_evaluation_submission_command
visible_case_ids
sealed_case_manifest_hash
```

candidate 仍复制到隔离目录修改。最终 harness 按单 operator 编译和评测，避免 CANNBench 默认的批量工程编译失败把无关算子一起计零。agent 容器不挂载完整 CANNBench repository，不可读取 `golden.py`、sealed cases、hardware metadata 和最终逐 case 结果。测试开始前冻结 graph version、policy checkpoint、prompt、model snapshot、seed hashes、case split 和预算，并发布时间戳 manifest。final aggregate 只在所有方法完成后解封一次。

# 11 实验设计

## 11.0 三组实验各自回答什么

主实验分为三组，避免让同一批 injected tasks 同时承担真实性、归因和外部泛化三种主张。

- External Frozen-Seed Track 使用 CANNBench Blind-Core，回答系统能否优化未参与训练的正确 seed implementation。
- Controlled Attribution Track 使用内部 single-fault 与 rewind tasks，回答诊断路径、机制归因和修复是否正确。
- Graph Evolution Track 使用开发集 learning curve 和结构 proposal，回答 add、split、merge 是否改善预测或优化结果，以及为此付出多少 profile 成本。

## 11.1 Baselines

主表至少包含以下方法，并保持相同模型、prompt 骨架、token、候选、编译和 profiling 预算。

1. Base LLM，无 skill library。
2. Current Flat AProf，使用当前扁平 references 和规则路由。
3. Flat Retrieval，使用 BM25 或 embedding 检索 skill。
4. Unweighted Static SkillGraph，图结构固定且边权均匀。
5. Learned Weighted Fixed Graph，只训练边权，不改变图结构。
6. Full AProf，版本化图、可微边权、profile gate 和 verified episodes。

资源允许时加入 outcome-only flat evolution 或 SkillFlow-style curator。它使用 terminal reward 和调用频率更新 skill，但不使用 AProf 的 profile mechanism gate 与条件效用，用来检验本文方法是否只是动态 library 带来的收益。

## 11.2 Ablations

- uniform edge weights
- fixed graph version
- no profiler mechanism validation
- no held-out shape regression
- no verified negative episodes
- no rewind episodes
- no failure memory
- profile-all 取代 selective verifier
- random acquisition 取代 cost-aware acquisition
- no graph-version gate

大规模 ablation 只在 compact test set 上运行，避免硬件成本失控。

## 11.3 Metrics

### 端到端优化效果

- Correct-Speedup@B
- CANNBench frozen-seed task coverage，无法获得正确 seed 或无法完成优化的任务计入失败
- unconditional geometric mean speedup，失败任务按 1 计
- conditional geometric mean speedup，只统计正确成功任务
- AUC of log-speedup versus budget
- trials、编译次数、完整 profile 次数和 wall-clock time to first valid gain
- public sealed cases 与 private extension 的 correctness 和 regression gap
- HAP，只在 metadata 与实际硬件严格匹配时报告

主表另外报告去除大于 10 倍病态 baseline 后的敏感性结果，防止单个 FastGELU case 支配平均数。

### 图路由效果

- path top-k recall
- MRR
- negative log-likelihood
- Brier score 或 calibration error
- operator-disjoint generalization

### Validation gate

- false acceptance rate
- false rejection rate
- regression escape rate
- profile-effect sign agreement
- benchmark-specialized rejection recall

### 数据效率

- verified episode yield
- NPU-hours per positive episode
- full-profile reduction relative to profile-all
- cache hit 与 duplicate patch elimination

### 图版本稳定性

- accepted、rejected 和 reverted updates
- graph churn
- active、provisional、cold、deprecated 和 shadow problem nodes 数量
- 跨版本 retained utility
- edit acceptance rate
- cluster co-assignment、per-node Jaccard 和 adjusted Rand index
- node split 后 intervention-response variance 的变化
- unknown buffer 的进入率、解析率和错误强制归类率

## 11.4 统计协议

- 每个 agent 配置至少运行 3 个随机种子。
- 主结果按相同 frozen seed task 与 agent seed 配对。
- 使用 hierarchical bootstrap，依次对 operator、seed lineage 和 agent seed 重采样，报告 95% 区间。task 内的 20 个 CANNBench cases 不作为 20 个独立任务重采样。
- Correct-Speedup@B 使用配对 permutation 或 McNemar 检验。
- log-speedup 使用配对 permutation 或 Wilcoxon signed-rank 检验。
- 多个比较使用 Holm 校正。
- 测试开始前冻结 graph version、policy checkpoint、model snapshot、prompt、temperature、token 和候选预算。

# 12 实施进度与验收条件

## 第 1 到 2 周

完成安装清理、schema、版本 ID、artifact manifest、episode logger 和 gate state skeleton。

验收条件包括插件原生安装与 `init.sh` 安装能力一致，现有 contract 全部通过 schema 验证，FastGELU 旧产物能导入为 legacy records。

## 第 3 到 4 周

把当前 references 编译成 atomic evidence predicates、anchor labeling functions 和 typed skill contracts。实现 source、workload、profile 与 patch 四类 feature extractor，并建立 missing-view mask。

验收条件是相同 source 与 artifacts 能生成确定性的 feature record，六个 anchors 允许多标签与 abstain，unknown buffer 可以完整保存未解析记录。

## 第 5 到 7 周

扩展到 6 个 training operators，修复弱注入，建立 natural、single-fault、rewind 与 no-harm starting states。完成 24 个 minimum task instances 的 build、multi-shape correctness 和真实 slowdown 验证，同时冻结 2 个 operator-disjoint development operators。

Go 或 no-go 条件是至少获得 24 个合格 task instances。若 active faults 不足，优先增加 operator 与自然、rewind tasks，不为了凑六个 anchors 接受弱标签。

## 第 8 周

从现有 references 和第一批 evidence records 编译 provisional graph。运行 consensus clustering、operator-level bootstrap 和 context-leakage probe，人工审核节点命名与 contract，发布 `v0001`。

## 第 9 到 10 周

完成 candidate gate、paired statistics、selective verifier、contextual edge model、hard mask、prior regularization、behavior propensity logging 和 shadow evaluation。采集 72 条 minimum verified episodes，得到约 200 到 280 个 candidate transitions。

Go 或 no-go 条件是至少 30 个 verified positive improvements、同量级 informative negatives，并且 80% core edges 的 effective sample size 达到 8。若达不到，论文保留 weighted fixed graph，不进入正式 node evolution 主张。

## 第 11 周

冻结 edge policy，提出第一轮 add、split、merge 和 refine candidates。执行 targeted disambiguation interventions，在 development operators 上运行 graph-version gate。最多提交一到两个高置信结构编辑，避免为了展示动态性制造 churn。

## 第 12 周

实现 `CannBenchOptimizationAdapter`，冻结 benchmark commit、Blind-Core operator list、6 份正确 seed implementations、4 对 16 的 case split，以及 graph、prompt、模型和预算 manifest。确认实际实验硬件与 HAP metadata 是否匹配。

## 第 13 到 14 周

完成 External Frozen-Seed Track、Controlled Attribution Track 和主 baselines。最低实验预留约 50 到 100 张卡小时。若进入 10-operator target 和 180-episode training，预留约 120 到 250 张卡小时。实际论文按 pilot 测得的 cheap timing 与 full profile 时长报告预算公式和重试开销。

## 第 15 周

完成 compact ablation、learning curve、统计检验、失败案例、leakage audit 和成本分析。若 private cases 无法获得，删去 true blind 的表述。

## 第 16 周

使用冻结 manifest 完成一次独立复现，整理 graph lineage、episode index、artifact hashes、seed packages 和论文图表。

# 13 预期贡献

论文计划提出四项贡献。

1. 一套 evidence-grounded、版本化的 Ascend C mechanism graph。它把现有六类知识降为非互斥 anchors，通过弱监督多视图证据提出底层 nodes，再用 profile-verified interventions 决定节点新增、拆分、合并和退役。
2. 一种冻结基础大模型、只训练外部图决策边权的 profile-grounded 后训练方法，在小数据条件下利用 expert prior、hard mask 和 verified negative episodes 学习候选路由。
3. 一套机器执行的 profile validation gate，用配对性能测量、机制一致性与跨 shape 回归控制错误经验进入 skill library。
4. 一种面向低资源 accelerator language 的 verified episode generation 与 sealed external evaluation 流程，结合自然 case、单因素注入、rewind、no-harm control 和 CANNBench frozen seeds，并通过分层验证降低 NPU profiling 成本。

# 14 风险与备选方案

## 数据过少

复杂 policy 和自由结构搜索都容易过拟合。第一版坚持线性 edge model 或小型 MLP，并用 expert prior、L2、entropy 和 operator-disjoint validation。verified episodes 不足时只训练边 bias 和少量 context interaction。结构证据不足时保留 anchors、provisional nodes 和 unknown buffer，不强行得出新 taxonomy。

## 聚类只学到 operator 或 shape

所有连续特征先按 hardware capacity 和 attainable performance 归一化。cluster discovery 使用 operator-level bootstrap 和 domain-balance regularizer，并用只读取 operator、shape 与 SoC 的 leakage probe 检查来源泄漏。正式 node 还必须得到 intervention response 或跨 operator evidence 支持。

## 注入数据缺少真实性

主结果同时报告自然 case 和 rewind。注入 case 主要用于 credit、diagnosis 和覆盖评测，不单独支撑真实性主张。

## Profiling 成本过高

使用 cheap timing、hash cache、CPU 并行 build、NPU 串行队列和 selective full profiling。minimum training 的 24 个 tasks 最多产生约 200 到 280 个 candidate transitions。全部 candidates 经过 static、build 和 correctness funnel，只有每个 task 的 baseline、winner，以及 novelty 或 uncertainty 最高的少量候选进入完整 msprof。最低计划把 full profile 控制在约 48 组 baseline 与 winner 采集，并在 pilot 后按实际运行时重算上限。若预算仍不够，优先保留 operator coverage、失败 episodes 和三条 episode seeds，削减每条 episode 的 candidate 数与 full profile 比例。

## Counter 缺失或不稳定

metric 记为 unknown，不允许 agent 补造。候选可以依靠正确性和稳定 latency 进入性能成功集合，但 mechanism confidence 不更新。论文单独报告可稳定获得的 AIV、MTE、active-core 或 traffic 指标覆盖率。

## 病态 baseline 夸大收益

主指标使用 log-speedup 和失败按 1 计的无条件几何平均，并报告去除超过 10 倍加速 case 的敏感性结果。FastGELU 258 倍案例只作为完整系统流程展示，不作为整体能力的代表。

## 单一 SoC 限制

DAC 版本只声明在实际测试 SoC 和 CANN 版本下有效。graph schema 保留 compatibility 字段，但论文不把跨 SoC 泛化写成已经完成的贡献。

## CANNBench 并非现成优化集

CANNBench 没有待优化的 Ascend C seed source，并且公开 cases 不能提供真正 blind 的证据。论文使用预注册的 frozen-seed track，把从零生成和后续优化分开；没有 private extension 时明确写成 sealed public evaluation。实际硬件与 metadata 不匹配时不报告 HAP。

# 15 论文结构建议

1. Introduction
2. Background and Motivation
3. AProf Overview
4. Versioned SkillGraph
5. Differentiable Edge Post-Training
6. Profile Validation and Verified Episodes
7. Implementation
8. Evaluation
9. Discussion and Limitations
10. Related Work
11. Conclusion

核心图建议包含四张。

- Figure 1 展示从当前 flat skill workflow 到 versioned SkillGraph 的完整训练与验证流程。
- Figure 2 展示六个 non-exclusive anchors、多父 mechanism nodes、unknown buffer，以及 evidence views 和 intervention response 如何形成节点。
- Figure 3 展示固定图内的可微 edge training 与 phase boundary 的 add、split、merge、refine、deprecate 两时间尺度更新。
- Figure 4 展示分层 validation funnel、verified episode、CANNBench frozen-seed adapter 和 sealed test harness。

# 16 与 SkillFlow 的关系

SkillFlow 说明了 phase 内固定 skill library、phase 边界更新 library 的可行性，也提出用训练信号定位 skill creation 和 pruning。AProf 借鉴这一阶段化结构，但改变三个关键部分。

第一，AProf 的外部状态是带显式边权和 contract 的 SkillGraph，梯度直接更新图决策参数。第二，AProf 不使用 forward/backward likelihood ratio 代表性能贡献，主要监督来自真实配对硬件测量和 gate outcome。第三，图结构修改要经过 correctness、performance、profile mechanism 和 cross-shape shadow validation，LLM 只负责提出候选。

因此，SkillFlow 应作为强相关工作和 flow-only curation baseline。论文的核心主张应放在 profile-grounded typed graph、可微外部路由和 validation-gated post-training 上。

# 17 关键参考资料

- AProf repository  <https://github.com/jieran-zhang/Aprof>
- CANNBench repository  <https://gitcode.com/cann/cann-bench>
- CANNBench benchmark specification  <https://gitcode.com/cann/cann-bench/blob/master/docs/spec/benchmark_spec.md>
- SkillFlow  <https://arxiv.org/abs/2605.14089>
- Reinforcement Learning for Self-Improving Agent with Skill Library  <https://aclanthology.org/2026.acl-long.69/>
- Memory-R1  <https://aclanthology.org/2026.acl-long.583/>
- SkillOps  <https://arxiv.org/abs/2605.13716>
- KernelBench  <https://arxiv.org/abs/2502.10517>

# 18 当前最重要的下一步

当前最先做的工作仍是 P0 和 P1，同时要把固定六类的叙述改成 anchors 与 provisional mechanisms。先把 Markdown 中已有的 contract、evidence predicates 与 gate 变成机器可执行 runtime，再扩数据和训练边权。若这一步没有完成，后面的 graph induction、verified episode 和 policy reward 都缺少可信来源。

第一批实现应达到下面这个最小可运行流程。

```text
current flat AProf references
    -> compile anchor facets and atomic evidence predicates
    -> induce provisional problem nodes and unknown buffer
    -> publish SkillGraph v0001
    -> select one symptom/problem/skill path
    -> generate isolated candidate
    -> runtime executes build/correctness/paired timing/profile gate
    -> finalize one verified episode with hashes and versions
    -> update edge weights
    -> replay the same task and observe changed candidate ranking
```

这个流程在 FastGELU、ReduceSum 和另一个未见 operator 上跑通以后，再扩充训练 task lineages 和 graph structure update。第一轮节点编辑只做一个有充分 response heterogeneity 的 split，或一个有充分 equivalence evidence 的 merge。它比同时开放所有结构操作更能检验论文真正依赖的训练过程。
