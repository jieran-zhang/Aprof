# 源码观察入口

输入包含 Host、Tiling、kernel 源码及 workload。逐项记录地址计算、循环有效域、Scalar/Vector API、数据类型、分派、别名和输出所有权。事实引用具体源码行、源码 hash 与适用输入。

Scalar 观察描述循环中实际执行的逐元素标量读写或算术，以及该循环的迭代域、条件分支和处理对象。配置字段读取和控制流循环分别说明。算法观察记录排序范围、归约遍数、重复读取及工作量公式。

本页只维护源码观察。观察与后续假设的交接由[C1 契约](../../../workflows/contracts/diagnosis.md)定义，当前字段由[输出迁移说明](output-contract.md)定位。
