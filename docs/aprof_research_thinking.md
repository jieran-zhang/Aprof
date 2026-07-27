# AProf 研究思路整理（活文档）

> **定位**：记录我们对「问题诊断模块 → Profile-Guided 端到端调优 → Skill Library RL 自改进」的统一结论。  
> **用法**：多轮对话后在此追加「已共识 / 待决 / 修正」；与对外汇报稿 `blind_diagnosis_framework_briefing.md` 分工——那边讲现状与数字，这边讲研究叙事与设计决策。  
> **状态**：初稿（2026-07-27），尚未全部共识。

---

## 0. 文档维护约定

| 标记 | 含义 |
|------|------|
| ✅ 已共识 | 多轮对齐后可写进论文/设计的结论 |
| 🟡 草稿 | 方向明确，措辞或边界未定 |
| 🔴 待决 | 需要继续讨论 |
| ⚠ 能力缺口 | 叙事已有，仓库尚未对齐 |

修订请在文末「修订记录」追加一行，不要静默改掉旧结论。

---

## 1. 两条投稿线如何拆

| 会议 | 时间 | 工作标题（草稿） | 重心 |
|------|------|------------------|------|
| **DAC** | 2026-11 中旬 | Profile-Guided Agentic Kernel Optimization for Ascend AI Accelerators | Ascend 上的 **profile-guided 端到端自动优化 demo**；不过度消耗 ASPLOS 主线 |
| **ASPLOS** | 2027-03 初 | Reinforcement Learning Based Skill Libraries Training for Cross-Accelerator Kernel Optimization | **Skill library 作为可训外部参数**；跨硬件（Ascend / Tenstorrent / SDA）特化与迁移 |

🟡 **原则**：DAC 证明「观测–推理–改写–验证」在 Ascend 上跑通且有效；ASPLOS 证明「同一套 multi-agent base + 不同 skill lib 后训练」带来硬件特化与可迁移的优化能力。

---

## 2. DAC 叙事：端到端 Profile-Guided Agentic Kernel Optimization

### 2.1 目标陈述（🟡 草稿，可直接改写进 abstract）

在 Profile-Guided Agentic Kernel Optimization 工作流中，AProf 将 Ascend AI Accelerators 上的运行 profile 转化为结构化性能信号，自动定位 kernel 级热点、瓶颈来源与可优化空间。

基于这些 profile-guided 证据，agent 能够生成针对性的 kernel 优化策略，例如算子融合、访存优化、tiling 调整、并行调度改写或实现替换。

优化后的 kernel 会被自动执行、重新 profiling 并与 baseline 对比，形成「观测–推理–改写–验证」的闭环端到端性能调优 demo。

### 2.2 闭环四步（论文语言）

```text
Observe   : msprof / aprof → 结构化信号（CSV、trace、roofline proxy）
Reason    : Diagnosis Agent + skill 检索 → 瓶颈族 / 根因假设 / metric 佐证
Rewrite   : Optimization Agent → 针对性 kernel 改写（tiling / 访存 / 流水 / API…）
Verify    : 编译 + 正确性 + 再 profile + vs baseline speedup / regression
         ↺ 失败或收益不足则回到 Reason / Rewrite
```

### 2.3 与当前仓库的对齐（⚠ 能力缺口 — 讨论用）

| 闭环环节 | 仓库现状（2026-07） | DAC 需要补到什么程度 |
|----------|--------------------|----------------------|
| **Observe** | Profiling skill、remote deploy、`run.sh hw`、msprof 产物解析 | 端到端 demo 默认吃真实/仿真 profile，而不只是源码盲诊 |
| **Reason** | `ascendc-aprof-diagnosis` 六类矩阵 + GLM 盲诊评测；workflow Step1–4 设计完整 | 诊断输出稳定成 Optimization 可消费的契约（问题族 + 建议动作 + metric） |
| **Rewrite** | ⚠ **基本缺失**：无独立 Optimization Agent / 自动改写 skill；注入 skill 是「造坏」不是「修好」 | 至少 1–2 类可自动应用的改写（如 tileLength、double buffer、blockDim）+ 人工可审 patch |
| **Verify** | 有 compile/verify/hw 管线与 injected_ops 验证；⚠ **缺「改写后 vs baseline 自动对比」编排** | 一键：改写 → build → accuracy → re-profile → ΔTask Duration / speedup 报告 |
| **Benchmark 造题** | 注入 + 盲诊对齐已较成熟（gold12 / injected_ops） | DAC 可用「注入劣化再恢复」作可控 demo；真实慢 kernel 作展示 |

