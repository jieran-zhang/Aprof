# 题 3

请阅读完整 source（含 host、参数/tiling 和 kernel 上下文）及 workload。本题要求理解现有实现，请提交一份连贯的代码理解说明：先解释输入输出与整体算法，再解释当前实现怎样分工、搬运、计算和同步，最后说明目标硬件上的执行行为、适用边界和证据不足之处。

用 workload 中的值做必要的具体推导，让地址/计数的单位明确。请给出能定位到源文件/符号的依据。不要预选 Problem/Action，不要求提出优化或改代码。只写能由本题材料支持的结论；字数和引用数量不计分。

固定 SDK 契约见本目录 `sdk-contract.md`，与所有其他题完全相同；API 原文在公共根目录 `shared/rawdocs`。

分析 `source/op_host/maximum.asc`、`source/op_kernel/maximum_tiling.h` 和 `source/op_kernel/maximum_kernel.asc`。固定 host 查询得到的 Vector 核数为 4，所有输入是连续 ND，无额外分配余量。

比较以下三次独立调用，每次 x1 的逻辑值都为 `[[1,4,8],[2,5,9]]`：

| 调用 | dtype | x1 shape | x2 shape | x2 数据 |
| --- | --- | --- | --- | --- |
| P | float16 | [2,3] | [2,1] | [[3],[7]] |
| Q | float32 | [2,3] | [2,1] | [[3],[7]] |
| R | float16 | [2,3] | [3] | [3,7,6] |

请分别沿 host tiling、分派条件、实际地址与计算路径说明这三次调用。再概述文件中其他 dtype/shape 分支的实现策略。对三次调用的输出或执行边界，给出由当前源码可以支持的结论和必要的保留项。
