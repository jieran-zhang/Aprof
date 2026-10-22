# 来源与修改说明

本区由 APROF 既有技能和 cannbot-skills 固定修订 `c60a48af8f0ff2374e1491a313d9f26b02620d1e` 蒸馏。上游原文与完整 [CANN Open Software License Agreement Version 2.0](sources/cannbot-skills/LICENSE) 位于 sources/cannbot-skills，仅供 hash 与归属核验，不作为第二套运行 router。

修改：按角色和算子族/执行分支重组；补充所有权、容量与成本公式、fallback、验证与失败条件；所有容量统一为字节；修正上游部分示例的 bits/bytes 混用；硬件常量改为有平台条件的参数；FA 的驻留/streaming 依据容量选择。每个条目 YAML 保存原文件、修订、行号和 hash。新增中文说明由 APROF 维护，派生部分保留原许可，不重新声称 MIT 等许可。

原 APROF 辅助技能 NOTICE/LICENSE 和来源原文保存在 workflows/migration/archive 的对应路径。历史案例不删除失败记录，不将其性能结论转成新协议承诺。运行与安装不依赖外部 cannbot 仓库。

## 1.3.0 增补来源

以下固定修订的相关完整文件和许可按仓库/commit/原路径存入本区 sources。原先 c60a48af 来源仍原样保留，新增修订不覆盖旧档案。

| 仓库 | 固定修订 | 许可 |
| --- | --- | --- |
| cannbot-skills | `41377d0a442cd5b1c2356874873a3dda591c6633` | [包内许可](sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/LICENSE) |
| cann-samples | `17c948bb961fc6a660e4fcab45f6bf217c9c6239` | [包内许可](sources/cann-samples/17c948bb961fc6a660e4fcab45f6bf217c9c6239/LICENSE) |
| asc-devkit | `d378849769f9ee610af9d0ac38db2b3b6bed3209` | [包内许可](sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/LICENSE) |
| ops-nn | `8b42e125134fa9abf1e42a67e6b2792f78c26be5` | [包内许可](sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/LICENSE) |
| ops-transformer | `d7e6a7c6c1450c040049486845336c77f3100406` | [包内许可](sources/ops-transformer/d7e6a7c6c1450c040049486845336c77f3100406/LICENSE) |

新增中文正文由 APROF 归纳与重写，必要片段保持原归属与适用范围；sources 不是另一套 router，使用不依赖上游仓库、工作树或下载目录。来源事实、源码确认和本次工程归纳在正文分别说明。所有新增内容未进行本版 NPU 收益验证，不重标许可或性能资格。
