# 原始输入 03

算子：`masked_scale`。这里是原始种子的只读源码摘取，不含本批历史优化结果。

- `op_host/`、`op_kernel/` 保留 host、tiling 与 kernel 原文。
- `scripts/cases.py` 是原始 20 case；`matrix-20.json` 是其静态解析，特殊数值编码见文件。
- layout、dtype、数学语义及 oracle 定位见 `SOURCE-MANIFEST.json`。
- Python 文件只供阅读；本次不运行数据生成、验证、编译、native 或硬件命令。
- 没有真实性能数据，未知成本应保持未知。
