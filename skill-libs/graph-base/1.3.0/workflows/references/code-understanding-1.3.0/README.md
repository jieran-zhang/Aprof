# 1.3.0：910C 代码理解阶段维护记录

本次新增 `C0 preparation → code-understanding → C1 diagnosis` 正式前置阶段。runtime0.7.0、D6/P3/O6、routing5和原JSON交接保持原义；开发包未封版，默认版本不切换。

[独立skill](../../../skills/ascendc-code-understanding/SKILL.md)解释整体算法、当前实现策略与910C硬件执行。日常产物是一份中文阶段Markdown，P/O/R2可以复用或局部更新。[阶段contract](../../contracts/code-understanding.md)不要求execution-model JSON、CPU脚本、硬件运行或新的runtime通过回执。

## 知识与来源

新skill包含短入口、工程阅读方法、910C硬件映射、完整Add和基础Cube两份教学分析、来源索引。根据实际重载、源目标位置和平台解释DataCopy、Vector、Cube/MTE/FIX通路；区分逻辑标签与物理内存、逻辑shape与传输格式、预留与存活、就绪与允许覆盖。

固定许可范围内实际使用cannbot-skills和asc-devkit，未将另外三个仓库登记为已支持结论。包内保留30个原始源文件的34段精确原文及两份完整许可；[完整性结果](checks/source-checks.json)均通过。阅读不依赖上游仓库或下载目录。

[独立技术复核](technical-review/REPORT.md)检查硬件/API映射、布局、同步与教学公式，未发现待修复问题。没有SDK构建或硬件运行，静态结构不能证明已发生有效重叠或性能收益。

## 开发评测

最新按AProf使用方式补做[无工具对照](no-tools/README.md)：只给源码、workload及平台声明，B再内联新skill及固定全部参考正文；24次均为单次无工具请求。A351/360、B354.5/360，12对中3提高、9持平；主要补全910C尾搬运物理对齐和部分格式链。平均输入约1.19万→2.73万token，强基线仍接近满分，不能据此宣称普遍能力提升。新旧条件分别保存，跨轮分差不能当作工具收益。

以下保留首轮工具/SDK开放条件的记录：

预先冻结六组题目、59项事实与评分办法，另作[独立金标准复核](evaluation-review/REPORT.md)。共同基线为现有1.3.0平台/API技能与相同固定SDK资料；B额外加载新skill。相同配置gpt-6.1-sol/high、新上下文与独立文件视图，6题×A/B×2次，共24次。题目不提供Problem/Action，教学例与测试代码分开。

工具与CPU模型只用于本次开发验收，检查整数tiling、地址、布局及事件偏序，不加入日常workflow。盲评只按预先固定事实评价算法/策略、执行事实、硬件对应，分别记录正确、部分正确、错误、遗漏和无依据断言。

首轮24次有效调用与独立匿名评分已完成。A、B均357/360，12对全部持平；新skill在B的12次调用均被实际读取。该工具/SDK开放轮未测得准确性提升，强基线接近满分，读取/答复软目标也存在超限，因此不作严格等token或普遍能力结论。

见[逐题与逐调用结果](EVALUATION.md)、[实际读取、成本与缺口](FINDINGS.md)、[分类与流程变更](CHANGES.md)、[检查结果](CHECKS.md)。公开源码、workload、冻结事实答案与CPU工具保存在本目录checks/sources/evaluation，仅用于开发验收。完整CLI轨迹、匿名评分及可重现脚本另外版本化保存于仓库scaffolding/curation/graph-base-1.3.0-code-understanding；技能运行和阅读本报告均不依赖该目录。

本页不是性能验收结论。