🟡 **当前诚实表述建议**：

- 已具备：**profile 结构化 + 诊断归因（含盲诊评测）+ 直调工程跑通/上板**。
- 未齐：**自动改写 Agent + 相对 baseline 的闭环验证编排**。
- 因此「现在应该能够跑好端到端」若指完整「观测–推理–改写–验证」，在仓库层面仍是 **目标态**；若指「诊断↔采集」半闭环，则已接近。

🔴 **待决**：DAC demo 的最小可发表闭环是什么？

候选 A：注入劣化 case → 诊断命中 → **手工/半自动** 应用配方改写 → 自动 verify+speedup  
候选 B：全自动 Optimization Agent（受限动作空间）  
候选 C：先只发诊断+profiling 系统，改写作为 case study（偏弱，与 2.1 陈述不完全一致）

---

## 3. ASPLOS 叙事：Skill Library 作为可训外部参数

### 3.1 核心 statement（🟡 草稿）

用 RL 增强 agent 的 **skill library 自改进**能力：先搭出一个类似「预训练模型」的 **multi-agent 基座系统**，给出诊断与调优框架；其中可训的「参数」是 **skill lib**，对系统做 RL 训练时，每次反传意义上的「梯度」改变的是 skill lib（ADD / UPDATE / MERGE / SPLIT / DEPRECATE），而不是（或极少）更新 LLM 权重。

据此可针对 SDA 提出一个 base 系统，在 Ascend、Tenstorrent 上分别做 RL 后训练，最终再检测算子优化能力（含跨硬件迁移 / 负迁移）。

### 3.2 训练视角对照表（✅ 方向已共识，术语可再打磨）

| 传统 DL | 本工作类比 |
|---------|------------|
| 预训练模型权重 | Multi-agent system = base policy / inference engine |
| 可训参数 θ | **Skill library**（持久、可版本化的外部参数） |
| 激活 / 上下文 | Episode memory（单次 kernel 优化轨迹与证据） |
| 损失 / 奖励 | correctness + speedup + profiling evidence + cost |
| 反传更新 θ | RL 选择并提交 skill edits（离散、门控） |
| LLM weights | frozen 或 mostly frozen |

### 3.3 预期贡献（🟡）

1. **Profiling-grounded skill RL**  
   把 kernel profiling evidence 纳入 skill-library self-improvement，而不是只用 final task success。

2. **Skill library as trainable external parameters**  
   提出 memory-to-skill 的离散「反传」机制，用 RL 优化 add/update/merge/delete（及 split/deprecate）等 skill edits。

3. **Hardware-specialized post-training**  
   从同一 base multi-agent optimizer 出发，在 SDA、Ascend、Tenstorrent 上训练出不同的 hardware-specific skill libraries，并评估跨硬件迁移与负迁移。

### 3.4 Base Multi-Agent System（🟡 角色表）

| Agent | 职责 | 与当前 AProf 映射 |
|-------|------|-------------------|
| **Profiler Agent** | 收集 runtime、hardware counter、memory/compute bottleneck | ≈ `aprof-profiling-agent` + remote deploy / msprof |
| **Diagnosis Agent** | 解释瓶颈（memory bound、occupancy、vectorization、bank conflict、DMA overlap…） | ≈ `aprof-diagnosis-agent` + 六类诊断矩阵（Ascend 术语已落地；跨硬件需抽象层） |
| **Optimization Agent** | 根据诊断 + retrieved skills 生成 kernel 修改 | ⚠ 待建 |
| **Verification Agent** | 编译、正确性、benchmark、多 shape regression | 部分在 inject/deploy/run.sh；⚠ 缺统一 Agent + speedup 契约 |
| **Skill Curator Agent** | episode memory → skill edit；决定 add/update/merge/delete | ⚠ 待建（论文主创新落点之一） |
| **Router Agent** | 按 op / hardware / profile 检索 skill | ⚠ 部分存在于 source-hypothesis-routing；非可训检索策略 |

