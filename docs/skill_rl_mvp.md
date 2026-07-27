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

## 两组 episode（勿混谈）

| Fixture | 含义 | 数字 |
| --- | --- | --- |
| A | 大 shape 弱启动（main summary） | 23548.65 → 91.178 μs（~258×），测量稳定 |
| B | 小 shape 强叙事（合作者轨迹合成） | 7.8 → 5.9 μs（~1.32×，blockDim=8）；专用化 ~5.8 仅附录 |

## 模块

```text
src/aprof/skill_rl/
  models.py episode_adapter.py reward.py library.py
  curator.py validation_gate.py sequential_rollout.py
  splits.py trainer.py simple_yaml.py

skills/aprof/skill_library/v0/   # 六族可执行 stub
tests/fixtures/skill_rl/         # Fixture A/B
```

## 跑单测

```bash
# Windows PowerShell
$env:PYTHONPATH="src"
python -m unittest discover -s tests/unit -p "test_skill_rl*.py" -v
```

## 离线一轮 SAGE-lite

```python
from aprof.skill_rl import adapt_fixture_a, adapt_fixture_b, run_offline_round

report = run_offline_round([adapt_fixture_a()], [adapt_fixture_b()], commit=False)
print(report["metrics"]["primary"])
print(report["metrics"]["specialized_appendix"])
```

`commit=True` 会在 `skills/aprof/skill_library/v1/` 写出新版本（建议在临时目录测）。

## 与 main E2E 的关系

main 上的 optimize candidate loop / memory / contracts 提供真实轨迹来源；本 MVP **消费**结构化 episode，不重跑 msprof。后续把 `optimization_memory.jsonl` 接到 `episode_adapter` 即可扩大 Train 集。
