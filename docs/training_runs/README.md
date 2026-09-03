# Training runs（可提交摘要）

本目录用于收集 `feat/aprofgraph` 上的训练试验摘要。

## 约定

| 路径 | 是否提交 | 说明 |
| --- | --- | --- |
| `docs/training_runs/README.md` | 是 | 本说明 |
| `docs/training_runs/LATEST.md` | 是 | 指向最近一次 run |
| `docs/training_runs/run_*/REPORT.md` | 是 | 人类可读总结 |
| `docs/training_runs/run_*/summary.json` | 是 | 机器可读总结 |
| `docs/training_runs/run_*/episodes.sqlite` | 否 | EpisodeStore（体积大，本地保留） |
| `docs/training_runs/run_*/artifacts/` | 否 | CAS 源文件缓存 |
| `docs/training_runs/run_*/policy_*.json` | 建议提交小文件 | 固定图 policy checkpoint |

密钥与 SSH 不在此目录，见 `docs/local/environment.md`（已 gitignore）。

## 当前最小训练入口

```powershell
$env:PYTHONPATH="src"
python scripts/run_deepseek_trace_train_smoke.py
```

该脚本：DeepSeek V4 Flash 提案 → SkillGraph v0001 路由 → EpisodeStore → `fixed_graph_shrunk_edge_bias_v1` 训练。

注意：首轮 timing 可能是合同合法的 **placeholder**；只有 `measurement_source` 标明 live 910B 时才可当作真机结论。
