# 1.3.0代码理解：无工具对照

针对AProf实际输入方式，模型只接收源码、workload、平台声明；B再加入固定skill全文。A为351/360，B为354.5/360，12对中3提高、9持平、0退步。这里是完整性与准确性的加权事实得分，不是普遍准确率。

6组各做2次独立A/B，共24份回答；同gpt-6.1-sol/high/default、同12000输出token上限。显式`tools=[]`、`tool_choice=none`，服务器回显及响应类型检查通过，实际工具调用0，没有截断。没有Agent循环、共享SDK手册或其他skill。3500字符是软目标，两组都超出，详见成本报告。

| 组别 | 输入 | 平均得分/30 | 平均输入token |
|---|---|---:|---:|
| A | 源码＋workload＋平台声明 | 29.25 | 11948.7 |
| B | 相同输入＋SKILL及固定全部5篇参考正文 | 29.54 | 27283.8 |

可见增益来自尾部搬运的UB物理对齐、以及一个重复中的Cube输出格式链补全。大多数执行事实两组已掌握，输入量约增至2.28倍，尚不足以证明全量内联对所有工程都划算。B剩余扣分全部涉及3510/950静态对照细节；主指标完整保留，不按910C范围事后删题。

- [逐题、三维及24次逐调用结果](EVALUATION.md)：每份可阅读答案与评分原文。
- [具体差异、成本和后续方向](FINDINGS.md)：哪些知识被体现在回答中、哪些能力未测得改善。
- [冻结协议](PROTOCOL.md)、[逐事实评分](GRADING_PROTOCOL.md)、[预定抽审](REVIEW_PLAN.md)：评分与独立复核在解盲前锁定。
- [输入独立复核](design-review/REPORT.md)、[匿名评分复核](scoring-review/REPORT.md)、[裁决](scoring-review/ADJUDICATION.md)。
- [检查与保护范围](CHECKS.md)、[汇总JSON](RESULTS.json)、[实际固定输入](sources/inputs/case-01.txt)及[skill统一后缀](sources/inputs/skill-suffix.txt)。

被测模型不调用工具；开发者用于定答案、核对哈希、评分和离线包检查的工具不进入日常workflow。runtime0.7.0、D6/P3/O6、routing5、JSON schema和skill正文保持原样，仍是未封版1.3.0，不切换默认版本，不开展硬件实验。

本轮测完整展开的skill包，不能代表只给短入口且无法打开参考的形态，也不能单独归因于方法或知识。六组相关实例不是盲留出泛化测试。[旧工具/SDK开放轮](../EVALUATION.md)单独保留，不能用跨轮分差估计工具收益。完整开发轨迹与重放脚本保存在仓库scaffolding/curation/graph-base-1.3.0-code-understanding-no-tools；阅读本包不依赖该目录。
