# Troubleshooting

## 2026-08-11：GM scalar 不能直接传给 Muls

- Symptom：bisheng 报 `Muls` 模板推导冲突，参数类型为 `__gm__ float`。
- Root cause：`tiling_->scalar` 是 GM 地址空间引用，而 `Muls` scalar 参数需要 device 局部普通 `float`。
- Fix：在 `Compute` 开头以 `const float scalar = tiling_->scalar` 加载到局部变量，再传给两条 dtype 路径。
- Prevention：来自 tiling GM 结构的标量在传给 AscendC vector scalar API 前，先显式复制到 device 局部同 dtype 变量。
