# 题 5

请阅读完整 source（含 host、参数/tiling 和 kernel 上下文）及 workload。本题要求理解现有实现，请提交一份连贯的代码理解说明：先解释输入输出与整体算法，再解释当前实现怎样分工、搬运、计算和同步，最后说明目标硬件上的执行行为、适用边界和证据不足之处。

用 workload 中的值做必要的具体推导，让地址/计数的单位明确。请给出能定位到源文件/符号的依据。不要预选 Problem/Action，不要求提出优化或改代码。只写能由本题材料支持的结论；字数和引用数量不计分。

固定 SDK 契约见本目录 `sdk-contract.md`，与所有其他题完全相同；API 原文在公共根目录 `shared/rawdocs`。

比较 `source/baseline/mmad.asc` 与 `source/variant/mmad.asc`；差异完整列于 `source/VARIANT.patch`。两者都固定 `SCENARIO_NUM=1`、host 宏 `NPU_ARCH=2201`、device 宏 `__NPU_ARCH__=2201`，其余使用 main 中所有常量。B 的 GM 文件按 [N,K] 连续存储，它对应逻辑 [K,N] 矩阵的转置存储。

请解释整个矩阵乘的分核、循环和数据路径，再选一个输出 tile，具体说明前 10 个 K 迭代中各级 buffer 的物理位置、选择和复用，以及各事件建立的执行关系。比较两个版本在可证明依赖与执行保证上的差别，明确静态材料对实际运行结果的支持边界。
