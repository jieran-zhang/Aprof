# 采集与报告身份

固定上游文档支持 Ascend 950（dav-3510）的 Ascend C `__cube__`、`__vector__`、`__mix__` kernel，通过 `<<<>>>` 或 aclnn 单次调用一个算子。任意多算子 runner 不自动满足该契约。工具需匹配 CANN，master 安装说明不授权独立升级。

记录安装的可执行文件/版本，选择命令前查询能力；下列命令不执行目标：

```bash
npu-compute --help
npu-compute --list-sets
npu-compute --list-sections
```

Set/Section 名区分大小写。固定版本列出的集合如下，安装版本输出具有优先权：

| Set | Section 次序 |
| --- | --- |
| `basic` | Pipeline, PipeUtilization, Memory, MemoryL0, MemoryUB, L2Cache, ArithmeticUtilization |
| `full` | basic 全部内容，再加 ResourceConflictRatio |

按问题使用单独 `--section`。Set 与 Section 按命令顺序展开，首次出现去重；`basic` 加 `ResourceConflictRatio` 对应文档的 `full`。只选假设所需视图。

在目标工作目录执行：

```bash
npu-compute --section PipeUtilization --section Memory -- ./operator <arguments>
npu-compute --set full --export <new-report.npu-rep> -- ./operator <arguments>
npu-compute --import <existing-report.npu-rep> --export <existing-export-parent>
```

`--` 后参数全属目标；不可执行脚本需解释器。目标不能包裹构建、数据生成、验证或另一层 npu-compute。

采集成功需退出码 0、stdout 给出 `npu-compute: report= <path>`，且该 `.npu-rep` 存在。导入成功需退出码 0、stdout 给出 `npu-compute: unpacked= <directory>`，且目录有可识别结果。使用这些真实路径；导入的 `--export` 是父目录，工具建立唯一子目录，不猜名称或覆盖旧报告。

根结果和各 `collection-p...` 分开，用本结果 summary 的 `OpInfoSummary` 识别 kernel，不能借用相邻结果或 msprof 目录规则。身份缺失或多结果歧义未解决时，不做正式标准化。

AProf 机制采集使用 [采集接口](../../ascendc-aprof-profiling/references/collector-interface.md)，manifest 绑定原始报告、workload、source、device 和政策。内部 replay、PMU 行与 Pipeline 采样组都不是独立重复。上述原生命令只有满足 AProf 独立采集与正确性要求时才能进入机制证据；也不能代替 [统一性能计时](../../ascendc-aprof-profiling/references/unified-timing.md)。
