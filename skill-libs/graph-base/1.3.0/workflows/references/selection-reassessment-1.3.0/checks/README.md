# 检查结果（2026-10-21）

本轮维护已完成，仍为未封版1.3.0。没有新的硬件实验或算子实现；没有性能/HAP结论。

| 检查 | 结果与范围 |
|---|---|
| CPU contract/路由/兼容测试 | 共435项，分批覆盖434通过、1跳过；修复后重跑受影响用例。跳过项为独立包没有携带开发仓库scaffolding的专用兼容入口 |
| 自主分析 | 3个执行Agent分别从原始源码与20-case矩阵开展15算子×2轮静态分析，未预设Problem/Action；独立Agent复核并纠正记录 |
| 新记录离线回放 | 15任务、30轮全部通过，核对真实检索、Problem展开、decision、C1和内部P/O咨询；未生成伪造的confirmed C2/implemented C3 |
| 独立语义检查 | 280行派生量、关键数值边界与210个入口引用核查；4项行为审查发现均已修复，详见独立报告 |
| 旧记录兼容 | 历史15任务、30轮按冻结D5/routing回放通过 |
| 冻结保护 | 659个受保护文件hash全部未变，包括1.2.0、旧schema、旧冻结快照及knowledge.py |
| 独立目录 | 审计hook禁止网络、原工作树、上游仓库和输入暂存目录访问；结构检查及30轮回放通过 |
| 重建 | D6/P3/O6编译结果与冻结产物完全一致，routing v5通过 |

CPU测试先发现旧fixture的当前版本期待错误和测试期间目录变动，已修正fixture并在固定复制目录重跑；不是忽略失败。decision补丁分别增加预测证据身份、候选身份及完整workload绑定反例。435是去重后的收集数，不把重复回归累计为额外覆盖。`pytest-runtime-frozen.log`记录后半和受影响模块216通过1跳过；先前166通过中8项在后半重跑，合计非decision模块374通过1跳过。decision最终60项通过（含后增参数化项），总计434通过1跳过。

计时相关正反例使用CPU FakeRunner合成契约证据，不是硬件测量。本批自主R2均为not_measured：可以修正工作量、覆盖、API和资源条件；不能将其写作第二轮实测收益。

详细入口：[15算子表](../../selection-regression-15/README.md)、[逐轮回放](autonomous-replay.json)、[机器汇总](results.json)、[语义复核](../review-autonomy/REPORT.md)、[完整workload绑定](../review-decision/workload-binding.md)、[构建身份](offline-build.json)。
