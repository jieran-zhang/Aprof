# 精简优化证据

[index.json](index.json) 是本仓库证据入口。它记录每个收录文件的本地位置、
SHA-256 和大小；原始记录中的绝对路径只作 provenance，不用作读取回退。

- Level1：37 条 memory、26 条 lesson，保留原 JSONL 字节和不同 revision。
- Level2：26/48 次已闭合尝试，保持暂停；收录事件、反馈、报告、checkpoint、
  baseline/candidate 源码包及计划。尚无正式发布的 Level2 memory/lesson/episode。
- `deliveries/`：已经测量过的算子实现和旁证，不是 skill 发布版本。

约 18 MB 精简材料进入 Git。完整 evidence closure、snapshot、payload、完整文件
索引及约 435 GiB 原外置 raw 保持外部。部分历史 loose raw 已归档清理；查看
`traces/maintenance/` 回执并使用原有 archive reader，不能假定旧路径仍存在。
本目录明确不是完整离线证据包。

从仓库根目录验证或按索引 key 读取：

```bash
python3 scaffolding/tools/compact_evidence.py verify --root scaffolding/evidence
python3 scaffolding/tools/compact_evidence.py read --root scaffolding/evidence --key <index-key>
```

读取只使用已收录文件，校验 hash；未收录对象明确报缺。外部目录消失不会妨碍
读取本地 lesson、源码和反馈，也不会被解释为原始证据已经完整。

原 lesson 的条件、反例和不确定性继续保留。精选知识经独立验证后写入下一版
skill references；当前稳定 skill 不自动加载本证据库。
