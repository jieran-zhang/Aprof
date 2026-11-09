# 诊断输出与历史字段迁移

现行正文输出使用[C1 契约](../../../workflows/contracts/diagnosis.md)，机器交接使用 handoff/v4 与 action-decision/v3。任务内假设 ID、机制摘要、支持、反证、未知项和判断理由一并交付。当前 strict JSON 的字段以对应版本 schema 为准。

旧 `diagnosis_hypotheses.json` 的 `hypotheses.id` 对应任务内稳定假设 ID，`summary` 对应机制摘要与适用 workload，`confidence` 的判断依据迁移为支持、反证、未知项与状态理由。历史枚举及历史 JSON 按其原 schema 读取，现行输出显式绑定自己的版本。

正文填写按 C1 必需结果逐项核对，交接验证使用包内现有 contract/handoff 命令。评审者可以从[指标字典](../../ascendc-aprof-profiling/references/metrics.md)核对观察字段与数据来源，再核对方案和 Action 实例的实际绑定。
