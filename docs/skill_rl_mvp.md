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
| SSH 910B 重采 | `xeon6.pku-dasys.cn:2222` **超时**；改用仓库内既有 HW 产物 |
| GLM-5.2 盲诊 | 成功：`fast_gelu/op_0005`、`gelu_mul/op_0005`（tile 过小） |
| Skill-RL 对比 | generic frozen → curated：primary **0.46→0.55**，actionability **0.67→0.91** |

报告副本：`tests/fixtures/skill_rl/inject_eval_report.json`

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

当前 **16** 个 unittest 通过。
