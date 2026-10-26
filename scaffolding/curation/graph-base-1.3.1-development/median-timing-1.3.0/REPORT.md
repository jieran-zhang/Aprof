# 1.3.0 中位数探索计时：离线比较与维护报告

本轮采用显式版本化的试用探索统计协议 `median_stability_exploration_v2`／`bounded_outlier_v2`，runtime **0.8.2**。包仍未封版，不切换默认版本；D v0007、P v0004、O v0007、routing v0006、condition policy v0002保持。原5预热/20正式、逐轮清L2与完整调用采集不变，正确性、GM≥1.03、最坏case回归≤3%、HAP目标及Action—P/O准入不变。

新增规则见[中位数稳定性v2](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-profiling/references/median-stability-v2.md)：轮内4/20与CV≤10%、双方原始中位数漂移、剔除敏感性及收益分别报告。阈值仅为本任务试用值；15%的CV只列作离线敏感性，未采用。旧schema及旧2/20、5%结果继续按原义回放，不能事后把旧capture改成测前新协议。

## 数据及复算口径

入口是2026-10-21累计round-results.json，覆盖GridSampler3D、Maximum各R1～R15，共30轮、600个候选case和对应父本。按原官方parent comparison的最终窗口复算轮内门槛；同时读取首测及所有登记复验，用原始中位数检查同实现、workload和测量口径的漂移。所有数据都来自既有capture/Task CSV，不调用collector、oracle或NPU。R0比较、HAP和原交接状态不重写；本表比较父本，不把相对R0的大收益误称本轮增量。

[冻结证据](evidence-identity.json)绑定包内压缩归档，包含原入口、请求/结果、选择记录、capture、原始Task CSV及声明的精确文本与hash。脚本核对文本hash、capture→CSV绑定，重新解析完整20调用。它不重新认证原始正确性、设备状态或所有native/PROF回执。相同源码/二进制/workload还不足以证明分布不变，缺实际分布或设备动态信息的项仍有限制。

## 轮内阈值敏感性

下列“双方20 case达标轮数”只检查轮内异常上限和CV，**不是完整v2判定或历史准入数**。

| 算子 | 异常上限 / CV上限 | B超限组 | A超限组 | 双方20 case均达标 |
|---|---|---:|---:|---:|
| GridSampler3D | 2/20 / 5% | 21 | 21 | 0/15 |
| GridSampler3D | 3/20 / 10% | 5 | 3 | 9/15 |
| GridSampler3D | 4/20 / 10% | 1 | 1 | 13/15 |
| GridSampler3D | 4/20 / 15% | 0 | 1 | 14/15 |
| Maximum | 2/20 / 5% | 1 | 2 | 13/15 |
| Maximum | 3/20 / 10% | 0 | 0 | 15/15 |
| Maximum | 4/20 / 10% | 0 | 0 | 15/15 |
| Maximum | 4/20 / 15% | 0 | 0 | 15/15 |

GridSampler3D的旧无效组中，B21组有16组漂移≤3%、17组≤5%，绝对漂移中位数1.83%；A21组分别14、18组和1.85%，与输入证据一致。这支持区分轮内尖峰和中位数漂移，但并不证明4/20均是外部噪声。Maximum旧超限组仅B1/A2，样本不足以泛化。

## 逐轮结论变化

以下accepted/rejected/inconclusive均在“反事实分析”列内：是假设应用新统计逻辑的输出，**不是新生成的正式timing artifact，也不重新接纳历史候选**。首列为冻结历史工程结果；“末窗”只用原最终窗口作新规则分析，“全部窗口”再纳入首测及所有登记复验。3%～5%漂移保留caution；>5%、轮内超限或观测范围跨工程门槛时仍需复核。原始和处理后的点估计都在[机器明细](comparison.json)。