### 3.5 Memory System（🟡）

- 存：当前（及历史）kernel 优化 episode 的轨迹与证据。  
- 建议字段（未定稿）：`kernel_id`、`hardware`、`profile_signals`、`diagnosis`、`skills_used`、`edits`、`verify_metrics`、`reward`、`failure_modes`。  
- 与现有产物关系：可把 `single_case_diagnosis.json`、`profiling_results.json`、patch diff、`offline_alignment` 视为 episode 的可序列化片段。

### 3.6 Skill Library 分层与 Contract（🟡 — 需单独定 schema）

| 层 | 内容 |
|----|------|
| **base skills** | 跨硬件通用优化知识（如「减小无效同步」「增大有效 tile」抽象原则） |
| **hardware skills** | Ascend-specific / Tenstorrent-specific / SDA-specific |
| **operator skills** | matmul / conv / attention / reduce / elementwise fusion |
| **meta skills** | 如何诊断、如何选 profiler、如何比较 noisy benchmark |

Skill 应有 **定义好的 contract 结构**（版本、前置条件、适用硬件、输入信号、动作、验证门、失效条件）。  
现有 `skills/aprof/references/contracts.md` 覆盖诊断/profiling JSON，**尚未**覆盖「可 RL 编辑的 skill 对象」与 edit 操作语义。

🔴 **待决**：Skill 最小 schema（YAML/JSON）长什么样？与现有 `SKILL.md` 文件是 1:1 还是「markdown 叙述 + 结构化 front-matter/sidecar」？

### 3.7 Memory → Skill Policy（Skill Optimizer）（🟡 论文方法论核心）

独立、可训练、受约束的 Skill Optimizer：

1. **Credit Assignment**  
   判断成功/失败与哪些 skill、哪些 profiling signal、哪些 code edit 相关。

2. **Candidate Edit Generation**  
   对 skill library 生成离散编辑候选：`ADD` / `UPDATE` / `SPLIT` / `MERGE` / `DEPRECATE`。

3. **Validation Gate**  
   在 held-out kernels、unseen shapes、不同输入规模上验证候选 edit。

4. **Commit / Reject**  
   只有通过统计阈值与 regression tests 的 edit 才写入 skill library。

Reward（草稿）：`correctness + speedup + profiling evidence quality − cost`（API/编译/上板成本）。

---

## 4. 问题诊断模块在总图中的位置

### 4.1 现状摘要（✅ 工程事实）

- **知识本体**：`skills/aprof/diagnosis/`（六类矩阵 + 路由 + roofline）。  
- **镜像造题**：`ascendc-aprof-inject-problems`（同六类，GT 隔离）。  
- **评测**：GLM 盲诊；gold12 family≈83%，injected_ops family≈88%（id hit 更弱）。  
- **并行旧路径**：`src/aprof/agents/diagnosis/` 规则启发式，不宜当作论文主路径。

### 4.2 诊断模块在两条论文中的角色（🟡）

| 论文 | 诊断模块角色 |
|------|----------------|
| DAC | 闭环中的 **Reason**：profile → 结构化瓶颈 → 驱动改写；盲诊准确率可作为系统能力旁证 |
| ASPLOS | Diagnosis skills 是 **skill lib 的一类可训参数**；profiling-grounded reward 依赖诊断是否选对信号 |

### 4.3 诊断相关待决（🔴）

1. 六类族是否升格为跨硬件「瓶颈本体」，Ascend 指标只是 specialization？  
2. 盲诊 family/id 指标是否足以支撑 DAC；是否要加「建议动作可执行率」？  
3. Python rules 路径：归档说明 / 淘汰 / 仅作 baseline comparator？

