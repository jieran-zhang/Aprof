# 0.4.1 结构迁移记录

源基线为 `skill-graph-base` 的 `d8f6837a565e4eb718605a289fa929ebc0c1496f`，
skill lib 版本为 0.4.0。本次在独立 worktree / 分支实施；原 checkout、原绝对
路径和暂停实验不变。

[验收结果与复现命令](verification.md)：完整 CPU 回归 2711 passed / 11 skipped，
最终稳定包的独立检查通过。

- [baseline.json](baseline.json)：迁移前冻结文件 hash。
- [paths.json](paths.json)：旧 Git 路径到新路径的定位表；已合并的重复 skill
  可能指向同一份 canonical 文件，不代表历史签名内容被改写。
- [integrity-verification.json](integrity-verification.json)：runtime、schema、图、
  benchmark 和交付文件的字节一致检查及精简证据计数。
- [graph-reproducibility.json](graph-reproducibility.json)：v0001 已存在的重编译
  差异与迁移前后结果；v0002 可从冻结父图重现。
- [producer-epoch.json](producer-epoch.json)、[guard-epoch.json](guard-epoch.json)：
  迁移后 producer 身份。旧签名记录和源码包仍使用原 hash；恢复执行需显式
  continuation/handoff，不能把新目录当成旧 producer。

root 仅保留 `skill-libs/`、`scaffolding/` 两个业务目录及 README/Git/宿主安装
元数据。没有旧路径软链接、兼容副本或另外生成的整套 skill。

采集专用规则、case/采样策略及原始 lesson 留在 scaffolding。稳定包内
`skillgraph/provenance/` 是重现历史图出处的冻结资料，不是第二份 skill 源码
入口。下一版复制完整版本目录后开发，验证后重新封存。

本次不搬迁大型 raw，不恢复 Level2，不改 gate、训练算法或测量协议，不处理
远程 push 认证。精简证据仍为 Level2 26/48、暂停、离线证据不完整。