| 算子/轮 | 原结论 | 新末窗分析 | 加入全部窗口 | 新GM/父本 | 最坏case回归 | 全窗口复核原因 |
|---|---|---|---|---:|---:|---|
| Grid R1 | inconclusive | rejected | rejected | 1.2186× | 230.09% | 至少一个 case 回归超过 3% |
| Grid R2 | inconclusive | accepted | inconclusive | 5.8128× | 0.33% | candidate/case 14 波动较大／需复核；不能仅凭稳定中位数自动通过 |
| Grid R3 | inconclusive | inconclusive | inconclusive | 1.7045× | 6.03% | baseline/case 14 波动较大／需复核；不能仅凭稳定中位数自动通过 |
| Grid R4 | inconclusive | accepted | accepted | 1.4303× | 0.15% | 符合原工程门槛 |
| Grid R5 | inconclusive | rejected | rejected | 1.4781× | 14.80% | 至少一个 case 回归超过 3% |
| Grid R6 | inconclusive | accepted | inconclusive | 1.7110× | 0.82% | baseline/case 2 波动较大／需复核；不能仅凭稳定中位数自动通过；candidate/case 2 波动较大／需复核；不能仅凭稳定中位数自动通过；baseline/case 14 波动较大／需复核；不能仅凭稳定中位数自动通过；已观察窗口／剔除敏感性跨越工程门槛，不能把小收益当稳定优化 |
| Grid R7 | inconclusive | inconclusive | inconclusive | 1.0271× | 15.12% | candidate/case 18 原始中位数跨窗口漂移超过 5%；candidate/case 2 波动较大／需复核；不能仅凭稳定中位数自动通过；剔除改变工程门槛结论；需解释原始与处理后差异 |
| Grid R8 | inconclusive | rejected | inconclusive | 1.0674× | 12.72% | candidate/case 2 波动较大／需复核；不能仅凭稳定中位数自动通过 |
| Grid R9 | inconclusive | rejected | inconclusive | 1.0697× | 15.80% | candidate/case 14 原始中位数跨窗口漂移超过 5%；baseline/case 18 原始中位数跨窗口漂移超过 5%；baseline/case 14 波动较大／需复核；不能仅凭稳定中位数自动通过 |
| Grid R10 | inconclusive | rejected | inconclusive | 1.0311× | 54.96% | baseline/case 14 原始中位数跨窗口漂移超过 5%；candidate/case 14 原始中位数跨窗口漂移超过 5%；baseline/case 16 原始中位数跨窗口漂移超过 5%；candidate/case 16 原始中位数跨窗口漂移超过 5%；candidate/case 14 波动较大／需复核；不能仅凭稳定中位数自动通过 |
| Grid R11 | inconclusive | rejected | inconclusive | 1.0723× | 6.94% | baseline/case 2 原始中位数跨窗口漂移超过 5%；candidate/case 18 原始中位数跨窗口漂移超过 5%；baseline/case 14 波动较大／需复核；不能仅凭稳定中位数自动通过 |
| Grid R12 | inconclusive | rejected | inconclusive | 1.0182× | 76.32% | baseline/case 3 原始中位数跨窗口漂移超过 5% |
| Grid R13 | inconclusive | rejected | inconclusive | 1.0271× | 9.17% | baseline/case 18 原始中位数跨窗口漂移超过 5%；candidate/case 18 原始中位数跨窗口漂移超过 5% |
| Grid R14 | inconclusive | rejected | inconclusive | 0.6943× | 56154.35% | candidate/case 3 原始中位数跨窗口漂移超过 5% |
| Grid R15 | inconclusive | rejected | inconclusive | 0.9710× | 22.55% | candidate/case 8 原始中位数跨窗口漂移超过 5%；candidate/case 14 原始中位数跨窗口漂移超过 5%；baseline/case 18 原始中位数跨窗口漂移超过 5% |
| Maximum R1 | accepted | accepted | accepted | 2.2084× | 0.49% | 符合原工程门槛 |
| Maximum R2 | accepted | accepted | accepted | 1.3919× | 1.92% | 符合原工程门槛 |
| Maximum R3 | rejected | rejected | inconclusive | 1.0354× | 4.44% | 已观察窗口／剔除敏感性跨越工程门槛，不能把小收益当稳定优化 |
| Maximum R4 | accepted | accepted | accepted | 1.2013× | 2.18% | 符合原工程门槛 |
| Maximum R5 | accepted | accepted | accepted | 1.0376× | 2.26% | 符合原工程门槛 |
| Maximum R6 | rejected | rejected | rejected | 1.0033× | 5.67% | 等权几何中位数比未达到 1.03；至少一个 case 回归超过 3% |
| Maximum R7 | accepted | accepted | accepted | 1.2949× | 1.93% | 符合原工程门槛 |
| Maximum R8 | rejected | rejected | rejected | 0.9719× | 83.13% | 等权几何中位数比未达到 1.03；至少一个 case 回归超过 3% |
| Maximum R9 | rejected | rejected | rejected | 0.9508× | 196.76% | 等权几何中位数比未达到 1.03；至少一个 case 回归超过 3% |
| Maximum R10 | accepted | accepted | inconclusive | 1.0372× | 2.46% | candidate/case 1 原始中位数跨窗口漂移超过 5%；已观察窗口／剔除敏感性跨越工程门槛，不能把小收益当稳定优化 |
| Maximum R11 | rejected | rejected | inconclusive | 0.9993× | 17.79% | baseline/case 8 原始中位数跨窗口漂移超过 5%；candidate/case 11 原始中位数跨窗口漂移超过 5%；baseline/case 14 原始中位数跨窗口漂移超过 5% |
| Maximum R12 | inconclusive | accepted | inconclusive | 1.0529× | 1.46% | candidate/case 7 原始中位数跨窗口漂移超过 5%；candidate/case 8 原始中位数跨窗口漂移超过 5%；已观察窗口／剔除敏感性跨越工程门槛，不能把小收益当稳定优化 |
| Maximum R13 | rejected | rejected | rejected | 1.0217× | 2.09% | 等权几何中位数比未达到 1.03 |
| Maximum R14 | rejected | rejected | inconclusive | 0.9910× | 24.92% | baseline/case 11 原始中位数跨窗口漂移超过 5% |
| Maximum R15 | inconclusive | rejected | inconclusive | 1.0046× | 5.44% | baseline/case 11 原始中位数跨窗口漂移超过 5% |

