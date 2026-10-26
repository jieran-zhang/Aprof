# 题 4

请阅读完整 source（含 host、参数/tiling 和 kernel 上下文）及 workload。本题要求理解现有实现，请提交一份连贯的代码理解说明：先解释输入输出与整体算法，再解释当前实现怎样分工、搬运、计算和同步，最后说明目标硬件上的执行行为、适用边界和证据不足之处。

用 workload 中的值做必要的具体推导，让地址/计数的单位明确。请给出能定位到源文件/符号的依据。不要预选 Problem/Action，不要求提出优化或改代码。只写能由本题材料支持的结论；字数和引用数量不计分。

固定 SDK 契约见本目录 `sdk-contract.md`，与所有其他题完全相同；API 原文在公共根目录 `shared/rawdocs`。

分析 `source/matmul_leakyrelu_basic_api.asc` 的完整调用。采用文件中 main 的所有常量：M=512、K=128、N=128，singleCoreM=256、singleCoreK=128、singleCoreN=128，baseM=256、baseK=128、baseN=128。输入 A 与 B 都是 half、连续 ND，分别按 [M,K] 与 [K,N] 存放。

本题实际目标为 910C/2201。请说明最终计算关系、分核和每个分支处理的范围、各存储层的数据类型与排布，以及从输入到最终输出每条关键依赖如何得到保证。说明源码中的其他平台分支在本次分析中的地位。
