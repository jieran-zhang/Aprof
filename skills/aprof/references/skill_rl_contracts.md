# Skill-RL Contracts（缺陷驱动）

本文件定义 AProf Skill-RL MVP 的可机读 skill θ、episode 字段与多目标验证指标。  
目标：把六类 skill 从叙述性文档升级为可版本化、可编辑、可打分的外部参数。

## 四类真实缺陷 → 字段 / 奖励

| ID | 缺陷 | Skill / Episode 强制字段 | Reward 行为 |
| --- | --- | --- | --- |
| D1 | msprof 无 warmup/repeat | `measurement_policy` / `measurement` | 缺 warmup≥1 或 repeat≥3 → `measurement_ok=false`，speedup 分不计 primary |
| D2 | 诊断过于通用 | `actionable_edits[]`、`expected_metric_delta`、`linked_hypotheses` | 无可执行 edits → `actionability=0`；Curator 拒绝空话 UPDATE |
| D3 | 利用率脱离可达上限 | `workload_model`、`diagnosis_type`、`attainable_utilization` | tiny/small 上 `true_bottleneck` 且无额外证据 → 扣 `workload_awareness` |
| D4 | 过度追性能牺牲算法/通用性 | `scope`：`production_safe` \| `benchmark_specialized`；`semantic_status` | specialized 不进 primary reward；仅附录 |

## Skill YAML schema（v0）

```yaml
id: tiling.increase_blockdim_when_underused
family: tiling
version: 1
scope: production_safe
preconditions:
  - "diagnosis_type == true_bottleneck"
  - "workload_class in [normal, large] or elements_per_core sufficient"
actionable_edits:
  - adjust: blockdim
    notes: "split work across AIV cores; keep elems_per_core DataCopy-aligned"
expected_metric_delta:
  primary: TaskDuration_median_us
  direction: decrease
  min_effect_pct: 3.0
measurement_policy:
  warm_up: 10
  repeat: 5
  statistic: median
  max_cv: 0.05
linked_hypotheses:
  - ai_core_underused_single_blockdim
contraindications:
  - elems_per_core_misaligned
  - tiny_workload_fake_low_util
  - single_run_duration_as_proof
```

六族：`tiling`、`data_movement`、`pipeline_parallel`、`onchip_memory`、`ai_core_utilization`、`api_algorithm`。

## Episode / Round / Candidate（统一消费优化轨迹）

与 main 上 `optimization_*` 语义对齐的最小集合：

- `case_id`, `op_name`, `scenario_id`, `baseline_kind`：`naive` \| `strong`
- `workload_model.workload_class`, `total_elements`, …
- `measurement`: `warm_up`, `repeat`, `statistic`, `cv`, `samples_us`, `median_us`
- `rounds[]`: `label`, `baseline`, `selected_candidate`, `rejected_candidates[]`
- candidate：`scope`, `semantic_status`, `strategy_id`, `config`, `code_changes`, `accepted`, `reason`

## SkillEdit

`op`: `ADD` \| `UPDATE` \| `DEPRECATE`  
`skill_id`, `payload`（完整或部分 skill 字段）, `evidence_episode_ids[]`, `scope`

- 成功且 `production_safe` → UPDATE/ADD 主库  
- 失败候选 → DEPRECATE / 写入 contraindications  
- `benchmark_specialized` 成功 → 旁路标签，不写主 best

## RewardBreakdown（验证「skill 变好」）

Hard gates（任一失败 → primary=0）：

1. `correctness`: `bad==0` 且 `checked>0`
2. `semantics`: `semantic_status == preserved`（未知且未标 changed 时按 episode 默认）
3. `scope_primary`: 计入 primary 的候选必须 `production_safe`
4. `measurement`: warmup≥1、repeat≥3、有 median；否则 unstable

Soft scores（写入报告，合成 `primary`）：

| 字段 | 含义 |
| --- | --- |
| `speedup_score` | vs 协议 baseline；需 ≥ `min_effect_pct` |
| `actionability` | 轨迹/skill 含可映射 `strategy_id` 或 `actionable_edits` |
| `workload_awareness` | 不在 tiny/small 上误报真瓶颈 |
| `efficiency` | 接受加速所用候选更少、拒绝可解释则加分 |
| `specialized_appendix_speedup` | 仅附录，不进 primary |

**主对比**：同一组 episodes 上 `skill_lib@v0`（frozen）vs `skill_lib@vN`（curated）的 `primary` 与 `actionability`。  
禁止仅用大 shape 弱启动的 258× 作为唯一 headline；小 shape 强 baseline（约 1.32×）必须同报。

## SAGE-lite 流程

Train episodes → Curator 提案 edits → Dev Validation Gate（hard + primary 不下降）→ commit → Test 只评估。  
Sequential rollout：同 `scenario_id` 内按序累积已 commit 的 skill ids。