原结论与“全部窗口反事实”不一致的候选共7个：

- grid_sampler_3d R1：inconclusive → rejected。至少一个 case 回归超过 3%。
- grid_sampler_3d R4：inconclusive → accepted。轮内规则、窗口复核与原收益门槛均满足（仅离线假设）。
- grid_sampler_3d R5：inconclusive → rejected。至少一个 case 回归超过 3%。
- maximum R3：rejected → inconclusive。已观察窗口／剔除敏感性跨越工程门槛，不能把小收益当稳定优化。
- maximum R10：accepted → inconclusive。candidate/case 1 原始中位数跨窗口漂移超过 5%；已观察窗口／剔除敏感性跨越工程门槛，不能把小收益当稳定优化。
- maximum R11：rejected → inconclusive。baseline/case 8 原始中位数跨窗口漂移超过 5%；candidate/case 11 原始中位数跨窗口漂移超过 5%；baseline/case 14 原始中位数跨窗口漂移超过 5%。
- maximum R14：rejected → inconclusive。baseline/case 11 原始中位数跨窗口漂移超过 5%。

仅放宽轮内标准会增加可分析窗口，但新的跨窗口规则也会把原Maximum R10的accepted放回需复核；不能只挑新规则变好的候选。Grid R2/R6的末窗点估计可达到工程门槛，但全窗口复核仍有超限或敏感性问题，不算已解决。以上变化仍不表示新协议得到独立验证。

## 具体控制例与回退

| 例子 | 首测→最终原始中位数 | 原始CV / 处理后CV | 异常数 | 新轮内判断 |
|---|---|---|---:|---|
| Grid R6 B case14 | 24.592→25.042 μs，漂移1.83% | 46.18% / 3.68% | 3 | within_window_acceptable |
| Grid R15 B case18 | 17.366→17.470 μs，漂移0.60% | 7.13% / 7.13% | 0 | within_window_acceptable |
| Grid R10 B case14 | 28.488→35.150 μs，漂移23.39% | 31.26% / 6.71% | 2 | within_window_acceptable |

R6 B case14展示高原始CV与稳定中位数可并存；其单case改进不等于整轮通过。R10 B case14漂移23.39%，无论轮内门槛是否通过，都不能仅凭CV放宽采用。

R14/R15的负面性能证据仍明确：

| 目标 | 新末窗 B/A | 回归 | A/B处理后CV | A/B剔除数 |
|---|---:|---:|---|---|
| Grid R14 case11 | 562.5435× | 56154.35% | 1.186% / 0.009% | 0 / 0 |
| Grid R15 case10 | 1.1432× | 14.32% | 0.723% / 0.747% | 0 / 0 |
| Grid R15 case16 | 1.1570× | 15.70% | 0.623% / 0.425% | 0 / 0 |
| Grid R15 case17 | 1.0539× | 5.39% | 0.261% / 0.341% | 0 / 0 |
| Grid R15 case20 | 1.2010× | 20.10% | 0.342% / 0.459% | 0 / 0 |

这五个目标窗口均未剔除异常，放宽阈值不改变这些回退。全轮尚有其他case的漂移，会使整轮保持不确定；这不抹去上表局部负面观察，也不能把整轮不确定包装成优化成功。R15四个新pair域10/16/17/20来自冻结原C2计划，未按回退大小事后选择目标。

## 实现、兼容与验收

- 新增`median_timing.py`，复用原始Task完整调用与oracle回放；5/20采集及native协议不变，测前v3声明、v2请求/结果显式分派。原`task_statistics.py`与旧schema保持原字节。
- 结果保留轮内质量、全部原始/处理后统计、双方漂移、固定最后窗口点估计、剔除与观测范围敏感性。超限标需复核，不转换成性能失败；中位数稳定也不自动accepted。
- 复验身份、时间顺序、独立native窗口、复验额度和全部case继续校验。新统计只接入当前v3/v4交接的结果读取，旧handoff/v2拒绝新结果；不放宽P/O准入。
- 同步profiling、协调者、准备/采集contract和统一计时参考；不新增优化阶段、日常必跑脚本或自动复验循环。

最终CPU、旧协议兼容、独立目录和受保护文件检查记录见[检查结果](CHECKS.json)。没有硬件采样、oracle重跑、HAP重新评分、训练或memory收集。

## 离线复算

从完整技能包根目录运行，output必须不存在：

```bash
python3 tools/compare_timing_stability.py \
  --frozen workflows/references/median-timing-1.3.0/sources/raw-evidence.json.gz \
  --output /dev/shm/aprof-median-offline-replay
```

该脚本属于开发/离线分析入口，常规优化不必执行。窗口范围是敏感性展示，不是统计置信区间；现有数据也参与了阈值选择，不能作为新规则独立泛化证据。后续若需独立验证，应由用户另行授权新数据和固定复验预算，本轮不追加。
