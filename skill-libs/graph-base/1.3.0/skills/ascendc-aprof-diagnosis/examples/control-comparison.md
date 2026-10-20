# 图外机制复用既有变换

证据状态：paper/source_review；未构建、未运行、无profiling或性能结论。

## 输入与未知

纸面细化练习：现有 problem.control_metadata_overhead 已覆盖一般的热点重复读取。这里暂以未注册的 temporary.metadata_decode_repeated 表达当前目标的具体解释，练习图外候选复用注册 Action；这并不证明目录缺少新机制。源码可以定位读取和使用点；是否不变、是否别名／副作用、编译后开销仍待检查。

## 机制比较与判别

把临时解释与现有控制开销模板并列比较，记录预期重复项和可反驳情况；若只是当前对象与参数的细化，应归入既有模板实例，不提案新增 Problem。只有发现旧模板无法解释的机制差异，才补充其不足与判别方法。预测是外提后动态读取／地址计算次数减少，不能直接预测一定加速；若编译器已外提，或字段实际随tile变化，此解释应修订。

不新增模板边、不创建临时新Action。用原始位置和同一scope核对不变性；计时更快也不能跳过是否混入其他变更和预测是否出现的检查。

## Action实例与两阶段交接

可复用`action.hoist_invariant_control`，逐条检查control_metadata_overhead、control_equivalence、semantic_equivalence、capacity。未知时C2先分析，不可直接实施；原前提齐全且计划许可时P_KEEP，C3选择hot_loop_address或tilingdata_access。标量spill动作另需compiler_report，不能混借。经判别仍存在独立机制差异时才形成提案，不自动晋升图。

新增证据创建后继reasoning/C1/C2，不修改本纸面输入。机器记录见同名JSON；该记录不作为case_support。
