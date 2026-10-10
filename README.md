# AProf

AProf 将稳定可用的 skill 库与研发、测量、trace 采集工程分开维护。

| 入口 | 用途 |
| --- | --- |
| [skill-libs](skill-libs/catalog.json) | 已冻结版本目录；每版都是完整源码及可独立使用的包 |
| [graph-base 0.4.2](skill-libs/graph-base/0.4.2/README.md) | 当前默认版本；Vector / 910C(A3) 输入约定、按架构选择 profiler、CAS 证据回放 |
| [graph-base 0.4.1](skill-libs/graph-base/0.4.1/README.md) | 保留的历史稳定版，源于 0.4.0 / d8f6837 |
| [采集流程](scaffolding/collection/workflows/README.md) | 显式绑定 skill 版本，组织实验、测量、归档和恢复 |
| [精简证据](scaffolding/evidence/README.md) | lesson、trace、源码与反馈；大型证据保留外部索引 |
| [CANNBench](scaffolding/benchmarks/cannbench) | 算子直调工程、harness 及冻结 split |
| [迁移说明](scaffolding/docs/repository-layout.md) | 依赖边界、版本发布、历史 producer 与验证限制 |

## 使用稳定版本

```bash
cd skill-libs/graph-base/0.4.2
python3 tools/install.py --runtime
python3 tools/release.py
./tools/aprofctl graph validate --graph skillgraph/versions/v0002
```

该目录可独立复制。宿主加载其中的 `skills/`，主入口是
`ascendc-aprof-workflow`；完整安装及调用说明见版本 README。
Python runtime 为 0.2.1，skill/plugin 为 0.4.2，默认图为 v0002。

仓库级插件入口在 `.agents/plugins/marketplace.json` 与
`.claude-plugin/marketplace.json`，均指向明确的默认版本。安装后的插件
应保留整个版本目录，并在宿主实际安装目录安装 runtime。

0.4.2 在受支持的 950 环境优先使用 npu-compute；910C/A3 使用 msprof。
本机验证与边界见 [0.4.2 验收记录](scaffolding/docs/releases/graph-base-0.4.2.md)。

## 使用采集脚手架

从仓库根目录显式选定版本；所有子进程继承同一选择。下面的历史采集协议
继续绑定 0.4.1；0.4.2 的新正式准入需要 1.1 profile 来源证据，不能将旧
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
export APROF_SKILL_LIB="$PWD/skill-libs/graph-base/0.4.2"
python3 scaffolding/tools/sync_aprof_registry.py check --skill-lib "$APROF_SKILL_LIB"
python3 scaffolding/tools/compile_graph_v2.py --skill-lib "$APROF_SKILL_LIB" --check
python3 scaffolding/tools/compact_evidence.py verify --root scaffolding/evidence
python3 -m pytest scaffolding/tests -q
```

历史兼容回归显式将 `APROF_SKILL_LIB` 设为 `graph-base/0.4.1` 的完整路径；
新 profiler 的专用测试仅适用于 0.4.2。两个版本的验收结果见发布记录。

稳定版不得原地修改。下一版在开发分支复制一个版本目录，移除其旧
`release.json`，更新版本号并修改源码，经验证后使用
`scaffolding/tools/release_skill_lib.py seal` 封存，最后更新 catalog 和宿主入口。
不另设 skill 作者源或生成副本目录。

原暂停 Level2 实验仍为 26/48，且不是完整离线证据包。这里的重构及证据导入
不会恢复实验、重写旧记录、制造正式准入或改变训练资格。
