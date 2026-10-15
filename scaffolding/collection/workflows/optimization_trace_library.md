# 统一优化 trace 数据目录

技能库代码与实验数据分开保存。当前机器的数据入口是：

```text
/mnt/tidalfs-hwwh01/dataset/dots_infra/workspace/jieran/APROF/optimization-traces/
  index.json
  README.md
  metadata-seal.json
  level1/
    memory-catalog.json
    lesson-catalog.json
    evidence-index.json
    evidence.tar
    <campaign>/<dataset>/
      current/{train,validation}/{optimization_traces,lessons}.jsonl
      current/{manifest,evidence_index,contexts,...}.json
      evidence-map.json
      revision-history.tar
      revision-history-index.json
  level2/level2-skill-graph-base-20261005-experiment/
    status.json
    source_attempts.jsonl
    readable/                 # 事件、反馈、报告及暂停 checkpoint
    snapshot.tar              # 源码、patch、计划、日志及其他小文件
    file-index.json
    external-raw-inventory.json # 超出预算的大型raw，明确原始保留位置
    payloads/                 # 大型原始输出和已有归档的物理硬链接
  tools/organize_optimization_traces.py
  method-validation/search-lite-method-20261008/
    readable/{method-validation-summary,ready}.json
    evidence.tar
    file-index.json
```

`index.json` 标识最新 Level1 系列，并列出所有已发布历史系列。各系列的
train/validation 保留原 split 和原始 JSONL 字节。全局 catalog 只按
`(record_kind, id, record_hash)` 合并完全相同的记录；同一 stable ID 的不同
revision 都保留，不用“最后一个文件覆盖前一个文件”的方式合并经验。

Level2 暂停时只有 **26/48 次源码尝试关闭了反馈**。其
`source_attempts.jsonl` 是由真实注册事件、关闭事件和反馈生成的检索索引，
不是 `optimization_memory` v2 发布结果。构建失败、未完成最终评估、HOLD
等状态保留在原始记录中。没有补写缺失轮次、成功轨迹、memory ID、lesson
或可训练 episode；研究测量不等于正式 runtime 准入。

独立的 `method-validation/` 保留本次轻量协议实测，包括前置准备失败和
实际成功的两进程观察。它复用已关闭候选的源码，新增源码尝试数为零，
不改变暂停 Level2 的 26/48 计数。整理命令可用 `--method-validation` 指定
已关闭的方法验证目录，按独立 16 GiB 上限保存全部文件。

## 证据完整性边界

Level1 打包所有当前已发布 revision 的 `evidence_index.json` 引用，并在
写入时逐个核对原 SHA-256。多个索引引用相同内容时只存一份。各数据集的
历史 revision 元数据与 CAS 也保留，但仅存在于旧 revision、已不被 current
引用的外部证据不宣称完整。原 run 中没有进入已发布索引的额外 raw 文件也
不属于这项闭包声明。

Level2 索引列出暂停 run 中的全部普通文件。中心快照完整保留元数据、小型文件、
源码和 patch，并计算实际 SHA-256；大于阈值的非文本输出与已有大型 TAR
在固定 raw 预算内使用物理硬链接。已有 native journal 与 validation 配对
记录提供的输出 SHA 用于去重，一个记录哈希仅保留一个大文件；复用记录
哈希不宣称重新验证了大文件内容。优先保留已有大型归档。保留的硬链接
不依赖旧目录名，删除旧路径不会删除中心目录中的
文件，但两个名字仍共享相同的内容，**不是独立备份，禁止原地改写任一端**。
大型 payload 此次未重算全部内容哈希；中央目录未宣称完成最终语义归档
验证。预算外 raw 的数量、逻辑字节与原始保留路径列入
`external-raw-inventory.json`，`status.json` 与顶层 `index.json` 明确标记
`all_run_regular_files_included=false`。它们不会阻止读取中心的源码、patch、
事件、反馈、报告、checkpoint 和维护封包，但不能宣称完整 Level2 portable
closure。读取器遇到明确外部 raw 会报错，不偷偷回退旧路径。

原始绝对路径只作为 provenance 保留。读取中心内容使用 `evidence-map.json`
或 `file-index.json` 定位中央目录内的文件/TAR 成员，不回退访问旧 checkout。
已有 Level2 storage 封包和维护回执一起保留；不能把一个 TAR 存在误认为其
所有下游选择、runtime gate 或训练准入已通过。

## 创建、验证和读取

工具只进行 CPU/文件操作，不构建候选，不调用 NPU，不修改源 run。目标目录
必须不存在；失败的 `.staging-*` 不算发布完成。全部数据和索引准备完毕并
通过结构验证后才原子重命名为目标目录。

```bash
python scaffolding/collection/scripts/organize_optimization_traces.py organize \
  --output /path/to/optimization-traces \
  --level1-checkout /path/to/aprof-feat-aprofgraph \
  --raw-budget-gib 64 --packed-budget-gib 64 \
  --level2-run /path/to/aprof/.aprof/runs/level2-skill-graph-base-20261005-experiment

# 不需要原仓库；默认验证封印、元数据及所有成员的存在/长度。
python /path/to/optimization-traces/tools/organize_optimization_traces.py verify \
  --output /path/to/optimization-traces

# 另行重算所有 packed 内容哈希；不将未哈希的大 payload 误报为哈希通过。
python /path/to/optimization-traces/tools/organize_optimization_traces.py verify \
  --output /path/to/optimization-traces --deep

# 精确读取一个原始文件；stdout 的字节不作改写。
python /path/to/optimization-traces/tools/organize_optimization_traces.py read \
  --output /path/to/optimization-traces --level level2 \
  --source-relative train/tasks/gather/feedback/gather002.json
```

Level1 的 `read` 使用 `--level level1 --sha256 sha256:<内容哈希>`。分支提交和
远程 push 只携带整理工具、测试及本说明，不把数百 GiB 原始实验数据提交
进技能库 Git 历史。后续继续实验时发布新的快照，旧快照不覆盖。
后续快照统一放在中心目录的 `snapshots/<时间戳>/` 下，并更新中心入口的
最新快照索引；不要另放进新 Git 分支的工作区。新 campaign 也应优先直接
使用中心目录内独立的 `runs/<campaign>/`，原始证据仅归档一次。

若整理在 Level1 完整打包后因存储限制中断，`--resume-staging` 可显式指定
同级的未发布 staging。它核对已打包 Level1 的已发布元数据后复用原包，只
替换该 staging 内未发布的 Level2 副本；不删除原 run，不重复打包 Level1。
