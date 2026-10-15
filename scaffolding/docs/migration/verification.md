# 0.4.1 迁移验收

验收环境为 Python 3.11，使用 CPU 与合成证据；未执行 CANN/NPU 性能实验。
完整回归在独立复制到 `/tmp` 的仓库中运行，显式选择副本内的 release；
最终 Python 源码与该副本逐文件一致。

| 检查 | 结果 |
| --- | --- |
| 完整 CPU 回归 | **2711 passed，11 skipped**，742.95 秒 |
| 最终稳定包、registry、workflow、profiling 工具及 release binding | **25 passed** |
| 独立目录安装 runtime | `tools/install.py --runtime` 成功，安装后 seal 校验通过 |
| 独立使用 | 两版图校验、路由、contract、合成 gate/episode、内置工具 smoke test 通过 |
| 发布文件与绑定 | 内容修改、越界链接、错误版本、给历史运行补绑定均被拒绝 |
| 精简证据 | 383 个文件、18,445,244 字节全部通过 hash 校验；禁止读取证据目录外文件时仍可完整读取 |
| 外部证据缺失 | 明确报告 external/not selected，不回退到旧绝对路径，不声称完整离线 closure |
| 字节一致 | 16 个 runtime 模块、22 个机器 schema、8 个图快照文件、956 个 benchmark 非文档文件、54 个 delivery 文件不变 |
| 图重现 | v0002 通过；v0001 的原有差异单独记录，迁移前后重编译结果相同 |
| Git 收录 | 383 个索引文件均已收录；保留原 submodule commit；无旧路径软链接或大型 raw |

11 项跳过为：1 项需要未恢复的外部 cann-bench，1 项需要本地历史运行，
9 项需要完整冻结 Level1 corpus。原基线回归也跳过相同测试。
原基线另有 7 项小型归档 fixture 因 `/tmp` 空间不足默认 64 GiB 预留而失败；
本次将这些 fixture 显式设为小额预算，生产归档预算没有改变。

复现主要检查（从仓库根目录）：

```bash
export APROF_SKILL_LIB="$PWD/skill-libs/graph-base/0.4.1"
python3 -m pytest scaffolding/tests -q
python3 "$APROF_SKILL_LIB/tools/release.py"
python3 scaffolding/tools/sync_aprof_registry.py check --skill-lib "$APROF_SKILL_LIB"
python3 scaffolding/tools/compile_graph_v2.py --skill-lib "$APROF_SKILL_LIB" --check
python3 scaffolding/tools/compact_evidence.py verify --root scaffolding/evidence
```

`compile_seed_graph.py --check` 对 v0001 仍报告既有差异；详见
[graph-reproducibility.json](graph-reproducibility.json)，不能重写历史快照来消除此项。

Level1 保持 37 条 memory / 26 条 lesson；Level2 保持 26/48、暂停、
`graph_policy_eligible=false`。约 435 GiB 原外置 raw 未迁入，完整 snapshot、
payload 和大索引仍外置，因此这里不是完整离线证据包。
本验收不新增硬件性能结论，不恢复实验，不处理 push 认证。
