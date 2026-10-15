# 1.0.0 runtime 0.2.3 已应用记录

用户明确授权仅升级未封存的 `graph-base/1.0.0` runtime，并重新验收受影响链路后，已应用原 `case-binding.patch`。`README.md` 与 `index.json` 保留此前未应用草案的记录；本文件与 `applied-index.json` 描述当前状态。

## 后续完整调用 PMU 接口补充

未发布的 1.0.0 随后增加完整多 kernel PMU 回放入口及 collector 的逐次证据绑定；精确差异见 [补充记录](full-call-pmu-applied.json)。该接口沿用原 CV、capture、warmup 与机制方向判定，缺少可核验频率证据时保持 unknown。旧单 kernel 分支保留；独立硬件资格仍待完成。下方六文件清单和 37 项结果描述首次 v5 应用时的记录。

## 修改范围

- runtime：原 v5 补丁的三个 Python 文件；`__init__.py`、`pyproject.toml` 标记 `0.2.3`；`store.py` 两处已支持版本集合增加 `aprof-runtime/0.2.3`，继续调用完整 `CandidateGate.evaluate`。
- collector：`device_task_window_timing.py` 使用完整 case/role map；`profile_capture.py` 的 `identity_state` 与 `source_bundle` 统一调用既有 `canonical_json`，UTF-8、无尾部换行，与 Task producer 完全一致。
- `profile-source-canonical.patch` 只改一个 collector 文件的 import 和两处序列化。没有修改 `profile_evidence.compare_profiles`，没有绕过原始 source hash 相等要求。profile manifest 与执行回执保留既有 schema 和写入格式。

v5 对全部 case 和两个 role 要求 map，包括单 kernel 的 exp/sigmoid；不存在 scalar 回退。旧 v4 回执继续由已发布 0.5.1 回放，不能重新标成 v5。采样 repeat、全部任务序列、完整 callback、gate 数学及 v0002 拓扑未改。

## 检查结果

| 检查 | 结果 |
| --- | --- |
| 原 v5 临时补丁检查 | 25 passed / 5.15 s |
| collector canonical 修复与未改 runtime | 9 passed / 3.31 s |
| 已应用 1.0 runtime 0.2.3 与两个 collector 的临时副本 | **37 passed / 8.44 s** |

最后一组命令：`python scaffolding/curation/task-case-binding-v5/run_applied_checks.py`。仅在临时测试副本放宽旧合成 fixture 的版本 skip 条件；没有伪造 runtime 版本或修改被测生产源码。

collector 检查使用受控 CPU 子进程：两角色分别完成 10 次预热和 5 次采集，核对每份真实执行回执的前后 source hash、完整 source bundle 与 Task canonical hash，再由未改的 runtime 完整回放并比较 profile。改文件、漏文件、多文件及未索引的嵌套 source 引用均拒绝。采集后的 manifest 原字节保持不变。没有调用 CANN、NPU 或真实 profiler，也没有归档真实 profile。

`applied-index.json` 记录 runtime 相对 0.5.1 的精确六文件差异及两个 collector 的哈希；其余 runtime 文件、schemas 和 v0002 文件与基线逐字节一致。版本专用 `skillgraph/registry.json` 不属于“两个发布包全部字节相同”的声明。

## 发布状态

1.0 仍是待复验候选。此处的 CPU 结果只证明接口和身份绑定，不构成硬件资格或稳定版发布。`R >= 100` 的完整多 kernel 成本仍待独立预登记判断。0.5.1 的文件与 stable manifest 未改动。
