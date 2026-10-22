# 独立目录无网络回放结果

结论：通过。完整副本的 unsealed release 检查通过；修复任务回执索引后，case-01、case-08、case-14 共六轮回放全部通过，均保持 conditional，未产生正式 C2/C3 选择或性能收益声明。

## 独立副本与运行方式

- 副本：`/dev/shm/aprof-offline-review-20261021-9jxz7nc8/graph-base-1.3.0`。初始完整复制 2,104 个文件、47,329,192 字节，无符号链接；复制时 `/dev/shm` 剩余约645GB。
- 两入口分别由 `python -I guarded_run.py` 调用副本内工具，工作目录也是副本。禁写 bytecode，原包和冻结快照均未由本审阅修改。
- 实际命令为副本 `tools/release.py --root COPY --allow-unsealed`，及 `tools/replay_source_regression.py --root COPY --case case-01 --case case-08 --case case-14 --output ...`。入口均没有算子/编译器/硬件执行。

## 审计规则与实际结果

`guarded_run.py` 保存了完整审计规则。路径经 realpath 解析：仅允许读取副本、该次审阅输出目录及 `/usr/local/python3.11.15` 运行时；写入仅限该次审阅输出目录。禁止全部 `socket.*`、子进程/exec/spawn/fork、`ctypes.*` 和新符号链接；副本写入也被拒绝。因采取白名单，原仓库、全部 `/tmp/aprof-raw15*`、维护临时目录及任何外部上游检出均不在允许范围。

每个受控进程都实际尝试访问原仓库、原始输入、执行组输出、维护目录、外部上游路径以及创建 socket：6项均被拦截。工具正常执行期间，禁止访问事件为0，未出现网络/子进程执行。详见 `release-audit.json` 与 `retry-1/replay-audit.json`。

## 第一次失败与最小修复

初次 release 成功：`valid=true`，`status=unsealed`，`verification=structure_only`，计入2045个发布有效文件（与完整复制文件数的差别来自缓存等忽略项）。初次三项回放在 case-14 的检索一致性检查失败；完整日志保存在 `replay.log`。

独立差异诊断确认 case-01/08 两轮检索和展开均匹配。case-14 的共享历史检索使用旧 Context：`context_hash`、`observations/41/state`（unknown→true）、`source_context_ref`（C0-source-only→source-authority）及 `symptom_adjacency` 不同，旧展开也不匹配当前 Context。原包实际已有正确的 R1/R2 前缀回执；问题是 inventory/harness 选用了未带前缀的历史记录。详情见 `replay-differences.json`。

主执行方修正逐轮 entry 回执索引及工具读取逻辑。本审阅按授权只将更新后的 `tools/replay_source_regression.py` 和 `source-regression-15/inventory.json` 同步到独立副本。其余 runtime/tools/schema/skills/任务cases文件与当前原包全量hash一致；新旧副本也只有这两文件变化。随后六轮均通过。按授权复用已通过的 release 结果，未重复 release 检查。

|任务|R1|R2|Action|
|---|---|---|---|
|case-01 Exp|通过；conditional|通过；conditional|software_pipeline_stages|
|case-08 GridSampler3D|通过；conditional|通过；conditional|hoist_invariant_control|
|case-14 Transpose|通过；conditional|通过；conditional|reorder_contiguous_access|

最终回放日志：`retry-1/replay.log`；完整六轮结果和实际 P 候选/O 咨询：`retry-1/replay-result.json`。候选/咨询不代表正式选择，全部 `formal_C2_C3_selection=false`、`performance_claim=false`。副本在最终回放前后全部字节未变。

## 最终身份

- 诊断知识内容 hash：`sha256:484e2107fbff032161df166d17b7be3b4ace2a34b8f98a843a1d9a629d0f3dc5`。
- runtime/src + tools 的49个有效代码文件清单摘要：`sha256:aebfc9490bee2a2f099c9653d3f0aeff909f30d21f4637bb7cb4c4a9322b9542`。
- `tools/release.py`：`sha256:a5a2831302483856b84285249df5d071740a461b7e89bbf455fd629e22248515`。
- `tools/replay_source_regression.py`：`sha256:7d7fad6ea627e658c0d4f61c1e72ea46c26ce7bc87c87ee8d4550fdd94e5d95b`。
- `runtime/src/aprof_runtime/action_decision.py`：`sha256:2df71cd39e0610e0332126b57975c1715672e4ea73aec6f408ffa85a73bd269d`。
- `workflows/references/source-regression-15/inventory.json`：`sha256:680ad1f027b945fd927ac957819debf0ab9a3bbbd60d561e6f2769a9d9a905f7`。

完整文件hash在 `retry-1/copy-inventory.json`；REGION 内容及初始身份在 `copy-metadata.json`；两文件更新前后hash在 `retry-1/copy-update.json`。原包随后仅新增报告导航的 README 变化未复制；该差异不属于代码、知识或任务证据。

## 限制

这是 Python audit hook 隔离检查，不是 OS 沙箱；hook 在解释器初始化及标准 runner 导入后安装，不能声称覆盖全部 stat/access 元数据或未经过 Python 审计接口的任意原生代码。标准 Python 和已安装运行依赖可读。此次实际受检代码没有触发这些逃逸方式；没有网络、硬件、算子编译、训练或原 oracle 执行。

unsealed 检查不授予正式发布验收。回放证明保存记录的身份、推理契约、正文展开及路由可以从包内重放，不重演 Agent 推理，也不证明完整数值正确性或性能收益。