---

## 5. 相关工作锚点（阅读笔记位）

| 论文 | 与我们的关系（草稿） |
|------|----------------------|
| ‼️ Wang et al., *RL for self-improving agent with skill library*, ACL 2026 | 最近邻：skill library + RL 自改进；我们差分在 **profiling-grounded** + **kernel/hardware** |
| ‼️ Yan et al., *Memory-R1*, ACL 2026 | memory 管理与利用的 RL；我们对齐「episode memory → skill edit」，但强调硬件证据与 commit gate |
| Pu et al., *SkillOps*, arXiv 2026 | skill 作为自维护软件生态；可对照 contract / lifecycle（add/merge/deprecate） |
| Du et al., *Survey on LLM agent optimization*, CSUR 2026 | 综述定位；用来划清「训 LLM vs 训外部 skill」 |

🟡 写 related work 时强调三差分：**(i) kernel profiling 进入 reward/credit**；**(ii) 离散 skill edit + validation gate**；**(iii) 多加速器后训练与迁移评估**。

---

## 6. 投稿与工程里程碑（🟡）

### 6.1 硬截止日期（⚠ 修正）

ASPLOS 2027 双轮截止（AoE）：

| Cycle | Full paper | Notification | 状态（相对 2026-07-28） |
|-------|------------|--------------|------------------------|
| April | 2026-04-15 | 2026-07-27 | **已过** |
| September | **2026-09-09** | 2026-12-21 | **唯一剩余窗口 ≈ 6 周** |

会议约 2027-04（Crete）。原先「2027-03 投 ASPLOS」若指开会时间，**真正可投的是 2026-09-09**；完整「三硬件 + 完整 RL + 迁移」很难在 6 周内做成 ASPLOS 级 artifact。

### 6.2 战略分叉（🔴 必须先选）

| 路径 | 含义 | 建议 |
|------|------|------|
| **A. ASPLOS'27 Sept 冲刺** | 6 周内交一篇**可站得住**的 systems/methodology 短闭环论文 | 砍 scope：Ascend-only 或 Ascend+弱第二硬件；RL 做 **最小可训 Curator**，不是完整三硬件特化 |
| **B. ASPLOS'28 主投** | 用一年做满 skill-RL + 跨硬件 | DAC'26 或 workshop 放 Ascend E2E；ASPLOS 吃满贡献 1–3 |
| **C. Sept 投薄版 + 拒稿改 ASPLOS'28** | 用 Sept 换审稿意见 | 仅当 A 的最小故事已能跑通数字 |

🟡 **默认建议（若「主目标是 ASPLOS」且不牺牲质量）**：走 **B**，把「现在–9 月」当成 **基座与数据飞轮建设期**，而不是硬凑完整贡献 3。若必须打 ASPLOS'27 牌子，走 **A** 并立刻锁最小 claim（见 §9）。

### 6.3 工程依赖顺序（与投稿目标无关的正确开发序）

**不要先写 RL trainer。** 没有 episode、reward、skill schema、改写–验证闭环，RL 没有可训对象。

```text
P0  Episode 闭环（Ascend）     ← 没有这个，后面全是空转
P1  Skill contract + 版本库     ← θ 的具体形态
P2  受限动作空间的 Rewrite/Verify
P3  Skill Curator（先规则/LLM，再 RL）
P4  第二硬件适配（同一 episode schema）
P5  RL 后训练 + 迁移/负迁移实验
```

旧甘特（DAC→ASPLOS）保留为愿景；以 §9 的冲刺/长线表为准。

🔴 **待决**：DAC 是否完全不写 RL？  
（若主投 ASPLOS'28：DAC 可写满 Ascend E2E，RL 一句 future work。若冲 ASPLOS'27：DAC 可降级或取消，避免双线分心。）

---

## 7. 本轮对话留下的开放问题清单

供下一轮优先拍板：

