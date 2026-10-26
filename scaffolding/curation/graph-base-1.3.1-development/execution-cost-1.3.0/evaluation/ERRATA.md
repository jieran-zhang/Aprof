# 独立复核后的注释勘误与标准解释

独立复核覆盖24项，维持全部`[2,2,2,2]`及A/B各96/96。原grades、GRADES-LOCK、FACTS及FACTS-LOCK不改；本文件与[结构化勘误](ERRATA.json)作为补充解释，与原评分一同阅读。见[独立复核](behavior-review.md)及[复核JSON](behavior-review.json)。本轮未重发模型请求、未改包。

## 两处评分注释更正

- **s5-maximum-plan-cache-A-1-v2，criteria_review[2]**：实际主选是同owner两4096 tile搬运合批至多8192元素，数据区98304B（96KiB）。Max仍K次、必要payload仍12MiB；搬运3K→3K′，队列管理约12K→12K′。81920B（80KiB）的2+2+1输入前瞻是替代方案。原注释复用了A2描述，错误地颠倒主选并称调用不变；分数不变。
- **s6-history-parent-rename-A-2-v2，intent_coverage.kind**：主选是`action.batch_writeback`，应解释为“existing writeback intent selected”。原“existing control intent selected”分类错误；派生复用的未注册缺口仍单列，分数不变。

## FACTS的解释澄清

- **s4，标准2**：64B是偏移+合成权重的布局假设，不是唯一答案或原Scalar默认合法表示。原`((X*wx)*wy)*wz`不能无证明改成`X*(wx*wy*wz)`。48/56/72B或单点状态均按真实表示、对齐、生命周期与消费成本评估。
- **s1，标准3**：不强制缩窄检测；缩窄若改变外部要求的软件fused数值路径应拒绝。有数值依据的拒绝与完整合法替代比较满足该项成本推理。
- **s5，标准3**：新静态buffer/event方法覆盖与来源事实分分开。A的合法合批/前瞻/cache资源与生命周期推理可以得分；缺方法记版本覆盖差异，不伪称已讨论，也不因B报新Action名加分。

原GROUP-SUMMARY已准确列出A控制外提/批量写回与B静态管理备选，保持原文件，无需生成更改后继。事实分持平和新意图/方法覆盖观察均不变；不由满分推断最快实现、真实硬件收益或B推理全面优于A。

## 行为覆盖与实际存储范围

本次P材料仅预展开elementwise/indexing/layout，未覆盖新增`under-fusion.vector_producer_consumer`叶的自主选用；该叶的来源/技术/构建验证另见总报告，本次没有自主选用证据。不追加请求、不变更评分。

239项基础导出清单保留，复核变更另列增量；包内gzip后的实际路径、存储及解压hash见[实际存储清单](DELIVERY.json)，该文件由主集成创建，不由本轮WORK复制。
