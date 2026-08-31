# Skill-RL MVP（缺陷驱动）

离线 SAGE-lite：把六类 skill 当作可版本化外部参数 θ，用多目标 reward 验证「skill 变好」，而不是只刷最终 μs。

## 针对的四类缺陷

| ID | 缺陷 | 指标 / 门禁 |
| --- | --- | --- |
| D1 | 无 warmup/repeat | `measurement_ok`；不稳定则 speedup 不计 primary |
| D2 | 诊断泛泛 | skill 必须有 `actionable_edits` + `expected_metric_delta` |
| D3 | 利用率脱离可达上限 | `workload_awareness`；tiny/small 误报扣分 |
| D4 | 牺牲通用性追性能 | `benchmark_specialized` 只进 appendix，不进 primary |

契约：[skills/aprof/references/skill_rl_contracts.md](../skills/aprof/references/skill_rl_contracts.md)

## Episode 来源

| 集 | 含义 |
| --- | --- |
| Fixture A/B | 人工/合作者轨迹（大 shape 弱启动 vs 小 shape 强基线） |
| **inject_hw_train** | 由既有 **910B** `results_hw_with_labels` 生成的 22 条 inject→baseline 恢复轨迹（`--min-ratio 1.5`） |

构建：

```bash
python scripts/build_skill_rl_inject_hw_episodes.py --min-ratio 1.5
python scripts/run_skill_rl_inject_eval.py
```

## 真机 / API 尝试（2026-07-28）

| 项 | 结果 |
| --- | --- |
| SSH 910B 重采 | 已通；`collect_msprof_repeats_and_score.py` / `run_skill_rl_closed_loop_hw.py` |
| GLM-5.2 盲诊 | 成功：`fast_gelu/op_0005`、`gelu_mul/op_0005`（tile 过小） |
| Skill-RL 对比 | generic frozen → curated：primary **0.46→0.55**，actionability **0.67→0.91** |
| **闭环** | Curator→`v1_closed_loop`→应用 `tiling.increase_tile_length`（16→256）→910B 复测：fast_gelu **30.64→5.66 μs (~5.4×)**，gelu_mul **~9→~2 μs** 量级（见 closed_loop 报告） |

报告：`tests/fixtures/skill_rl/inject_eval_report.json`、`msprof_live_score_report.json`、`closed_loop_hw_report.json`

### SAGE 原版打分 ≠ 本仓库 primary

SAGE（ACL'26）：任务链上 **outcome reward \(r\in[0,1]\)**（如 AppWorld 任务是否完成）+ **Skill-integrated bonus**（生成 skill 被后续任务成功复用时 +1）；评测主表是 **TGC/SGC**、步数/token。  
AProf Skill-RL：面向 kernel 优化的 **多目标代理分**（speedup/actionability/workload/efficiency + 硬门禁），**不是** SAGE 同一套公式。我们借的是 Sequential Rollout / skill 版本化 / validation gate 的骨架。

## 模块

```text
src/aprof/skill_rl/          # models, adapter, reward, curator, gate, trainer, inject_hw
skills/aprof/skill_library/v0/
tests/fixtures/skill_rl/     # A/B + inject_hw_train/
scripts/build_skill_rl_inject_hw_episodes.py
scripts/run_skill_rl_inject_eval.py
```

## 跑单测

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests/unit -p "test_skill_rl*.py" -v
```

当前 **25** 个 unittest 通过。

## SAGE × Memory-R1 扩展（2026-08-11）

当前 demo 已从“规则 Curator + ID 累积”扩展为可执行的轻量训练骨架：

- Memory-R1 风格 `ADD / UPDATE / DELETE / NOOP`，含 tombstone、事务回滚、
  edit audit、library budget。
- 结构化 skill retriever 与 frozen/rule/sampled 三类 Manager policy。
- SAGE 风格真实任务链：记录 generated / retrieved / actually-used，后续成功
  复用才获得 reuse bonus。
- 训练奖励拆为 `outcome + reuse + downstream edit delta - cost/health`；
  原 `primary` 只保留为诊断报表。
- group-relative candidate advantage、轻量 contextual-bandit selector 与
  VERL-compatible JSONL 导出。
- applicator registry 支持 `tile_length / blockdim / tile_num`；910B runner
  支持 scenario JSON、skill version、correctness verify 和 CV 超限补采。

离线复现：

```powershell
$env:PYTHONPATH="src"
python scripts/run_sage_memory_r1_demo.py
python -m unittest discover -s tests/unit -p "test_skill_rl*.py" -v
```

产物：

- `tests/fixtures/skill_rl/sage_memory_r1_demo_report.json`
- `tests/fixtures/skill_rl/transition_dataset.jsonl`
- `tests/fixtures/skill_rl/closed_loop_blockdim_hw_report.json`（若 910B 不可达则
  明确写 `status=blocked`，不生成伪性能结果）

注意：历史 inject 的 warmup=3/repeat=1 仅用于 replay 候选排序；真实结论仍以
warmup=10/repeat≥5/CV≤5% 的 910B gate 为准。Memory-R1 官方仓库截至本次实现
仍未发布训练代码，因此本实现依据论文动作/下游 outcome 机制自建兼容接口，
不是其代码复刻。