1. 「端到端已能跑好」——对外口径是 **目标态** 还是 **已交付**？缺口表（§2.3）是否认可？  
2. DAC 最小闭环选 A / B / C（§2.3）？  
3. Skill 对象 schema 与现有 `SKILL.md` 的关系？  
4. 诊断六类是否成为跨硬件瓶颈本体，还是 Ascend-only taxonomy？  
5. ASPLOS 的第三条硬件（SDA）与我们现有工程边界如何切？  
6. 是否新建独立 Optimization / Verification / Curator Agent 目录，还是先挂在 `plugins/aprof-performance-workflow` 状态机里扩步？  
7. **ASPLOS 路径选 A / B / C（§6.2）？** → 用户确认冲 **ASPLOS'27 Sept（2026-09-09）**  
8. 生成式 inject 集 vs 真实慢算子集：train/dev/test 怎么切？  
9. 是否把 `origin/main` 的 optimization skill **合入当前 inject 分支**（需解决 Python 包删除冲突）？

---

## 8. 修订记录

| 日期 | 变更 | 来源 |
|------|------|------|
| 2026-07-27 | 初稿：写入 DAC E2E 陈述、ASPLOS skill-RL statement、agent 角色表、与仓库能力缺口对照、开放问题 | 用户口述 + 仓库摸底 |
| 2026-07-28 | 修正 ASPLOS'27 截止（仅剩 Sept 9）；写入战略分叉 A/B/C、P0–P5 开发序、§9 ASPLOS-first 路线 | 用户确认主投 ASPLOS |
| 2026-07-28 | 拉取 `origin/main`：核实合作者 E2E + Feasibility Gate + fast_gelu 三轮优化数字；写入 §10 审计与 §11 skill-RL 实验设计 | fetch + 读 summary/skills |
| 2026-07-28 | 落地 Skill-RL MVP（缺陷驱动指标 + 双 fixture + SAGE-lite）；见 §11.6 与 `docs/skill_rl_mvp.md` | feat/skill-rl-mvp |

---

## 9. ASPLOS-first 往后怎么开发（建议）

### 9.1 一句话

把现有「诊断 + 注入 + 盲诊」当成 **base policy 的 Reason 模块**；下一步唯一阻塞 ASPLOS 故事的是 **可计量的优化 episode**（改写 → 验证 → reward），然后才是把 episode 沉淀成 **可版本化 skill θ**，最后才是 RL。

**2026-07-28 更新**：`origin/main` 已具备 Optimization Agent + gates + `optimization_memory.jsonl` 契约，以及一份可复述的 fast_gelu 三轮 episode（§10）。当前工作分支 `feat/new-ops-benchmark-inject` **尚未包含** `skills/aprof/optimization/`。Skill-RL 的下一步是：把 main 的 E2E 优化闭环与 inject 基准集合并，再在之上加 Curator/RL，而不是从零重写 Rewrite。

### 9.2–9.5

（见上文历史内容：路径 B/A、P0–P5、审稿雷区。）

---

## 10. 合作者 E2E 声称审计（`origin/main`，2026-07-28）

### 10.1 代码位置（已 fetch，不在当前 HEAD）

| 声称 | 仓库证据 | 结论 |
|------|----------|------|
| 完整 aprof 端到端 demo | commit `8467d4b`：新增 `skills/aprof/optimization/`、workflow 扩到 optional optimization、contracts 扩 `optimization_*` | ✅ 框架在 main 上已落地 |
| Mandatory Workload & Roofline Feasibility Gate | `workload-aware-diagnosis.md`；workflow-details 中 `WorkloadAndRooflineFeasibility`；contracts 强制 `workload_model` + `diagnosis_type` | ✅ 名称与语义一致（文档 gate，非独立可执行二进制） |
| 六类问题分支分别存知识 | diagnosis 六矩阵 + optimization 六 `*-optimization-strategies.md` + routing | ✅ |
| GPT 对官方 fast_gelu 三轮优化 23548.65→91.178 us | `tests/aprof_fast_gelu_three_round_optimization_summary.json` | ✅ 数字逐项吻合 |

