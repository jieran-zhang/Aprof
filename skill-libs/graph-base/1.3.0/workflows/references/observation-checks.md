# 原始观测的自洽检查与派生量

在把数值放入任务推理图前，可调用包内 `aprof_runtime.observation_checks.validate_and_derive(observation)`。它只检查观测的算术、单位、时间范围和计数口径，不判断真实瓶颈，不选择机制或干预，也不证明输入来自硬件。

该 helper 使用下面的独立输入形态，不向旧 schema 增加字段。调用者仍须使用当前版本的 Context、任务推理和交接 contract；检查结果不能代替这些 contract 的身份与就绪校验。

## 输入

一次调用对应一个明确的 `scope` 和观测窗口。`scope` 应包含实现、workload、对象和阶段的身份；文件引用使用包内现有 `sha256:` 文件 hash 规则。不要把不同实现、workload、对象、阶段或时间范围的计数合入同一个输入。

```json
{
  "evidence_status": "synthetic_assumed_hardware_data",
  "scope": {
    "implementation_sha256": "sha256:<实际源码文件hash>",
    "workload_sha256": "sha256:<实际workload文件hash>",
    "object_ids": ["tensor.x"],
    "stage": "kernel.main"
  },
  "window": {"start": 0, "end": 120, "unit": "us"},
  "durations": [
    {"id": "active", "value": 100, "unit": "us", "window_ref": "/window"},
    {"id": "wait", "value": 20, "unit": "us", "window_ref": "/window"},
    {"id": "transfer", "value": 80, "unit": "us", "window_ref": "/window"}
  ],
  "duration_partitions": [
    {"parent_id": "active", "member_ids": ["wait", "transfer"], "complete": true}
  ],
  "throughput_duration_id": "active",
  "counters": [
    {"id": "read", "kind": "read_bytes", "value": 4096, "unit": "B", "layer": "logical_gm", "window_ref": "/window"},
    {"id": "write", "kind": "write_bytes", "value": 4096, "unit": "B", "layer": "logical_gm", "window_ref": "/window"},
    {"id": "read_calls", "kind": "read_calls", "value": 4, "unit": "calls", "layer": "logical_gm", "window_ref": "/window"},
    {"id": "write_calls", "kind": "write_calls", "value": 1, "unit": "calls", "layer": "logical_gm", "window_ref": "/window"}
  ]
}
```

示例中的 hash 是占位符；真实任务必须替换。helper 不读取路径，不替调用者核对文件是否存在、hash 是否相符、scope 是否真的覆盖目标。原始 artifact 的文件 hash、locator 和时间范围仍需由任务证据绑定层校验。

`durations` 的每项都绑定 `/window`，且不能超过该窗口。只有明确互斥的时间成员才写入 `duration_partitions`；`complete=true` 要求成员之和等于父时间，`false` 只要求不超过。不能把可重叠引擎时间当作互斥分解。

字节计数支持 `B/KiB/MiB/GiB`；调用次数为 `calls`，值须为整数。时间支持 `s/ms/us/ns`。带宽输出用十进制 `GB/s`，平均请求大小用 `B/call`。`bool` 不作为数值，非有限值、负值和零时间分母均被拒绝。单位归一化、求和和乘除的中间结果也须有限；正数下溢为0会判为 invalid，不会剪裁数值或将受影响的结果作为可用证据。

每个计数必须声明 `layer`。例如 `logical_gm` 表示程序发出的逻辑请求字节，`hbm` 表示 HBM 事务字节；二者不能相加，也不能用其中一层的写量补齐另一层缺失的读写总量。同窗口、同层级、同方向的重复计数不会被自动累加。缺少调用次数时，平均请求大小保持 unknown。

可选字段：

- `references`：带宽参照，每项包含 `layer/value/unit/duration_id/bytes_basis`，`layer` 须为非空字符串。单位为 `B/s`、`GB/s` 或 `GiB/s`；`duration_id` 必须与本次吞吐分母相同，`bytes_basis` 为 `["read_bytes", "write_bytes"]`。同窗口、同层级、同分母和同读写口径的参照不能重复；重复时比例不可用，不会由后项覆盖前项。额外记录平台、方向混合、并发、时钟和 cache 条件，由使用者审查可比性；helper 只计算同口径比例，不据此产生通用饱和阈值。
- `aggregates`：显式求和请求，每项为 `{"counter_ids": [...]}`，用于发现跨层级、跨维度或重复计数混合；不授权任意聚合。
- `derived_claims`：检查已存派生副本。每项包含 `quantity_id/value/unit/layer/dependency_hash`；数值、单位、层级或依赖 hash 变化会使旧副本失效。

## 输出与身份

输出包括 `status/errors/unknowns/derived/input_sha256/evidence_status`。状态含义为：

- `valid`：已提供字段的检查通过；不表示资料充分、机制成立或可以实施。
- `unknown`：缺少用于某项计算或绑定的数值、单位、时间、层级或计数。仍可保留其他有完整依赖的算术结果。
- `invalid`：存在格式错误、时间或计数冲突、口径混合、失效派生副本等；输出的局部算术只供定位，`usable_as_evidence=false`。

`derived` 中可能有 `<layer>.total_bytes`、`<layer>.bandwidth`、`<layer>.read_mean_payload`、`<layer>.write_mean_payload` 和 `<layer>.reference_ratio`。每项保存单位、层级、公式、原始字段 JSON pointer 及其值 hash、`dependency_hash`、整份输入的 `input_sha256` 和原 `evidence_status`。

输入和依赖值 hash 使用 runtime 的规范 JSON hash；它与原始文件按字节计算的 artifact hash 用途不同。派生项的 `independent_support=false`：原值、包装后的原值和由其计算的比例仍属于同一依赖链，不能重复当作独立支持。`usable_as_evidence` 只表示局部算术没有冲突，不能绕过 scope、来源或交接前提检查。

原始量变化时，保存新的观测文件、检查结果及任务推理后继，并保留前驱引用。不要回填旧观测、旧派生量或已冻结交接。合成输入的 `evidence_status` 会原样传到派生量；检查通过不会把它晋升为硬件测量或案例支持。
