# 本轮变更与边界

本轮在既有未封版 1.3.0 上增加正式的源码理解环节，不重写既有诊断机制、Action 选择或 P/O 叶条目。对比依据是本轮开始时的实际文件身份；此前工作区尚未提交的变更予以保留。

## 新增知识

| 资料 | 主要内容 | 用途 |
|---|---|---|
| [技能入口](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-code-understanding/SKILL.md) | 整体算法、实现策略与硬件执行的阅读主线；适用范围与按需展开 | 诊断前明确该先理解什么 |
| [工程理解方法](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-code-understanding/references/engineering-reading.md) | host→tiling→kernel，实际分派、任务/循环、地址、owner、数值语义与源码定位 | 从完整工程还原当前实现 |
| [910C 硬件与数据流](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-code-understanding/references/910c-hardware.md) | API 重载/位置与执行单元；TPosition 与物理存储；pitch/stride/padding/格式；队列、事件与覆盖依赖 | 将代码行为对应到适用的硬件行为 |
| [Add 贯通例子](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-code-understanding/references/example-add.md) | 算法、host 启动、tiling、循环和 Vector 通路；代码能确认与不能确认的范围 | 学习如何解释完整工程，避免把 BUFFER_NUM 当作实际分配或有效重叠 |
| [基本 Cube 贯通例子](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-code-understanding/references/example-cube.md) | 任务切分、矩阵格式、GM/L1/L0、Cube/MMAD 与 FIX 输出 | 解释格式和通路，不把 API 名称直接等同于一条硬件路径 |
| [来源索引](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-code-understanding/references/source-index.md) | 固定修订、声明依据、原文片段、hash 和许可 | 追溯与独立阅读 |

材料按“源码片段→执行过程→硬件对应→分析意义→结论边界”组织。方法来自固定 cannbot-skills；硬件和 API 语义由固定 asc-devkit 的适用内容核对。只登记实际采用的来源，不把其余三个仓库列为本轮结论依据。

## 流程与维护

- C0 后、C1 前，由协调者组织完成或复用 code-understanding。保留 C0—C5 编号，同一 Agent 可以完成多个角色。
- 新增[角色](../../../../skill-libs/graph-base/1.3.1/workflows/agents/code-understanding.md)和[Markdown contract](../../../../skill-libs/graph-base/1.3.1/workflows/contracts/code-understanding.md)，同步主 workflow、协调者、诊断、P/O、技能注册和插件入口。
- 日常只新增一份中文理解报告。诊断引用它和原始源码，必要时可质疑或回查，不再重复编写一套完整工程分析。
- P/O 深入布局、通路或生命周期时复用同一 skill；R2 只更新源码或相关条件变化影响的部分并保存后继。纯新增性能观测不要求全量重读。
- 包维护工具只增加角色/文件注册及安装完整性检查；开发评测的脚本不进入日常阶段。

## 保持原义的内容

runtime 0.7.0、D v0006、P v0003、O v0006、routing v0005、全部既有 JSON schema、历史快照、knowledge.py 与 1.2.0 内容均以实施前 hash 核对。默认版本不切换，1.3.0 保持未封版。无硬件实验、训练或性能收益声明。

## 仍需覆盖的内容

1. **平台与 SDK 范围**：首版仅讲 910C 项目中有依据的 A3/2201 适用行为；950 不在教学范围内。2201 宏不能单独识别具体 SKU，工程构建目标和 SDK 仍需结合项目证据。
2. **API 广度**：重点覆盖典型 Vector/Cube、搬运/格式和队列/事件理解，不是所有 Ascend C 重载、库内部实现和融合算子的完整手册。项目实际调用未被覆盖时，需按同样方法核对对应实现。
3. **动态行为**：源码中的允许并行、依赖与资源占用不能证明真实发射时序、有效重叠、缓存命中或吞吐。此类结论需要后续实际观测。
4. **复杂工程**：教学例与六组开发题目不能代表全部间接分派、动态 shape、多算子 workspace、原子/多核合并或构建组合。
5. **评测外推**：本次只评代码理解，不据此认定 SPA 选型、P/O 实现或硬件收益已经改善。评分差异与阅读成本、具体错误见评测报告。
