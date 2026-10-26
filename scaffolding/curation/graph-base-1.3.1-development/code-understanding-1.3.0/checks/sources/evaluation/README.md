# 代码理解开发评测固定材料

本目录保存六题公开源码/workload、相同SDK资料、预先冻结的事实答案及CPU算术检查。它只用于技能开发验收，不是日常优化阶段的必读材料或必跑脚本。

- [suite.json](suite.json)：题目、公共输入身份与分组。
- public/case-01…06：源码、变体与workload；public/shared为共同API资料。
- [评分协议](private/GRADING_PROTOCOL.md)、private/gold：独立评分规则和59个事实。
- [冻结身份](private/FREEZE.json)：91个固定输入的hash；本说明不是实验输入。
- [CPU结果](private/results/cpu_checks.json)：tiling、地址、格式及事件的六项检查。

CPU模型和普通C++ tiling探针不代表SDK构建、NPU仿真或真实硬件运行。完整模型调用与读取轨迹在开发档案中保存；本目录足以阅读题目、源码、标准及检查结果，不需上游仓库。
