# 来源、版权与改写说明

本目录用于 Ascend 910C / Atlas A3 工程的代码理解。第三方材料仅取自 `sources/manifest.json` 所列的固定仓库版本；本版实际复制 cannbot-skills 与 asc-devkit 的必要文档片段和两个教学工程的源文件。其他三个允许仓库列为未使用，不声称它们提供了证据。

所复制材料来自 Huawei CANN 项目。源文件已有的 Copyright、许可及免责告示保留在原文快照中；源文件没有单独文件头时，保留仓库根许可并在 manifest 中标明对应关系。两份仓库根 LICENSE 按各自精确 git blob 原样保存：

- [cannbot-skills LICENSE](sources/licenses/cannbot-skills.LICENSE.txt)
- [asc-devkit LICENSE](sources/licenses/asc-devkit.LICENSE.txt)

两者标题均为 **CANN Open Software License Agreement Version 2.0**。复制材料及其改写受对应原许可约束；本包未把它们重新标记为 MIT、Apache 或其他许可证。完整条款以随包原文为准。

`SKILL.md` 与 `references/` 是为本阶段新编写的中文组织和解释。方法部分改写 cannbot 的工程阅读思路，未照搬其固定八步流程、必跑工具或其他技能依赖；硬件部分按 devkit 的 A3/2201 适用内容收敛；例子的公式、区间覆盖、字节数和依赖解读均明确标作推导，并保留原始 host/kernel/构建上下文供复核。正文中的缩写伪代码用于讲解，不冒充原始完整源文件。

原文快照为未经正文改写的原始行段；每段来源、原始行号、原文件 git blob、原文件 SHA-256 和快照 SHA-256 记录在 [sources/manifest.json](sources/manifest.json)。正文与原文之间的对应关系见 [来源索引](references/source-index.md)。包内文件的内容校验清单为 [manifest.json](manifest.json)，它不是阶段输出协议。

本包不包含运行产物、硬件测试结果或性能结论；提供的是可独立阅读的知识和教学材料。
