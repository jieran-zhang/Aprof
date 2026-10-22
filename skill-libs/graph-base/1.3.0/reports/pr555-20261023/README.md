# PR #555 核对与 CPU 全量回归

日期：2026-10-23。来源分支：`refactor/skill-libs-scaffolding`；修复基线：`1b783b05c460f51688f77ee8661963545cad2dfa`。

## 结果

本次运行收集 564 项：通过 564，失败 0，初始化错误 0，跳过 0；退出码 0，耗时 408.94 秒。
运行对象是指定 GitHub 分支的原始 Git 导出加本次修复，保留仓库路径、完整历史材料与 scaffolding 兼容入口；不是删减包、只跑代表项或设置 maxfail。
完整输出见 [cpu-regression.log](cpu-regression.log)，机器摘要见 [regression-results.json](regression-results.json)。

结构校验 `python tools/release.py --allow-unsealed` 已通过，身份仍为 graph-base/1.3.0、unsealed、structure_only；不代表稳定发布或 NPU 收益验收。
额外对照原始 Git 字节核对 3,504 份历史/来源文件：改动 0；没有改写原始快照 hash。

## 实际修复

1. 公开 `knowledge validate-chain` 与 v4 `knowledge link-result` 按 C2 已绑定的内容地址加载精确路由快照，继续核验 C1/C2/C3、来源与 hash。旧 D6 示例不再误用活跃 D7；缺快照和篡改快照仍拒绝，新增两项反例测试。库函数默认 current 的语义不变。
2. D3→D4 历史测试夹具只携带该夹具确实注册的 Action 及 variant review，并断言所有历史 Action 仍被覆盖。未来版本夹具按当前策略版本写入冻结文件，只复制历史图中存在的 Action。生产路由的完整覆盖要求没有放宽。
3. workload 反馈测试补传 timing_version，并同时覆盖 timing v1/v2。旧单实例回放测试固定 D6，不把历史格式构造成缺 workload 映射的 D7 新记录；D7 映射拒绝测试保留。
4. 独立包测试不再固定取第三层祖先；开发仓库兼容测试使用独立的无 handler 目录，避免依赖旁边必须存在 1.0.0。该测试在本次仓库布局运行中执行，没有以 skip 隐藏。
5. Python 工具链测试先用真实解释器检查架构不符应拒绝，再只模拟 fixture 的 aarch64 声明，以继续验证真实 venv、NumPy 导入与文件清单；不代表 x86 主机获得真实 aarch64/CANN 资格。测试依赖显式加入 NumPy 与 pytest-xdist。
6. 包内 `.gitattributes` 保留精确字节，避免 Windows 自动换行转换破坏受 hash 约束的检出/导出。

## 测试过程中遇到的问题

- 首轮 GitCode 导入包使用 `/tmp`：418 passed、97 failed、51 errors。其中 89 个失败先被“执行产物必须位于 /dev/shm”拦住，不能据此判断其下游逻辑。
- 改用 `/dev/shm` 后：493 passed、9 failed、64 errors。Docker 默认 noexec 阻止复制出的 venv 解释器执行，4 GiB 容量也不足；另有真实的历史夹具和公开回放错误。
- 本机 `core.autocrlf=true` 还影响了早期 Git archive，导致导出件出现大量来源 hash 错误。已通过 `git cat-file blob` 核实关键原始 Git 对象正确；这是本地检出/导出问题，不是 GitHub 源提交的 3,493 份文件有内容缺陷。错误导出运行未用于最终结论，也没有提交批量行尾更改。
- 最终使用 Linux/Python 3.12.15，Docker `--tmpfs /dev/shm:rw,exec,size=12g`，4 个 pytest worker，并关闭 Git 导出换行转换。真实包/测试问题通过上述修复处理，未减弱生产门禁或删除失败断言。

## 复现

在 Linux 的包目录执行，确保 `/dev/shm` 足够且允许执行测试复制的解释器：

```bash
python -m pip install -e 'runtime[test]'
PYTHONPATH=runtime/src PYTHONDONTWRITEBYTECODE=1 python -m pytest runtime/tests -n 4 -q --tb=short --basetemp=/dev/shm/aprof-pr555 --junitxml=/tmp/aprof-pr555.xml
python tools/release.py --allow-unsealed
```

`--basetemp` 必须选择本次专用的新测试目录。Windows 获取固定字节时使用 `git -c core.autocrlf=false archive`，或使用本包的 `.gitattributes`。

## 仍未完成的评审和平台事项

40 条评论逐条结论见 [pr555-comment-audit.md](pr555-comment-audit.md)，原评论、作者、具体引文与行号见 [pr555-comment-audit.json](pr555-comment-audit.json)。21 条满足、12 条部分满足、3 条未满足、3 条随旧模块移除、1 条待真实环境验证。
CPU 回归通过不等于全部评审要求完成。BT/FP buffer、Current/Rated Freq 的域、算法注入评测，以及部分过开核/角色/身份迁移要求仍须按清单处理；没有修改 GitCode 评论的 resolved 状态。

GitCode 在旧 head `be463915a6667f0bbe7d9b1f6706562f73bacc76` 的已核实剩余平台门禁是许可证 SCA 审核和历史 Markdown 检查工作流。SCA 对 Apache 标准正文的匹配需平台审核人处理；评论触发工作流采用目标分支时，需要维护者应用冻结 Markdown 的校验/过滤适配。它们与本报告中的 CPU 缺陷及环境问题分别记录，不能把所有失败归为平台问题。本次 GitHub 提交也不等于 GitCode 新 head 的流水线已通过。

本机无 NPU/CANN 真实设备验证；编译命令、精度、真实 profiling 与收益未宣称通过。
