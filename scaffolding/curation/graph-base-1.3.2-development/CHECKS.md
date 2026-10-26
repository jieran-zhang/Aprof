# 1.3.2 迁移检查

检查时间：2026-10-24T04:35:56+00:00。runtime 0.8.3，本版未封版；只进行 CPU 和离线检查。

| 检查 | 结果 |
| --- | --- |
| 独立安装、知识、来源、许可、快照、路由及包内导航 | 通过；graph-base/1.3.2，共 1,299 个文件 |
| runtime 全套 564 项 | 563 通过、1 跳过，零未解决失败 |
| 受影响隔离夹具复查 | 3 项通过；纸面合同的原断言已迁入开发审计 |
| 构建报告及旧编译定向检查 | 31 项通过，计入上述全套，不重复累计 |
| 开发审计及边界测试 | 审计通过，9 项测试通过 |
| 源码回归 | 15 例、30 轮通过 |
| 选择回归 | 15 例、30 轮通过 |
| 包外报告 CLI 演练 | 53 个知识链接有效；包内初始化报告为 0 |
| 原 1.3.1 | 1,518 个文件的路径与字节均保持 |
| 保留依赖身份 | 981 个来源、schema、知识正文及冻结版本文件的字节保持；冻结编译器等同于旧 knowledge.py |
| 221 个归档文件 | 215 个原字节不变；6 份 Markdown 只修正链接目标 |

完整测试在逐文件核对 hash 的本机临时副本中执行；测试临时目录在被禁读的仓库之外。独立目录演练阻断开发仓库、两个 scaffolding 归档和网络，覆盖知识重建、CLI、安装检查和交接。工作区最终与已测试副本再次逐文件核对。唯一跳过项是原仓库缺少旧 scaffolding dispatcher 的可选兼容测试，未新增跳过项。

开发审计逐项验证 221 个材料、8 项迁移分区、196 个种子文件及 195 个旧节点、4 份纸面案例和 2 项 pending 提案。纸面案例保持 not_run，pending 提案不具备晋升资格；空目录、损坏种子、缺失迁移项、错误合同和丢失运行时 provenance 都有拒绝用例。安装检查不再读取已迁出的材料。

## 文件统计

统计为递归普通文件数，包含隐藏文件；新包没有生成缓存。

| 对比 | 1.3.1 | 1.3.2 | 减少 |
| --- | ---: | ---: | ---: |
| 完整包 | 1,518 | 1,299 | 219 |
| skills | 991 | 770 | 221 |

完整包净减 219：迁出 221 个文件，新增冻结编译器和报告输出测试各一个文件。新归档材料 221 个，加上索引、清单、审计脚本、测试及本检查报告，共 230 个文件。

| 1.3.2 一级目录 | 文件数 |
| --- | ---: |
| `(root files)` | 5 |
| `.claude-plugin` | 1 |
| `.codex-plugin` | 1 |
| `runtime` | 81 |
| `schemas` | 51 |
| `skills` | 770 |
| `sources` | 219 |
| `tools` | 6 |
| `workflows` | 165 |
| **合计** | **1,299** |

| skills 子目录/直属文件 | 文件数 |
| --- | ---: |
| `ascendc-aprof-diagnosis` | 293 |
| `ascendc-aprof-parallel-planning` | 177 |
| `ascendc-aprof-optimization` | 170 |
| `ascendc-code-understanding` | 45 |
| `ascendc-aprof-profiling` | 31 |
| `tool-npu-compute` | 8 |
| `ops-profiling` | 6 |
| `ascendc-kernel-direct-invoke` | 5 |
| `npu-arch` | 5 |
| `ops-simulator` | 5 |
| `ascendc-api-best-practices` | 4 |
| `ascendc-code-review` | 3 |
| `ascendc-crash-debug` | 3 |
| `ascendc-docs-search` | 3 |
| `ascendc-env-check` | 3 |
| `ascendc-precision-debug` | 3 |
| `ascendc-runtime-debug` | 3 |
| `ascendc-aprof-coordinator` | 2 |
| `registry.json` | 1 |
| **合计** | **770** |

运行命令见 [README](README.md)，机器结果见 [CHECKS.json](CHECKS.json)，逐文件原始/当前身份与迁移映射见 [relocation.json](relocation.json)。历史报告中的原路径按迁移映射解析，不重写其冻结实验身份。未运行硬件实验，未封版、发布或切换默认版本。
