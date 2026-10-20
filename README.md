# AProf

AProf 将稳定可用的 skill 库与研发、测量、trace 采集工程分开维护。

| 入口 | 用途 |
| --- | --- |
| [skill-libs](skill-libs/catalog.json) | 已冻结版本目录；每版都是完整源码及可独立使用的包 |
| [graph-base 0.5.1](skill-libs/graph-base/0.5.1/README.md) | 当前稳定默认版；已验证的 Task Duration 测量、本地优化证据与任务后独立归档 |
| [graph-base 0.5.0](skill-libs/graph-base/0.5.0/README.md) | 保留的历史稳定版及 1.0.0 等预算比较基线；原始字节不变 |
| [graph-base 1.0.0 candidate](skill-libs/graph-base/1.0.0/README.md) | 未封存的 Teacher/Wiki 候选；保留原图和机器 gate，等待独立硬件验收 |
| [graph-base 1.1.0 draft](skill-libs/graph-base/1.1.0/README.md) | 中文开发版：coordinator 串联五个角色、v0003 诊断图和两棵知识树；反馈与收尾统一 L2 清理 5/20，硬件验证待完成 |
| [graph-base 1.2.0 draft](skill-libs/graph-base/1.2.0/README.md) | 新任务开发版：runtime 0.3.0、软时间目标、本地工作区与校验复用；未封版，见 [维护说明](MAINTENANCE-1.2.0.md) |
| [graph-base 1.3.0 draft](skill-libs/graph-base/1.3.0/README.md) | 中文知识扩充、v0004机制诊断与两阶段P/O路由；runtime 0.5.0，未封版，见 [维护说明](MAINTENANCE-1.3.0.md)；不切换默认版本 |
| [graph-base 0.4.2](skill-libs/graph-base/0.4.2/README.md) | 保留的历史稳定版；Vector / 910C(A3)、按架构选择 profiler、CAS 证据回放 |
| [graph-base 0.4.1](skill-libs/graph-base/0.4.1/README.md) | 保留的历史稳定版，源于 0.4.0 / d8f6837 |
| [新采集与学习脚手架](scaffolding/README.md) | 批量调用 APROF、独立 memory 整理、离线更新三个知识区 |
| [历史采集流程](scaffolding/collection/workflows/README.md) | 保留旧版本实验、归档、恢复和协议回放 |
| [精简证据](scaffolding/evidence/README.md) | lesson、trace、源码与反馈；大型证据保留外部索引 |
| [历史 Teacher 筛选审计](scaffolding/curation/README.md) | 66 条历史记录的当前 split、纳入理由、Wiki 引用和哈希校验 |
| [CANNBench](scaffolding/benchmarks/cannbench) | 算子直调工程、harness 及冻结 split |
| [迁移说明](scaffolding/docs/repository-layout.md) | 依赖边界、版本发布、历史 producer 与验证限制 |

## 使用稳定版本

```bash
cd skill-libs/graph-base/0.5.1
python3 tools/install.py --runtime
python3 tools/release.py
./tools/aprofctl graph validate --graph skillgraph/versions/v0002
```

该目录可独立复制。宿主加载其中的 `skills/`，主入口是
`ascendc-aprof-workflow`；完整安装及调用说明见版本 README。
Python runtime 为 0.2.2，skill/plugin 为 0.5.1，默认图为 v0002。

仓库级插件入口在 `.agents/plugins/marketplace.json` 与
`.claude-plugin/marketplace.json`，均指向明确的默认版本。安装后的插件
应保留整个版本目录，并在宿主实际安装目录安装 runtime。

0.5.1 默认围绕一个假设、一个候选执行；正式 gate 门槛不变。
910C/A3 的已验证测量以完整调用的 Task Duration 为主指标，保留 Event/Host 辅助量。
优化 agent 在任务临时目录完成采集、解析和在线验收，交付源码与简明报告。
需要训练 trace 时，由收集 agent 在任务结束后归档，单独记录归档成本。
受支持的 950 环境优先使用 npu-compute；910C/A3 使用 msprof。
本机验证与边界见 [0.5.1 验收记录](scaffolding/docs/releases/graph-base-0.5.1.md)，
历史 profiling 验证见 [0.4.2 验收记录](scaffolding/docs/releases/graph-base-0.4.2.md)。

## 使用新采集与学习脚手架

新任务使用 1.2.0，从 [aprof-optimize-batch](scaffolding/skills/aprof-optimize-batch/SKILL.md)
进入：显式冻结技能包和三个知识区，逐算子调用 coordinator，由独立 agent
整理包含全部尝试的 memory v3。采集结束后使用
[aprof-train-knowledge](scaffolding/skills/aprof-train-knowledge/SKILL.md)
提出 graph/knowledge 内容和排序参数候选，经过独立任务验证再考虑晋升。
记录格式、CPU 校验和历史文件归属见 [scaffolding](scaffolding/README.md)。

## 回放历史采集

从仓库根目录显式选定版本；所有子进程继承同一选择。下面的历史采集协议
继续绑定 0.4.1；0.4.2 及后续版本的新正式准入需要 1.1 profile 来源证据，不能将旧
exploration producer 的记录直接改绑到新 runtime：

```bash
export APROF_SKILL_LIB="$PWD/skill-libs/graph-base/0.4.1"
python3 scaffolding/collection/scripts/prepare_trace_pilot.py \
  --skill-lib "$APROF_SKILL_LIB" \
  --config scaffolding/collection/configs/trace-pilot.example.json \
  --output-root /tmp/aprof-pilot
```

pilot 只准备和冻结输入，不编译、不执行硬件。新 Level2 campaign 的
`prepare --skill-lib` 同样冻结 release 身份；后续步骤读取已绑定的版本。
Level2 搜索仍为 2 进程 × 6 对、直接父本比较，保留全量正确性和最终完整测量。

## 验证与开发

```bash
export APROF_SKILL_LIB="$PWD/skill-libs/graph-base/0.5.1"
python3 scaffolding/tools/sync_aprof_registry.py check --skill-lib "$APROF_SKILL_LIB"
python3 scaffolding/tools/compile_graph_v2.py --skill-lib "$APROF_SKILL_LIB" --check
python3 scaffolding/tools/compact_evidence.py verify --root scaffolding/evidence
python3 -m pytest scaffolding/tests -q
```

历史兼容回归显式将 `APROF_SKILL_LIB` 设为 `graph-base/0.4.1` 的完整路径；
版本专用测试按绑定版本运行；0.5.1 增加 Task 测量资格与本地证据验收。
各版本验收结果见对应发布记录。

稳定版不得原地修改。下一版在开发分支复制一个版本目录，移除其旧
`release.json`，更新版本号并修改源码，经验证后使用
`scaffolding/tools/release_skill_lib.py seal` 封存，最后更新 catalog 和宿主入口。
不另设 skill 作者源或生成副本目录。

原暂停 Level2 实验仍为 26/48，且不是完整离线证据包。这里的重构及证据导入
不会恢复实验、重写旧记录、制造正式准入或改变训练资格。
