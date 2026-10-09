# foreach_norm Troubleshooting

## [验证] 特殊值 case 的 metadata JSON 序列化失败

**现象：** case 12 在生成输入和 golden 后，`json.dumps(..., allow_nan=False)` 拒绝序列化 `value_range=[-inf, inf]`。
**根因：** 标准 JSON 不支持非有限浮点字面量；原始 case 的范围端点被直接放入 metadata。
**解决方案：** metadata 中将非有限范围端点规范化为 `"-inf"` / `"inf"` 字符串；实际输入和 torch golden 仍使用 IEEE infinity。
**经验：** 特殊浮点值应在持久化边界显式规范化，不应放宽为非标准 JSON。
**预防：** case runner 在写 metadata/results 前统一处理所有 attrs 和范围字段的非有限值。
