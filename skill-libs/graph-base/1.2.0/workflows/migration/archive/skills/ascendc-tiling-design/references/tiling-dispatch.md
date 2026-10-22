# 基于元数据的 tiling-key 分发

workload group 由 shape、dtype、layout 和声明属性定义语义/性能区域，不是 benchmark 编号。先为各组建立并行计划，再建立绑定同一架构档案与源码谱系的严格 `dispatch_plan`。计划的 `source_hash` 指分析父版本，分发的 `source_hash` 指实际实现。新记录在 dispatch 和 `Context.workload` 都保留 `plan_basis_source_hash`、`implementation_source_hash`，路由上下文仍指提议父版本。计划 JSON 放源码快照外，避免 hash 自引用。

每个 entry 含 `group_id`、uint64 `tiling_key`、C 标识符 `kernel_entry`、元数据 `conditions` 和能力要求。key 标识实现而非单个输入，区域应覆盖相邻未见 shape。保留条件为空的通用 fallback；条件不得重叠，多重匹配由 runtime 拒绝，不能靠顺序隐式选择。不使用参考输出、任意数据值、case ID 或是否正在评测来分发。

```bash
aprofctl contract validate --kind dispatch_plan --input <dispatch.json>
aprofctl dispatch select --plan <dispatch.json> --workload <metadata.json>
```

selector 仅供验证和参考，编译后的 Host 必须执行等价条件，key 必须改变真实 kernel 路径：

- 注册式 CANN 算子：在 Host Tiling 设置 key，使用匹配 SDK 的 key/template 注册与 kernel 分支。
- 直调：Host 选择已编译 launcher/entry，或显式传 `uint64_t tilingKey` 并在 kernel 分支；同步修改声明、启动和定义，不能假定无 SDK tiling 机制时 `TILING_KEY_IS` 仍有效。

全部 entry 保留原接口和 checker。tile 长度/blockDim 在选定区域内仍由容量推导，不能用 key 专属硬编码 UB/核数替代运行时查询。先完整正确性，再评估受影响组及全部其他组、fallback 的回归。

验收记录每个 case 的元数据 → group → key → entry；条件边界包含相等值与相邻值；未见合法元数据进入合法优化区域或 fallback；重叠、未知元数据失败需明确；强制或记录的 key 与真实路径一致。保留 dispatch/plan/profile hash、源码和 trace。改分发条件产生新 dispatch 版本，改分解或所有权产生新 parallel plan。
