# AProf 1.1.0 条件经验库

从 index.json 选择与当前问题有关的一页，再回到 SkillGraph 的合法路由。Wiki 不能自行建立机器判决、跳过正确性或补造未知谓词。

继承的已验证经验仅为原 910C/A3、CANN 9.0.0 上的 exp-tile8192。原 20 case 正确性、42 项边界、配对 Task 计时及五次候选 PMU/原 oracle 属于该历史记录。后来 gate-only 回放返回 production_safe_gain，退出码为 0，未新增构建、计时或 PMU。此前 oracle 解析失败和机制绑定失败仍保持失败，不能被后续成功覆盖。

只有该规则和对应技能修订具备原范围验证。tile-amortization、sigmoid-pipeline 等仍为草稿，不能扩大到未验证算子。原 45 次对照和封版后全量测试未运行。

1.1.0 当前采用统一计时，旧配对知识只在其原协议下解释。历史回执不验证新 runtime，也不授予新优化结果。来源 ID/hash 保存在开发仓库 scaffolding/curation/graph-base-1.0.0.json；安装包不复制原始 traces。evolution.jsonl 保留接受、延后和拒绝的提案。

只有可回放、来源绑定的独立验证能改变知识发布状态。验证/测试 traces 和注入标签不能作为在线诊断知识。
