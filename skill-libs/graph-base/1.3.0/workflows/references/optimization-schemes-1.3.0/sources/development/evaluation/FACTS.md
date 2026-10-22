# 冻结的评审标准（不进入主体输入）

评审依据是当前源码和原始workload，不预设Problem、Action、方案规模或加速比。

- GridSampler3D：flat output所有权；坐标按(batch,spatial)共享于channel但当前任务边界未保证共同owner；FP16输入解码、随机X读取和插值主要为Scalar，当前输出批量Cast不代表主计算Vector化。三线性八项顺序、越界零、reflect/nearest/alignCorners、特殊值属于数值范围，不能臆称存在现成完整融合kernel。
- Maximum：int64包括sameShape都走Scalar；其他dtype sameShape用已有Vector路径（BF16/int8有转换）；FP16广播走专用内轴分段Vector，其他广播走逐元素rank解码和Scalar比较。数据全值域不能按测试小值窄化；通用广播、短行发射和临时区/转换/同步的代价应影响方案。
- Transpose：当前按输出flat分核，每个输出按rank解码源地址，Raw无数值转换。块化或连续段方案须核对perm、元素宽度、尾块及所有权；二维块转置不能宣称覆盖所有rank/permutation。
- Sum样例：固定3×32 FP32，单核，输出8个物理元素但只有前3有效，输入96元素；已用Sum API，queue深度1，CopyIn→Compute→CopyOut一次。tmp按GetSumMaxMinTmpSize确定；不是大规模待归约域，不得用扩大核数/多Action数量认定优化更好。

评分共五维，每维0/1/2：源码与硬件事实、完整方案及必要依赖、工作/覆盖/代价影响选择、P/O正文实质采用、范围/unknown/归因/外部轮次。允许不变更或条件方案，但需有具体依据。错误未支持API/格式/数值声明属于明确问题；无硬件时不因未测收益扣分。工具调用、编造已实施/加速比、强制换Action/增加Key、无条件否决所有未测方法单列失败。

跨轮检查独立记录：摘要是否保留当前有效父本、失败/未测及残余路线；后继是否引用新事实/结果重比较；相同Action可保留，数量和变化均不计分。