### 10.2 三轮事实（msprof Task Duration，median of 5，accuracy bad=0）

| Round | 策略 | 配置变化 | median μs | 相对该轮 baseline |
|-------|------|----------|-----------|-------------------|
| 起点 | — | blockdim=1, tile=256 | **23548.65** | — |
| 1 | multicore launch | blockdim **1→32** | **758.505** | ~31.0× |
| 2 | 增大 tile | tile **256→10240** | **95.398** | ~8.0× |
| 3 | 删未用 bBuf + 再增 tile | tile **10240→15360** | **91.178** | ~1.055×（过 3% 门限） |
| 合计 | — | 32 / 15360 | **91.178** | **~258× vs 原始** |

过程细节支持合作者口述：blockdim/tileLength 为主；第 3 轮去掉未使用 `bBuf/bLocal` 以腾 UB 再放大 tile。有拒绝样例（blockdim=40 精度失败；单加 tile=12288 仅 1.77% 未过 3% 门限；只删 buffer 反而变慢）。

### 10.3 对 ASPLOS 实验的含义（重要）

1. **E2E 可讲**：Observe→Reason→Rewrite→Verify 在 Ascend + 一个算子上已有可引用产物。  
2. **baseline 偏弱**：起点 `blockdim=1` 跑满核规模数据，审稿人会认为第 1 轮是「修启动配置」而非深层优化。论文必须同时报：  
   - vs naive launch（现有 258×）  
   - vs **强 baseline**（例如已用满核 + 合理 tile 的官方/手工配置，只看 round2+3 的边际收益）  
3. **动作空间窄**：主要是 Host tiling 旋钮 + 删死 buffer；六类知识库远宽于这次实际用到的策略——实验上要证明 Router 会选对族，而不只是手调两个超参。  
4. **分支分裂**：当前 `feat/new-ops-benchmark-inject` 有生成式 inject/盲诊；`main` 有 optimization。合并时注意 main 曾大幅删减 `src/aprof` Python 包——**不要盲目 merge**，宜 worktree 或挑文件合入。  
5. **本地「试一试」**：无 NPU 时只能 dry-run 计划/读 skill；复现 91μs 必须在有 msprof 的机器上按 summary 的 workdir 策略重跑。

---

## 11. Skill-RL 怎么搭 + 训练集/验证集（对照论文）

### 11.1 论文里怎么切数据（Wang et al. ACL'26 SAGE）

- 数据集按 **scenario** 组织；Train / Dev / Test-Normal / Test-Challenge。  
- Train：SFT + RL；Dev：选 checkpoint；Test：泛化（Challenge 含未见 API）。  
- **Sequential rollout**：同 scenario 内任务链上积累 skill，测 skill 复用（SGC）。  
- 流程常是 **专家轨迹 SFT → 再 RL**（纯 RL 指令遵循不够时）。  
- Reward：任务成功 + skill 质量（skill-integrated），不只 final success。

Memory-R1：强调 memory 操作策略可 RL；我们对应的是 **episode → skill edit**，且必须过 validation gate。

### 11.2 映射到 AProf（建议的实验骨架）

把一次「kernel 优化」当成 AppWorld 的一个 task；把「同算子多 shape / 同问题族多算子」当成 scenario。

| Split | 建议构成 | 用途 |
|-------|----------|------|
| **Train** | 生成式 inject（`aprof_injected_ops` + gold inject）：已知 `problem_family`，可造「劣化→恢复」episode | 产生专家轨迹 / 离线 skill edit 候选；训 Curator 或做 SFT 示范 |
| **Dev** | 同分布 held-out inject（按 **算子×问题族** 分层抽样，禁止泄漏同一 op 的全部 shape） | 调门限、选 skill-lib 版本、early stop |
| **Test-A（in-dist）** | 未见 inject id / 未见 shape | 报 speedup、诊断族命中、skill 复用 |
| **Test-B（real）** | 真实慢算子 / 官方参考（如 ops-nn fast_gelu、其他 production kernel） | 防「只刷生成题」；对应 SAGE 的 Challenge |
| **Test-C（optional）** | 第二硬件或跨 op 族 | 仅当来得及时；否则 Sept 砍掉 |

