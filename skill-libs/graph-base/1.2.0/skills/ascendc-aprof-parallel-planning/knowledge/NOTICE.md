# 来源与修改说明

本区由 APROF 既有技能和 cannbot-skills 固定修订 `c60a48af8f0ff2374e1491a313d9f26b02620d1e` 蒸馏。上游原文与完整 [CANN Open Software License Agreement Version 2.0](sources/cannbot-skills/LICENSE) 位于 sources/cannbot-skills，仅供 hash 与归属核验，不作为第二套运行 router。

修改：按角色和算子族/执行分支重组；补充所有权、容量与成本公式、fallback、验证与失败条件；所有容量统一为字节；修正上游部分示例的 bits/bytes 混用；硬件常量改为有平台条件的参数；FA 的驻留/streaming 依据容量选择。每个条目 YAML 保存原文件、修订、行号和 hash。新增中文说明由 APROF 维护，派生部分保留原许可，不重新声称 MIT 等许可。

原 APROF 辅助技能 NOTICE/LICENSE 和来源原文保存在 workflows/migration/archive 的对应路径。历史案例不删除失败记录，不将其性能结论转成新协议承诺。运行与安装不依赖外部 cannbot 仓库。