**关键原则**：生成式数据适合 **可复现、可标注、可 RL**；真实算子适合 **外推**。两者都要，且主表不能只有生成式。

### 11.3 最小可投稿的 Skill-RL「框架」长什么样（6 周现实）

不必一上来 GRPO。Sept 可发表的最小栈：

```text
Episode runner（已有雏形）
  profile → diagnose(+workload gate) → optimize(candidate loop) → verify
  → 写 episode.json / 追加 optimization_memory.jsonl

Skill θ（结构化）
  六类 diagnosis + 六类 optimization strategies（main 已有 md）
  + 可版本化 sidecar（适用条件、禁忌、期望 metric 移动）

Curator（先离线）
  从成功/失败 episode 提案 ADD/UPDATE/DEPRECATE
  Validation gate：在 Dev inject 上重跑，过阈值才 commit → skill_lib@vN

对比实验（主表）
  frozen skill_lib@v0  vs  curated/RL-updated @vN
  指标：correctness-constrained median speedup、轮次/候选数、族命中、失败回收率
```

若时间够：再对 Curator 策略做小型 RL（或 bandit）；LLM 权重保持 frozen。

### 11.4 诊断模块「摸索出去」的实验问题（可写进论文 RQ）

1. Workload gate 是否降低假阳性优化（tiny shape 上乱改）？  
2. 六类分支知识是否比单一大 prompt 更好（ablation：打乱路由 / 去掉族 reference）？  
3. 生成式 train 得到的 skill 能否迁移到真实 Test-B？  
4. Skill update 是否减少重复失败候选（读 memory 前后对比）？

### 11.5 下周可执行动作（在「能试」的前提下）

1. `git worktree add ../Aprof-main origin/main`，只读跑通 optimization skill 文档与 contracts（勿搅乱 inject 分支）。  
2. 把 `tests/aprof_fast_gelu_three_round_optimization_summary.json` 当作 **第一条黄金 episode**，反推 `episode.json` schema。  
3. 从 inject 集划 Train/Dev/Test-A 清单（按 op×family 分层），单独列 Test-B 真实算子名单。  
4. 定强 baseline 协议：禁止用 blockdim=1 当唯一对照。  
5. 有 910B 时：对 1–2 个 inject 劣化 case 跑「恢复」闭环，验证 recipe 是否可自动。

### 11.6 Skill 优化方向与验证指标（2026-07-28 落地）

**需要**：skill 优化优先修可执行性、workload-aware、测量契约、`production_safe`；验证时 **代码性能必要但不充分**。

已在分支 `feat/skill-rl-mvp` 落地离线 SAGE-lite：

- 契约：`skills/aprof/references/skill_rl_contracts.md`
- 代码：`src/aprof/skill_rl/`
- 说明：`docs/skill_rl_mvp.md`
- Fixture A（大 shape 弱启动）+ Fixture B（2048 / ~1.32× + specialized 附录）
- 主对比：`frozen skill_lib@v0` vs curated（`run_offline_round`）的 `metrics.primary`；specialized 走 `metrics.specialized_appendix`

| 指标 | 用途 |
| --- | --- |
| correctness / semantics / scope | Hard gates |
| measurement (warmup/repeat) | 打 D1 |
| speedup（naive vs strong 分报） | 性能，但受 measurement 门控 |
| actionability | 打 D2 |
| workload_awareness | 打 D3 |
| specialized_appendix_speedup | 打 D4（不进 primary） |

---

## 12. （原 §9 详细条目保留区）

### 路径与审稿预埋（摘要）

- 不要先写 RL trainer；先 episode + skill 版本 + Curator gate。  
- 主表：correctness-constrained speedup + skill-lib 版本对比；盲诊准确率降附录。  
- 跨硬件若 Sept 来不及，删贡献 3，保住 profiling-grounded skill update。
|
