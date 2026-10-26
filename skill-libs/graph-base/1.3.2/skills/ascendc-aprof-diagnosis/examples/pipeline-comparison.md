# 流水重叠与片上容量压力

证据状态：paper/source_review；未构建、未运行、无profiling或性能结论。

## 输入与未知

纸面输入：源码包含可定位的copy/compute/copy阶段，队列／事件存在串行顺序；多个tensor同时存活，实际架构容量和profile overlap仍未知。

## 机制比较与判别

流水串行可能留下可覆盖空洞；容量压力可能限制可用槽数。应分别画ready/free边和每阶段同时live集合，以字节核算UB/L1/L0，不把TQue深度和物理buffer数当同一参数。

num=2只说明分配形式，不能证明已有重叠。相反，复用不重叠tensor的物理地址可以减少静态容量，却可能和延长存活的大batch／多槽流水竞争。资源不合法会阻塞动作，不意味着串行机制不存在。

## Action实例与两阶段交接

C2可以在unknown下计算分支：现有预算内重排、生命周期复用后重排、预算不足保留原排程。分别记录进入条件，不提前填“容量通过”。`action.software_pipeline_stages`仍需要真实overlap_low证据；`action.reuse_disjoint_onchip_buffers`需要原容量/依赖前提。确认后由C3选择pipeline、slots或reuse方法，检查首轮／回卷／排空及最后异步消费者。

新增证据创建后继reasoning/C1/C2，不修改本纸面输入。机器记录见同名JSON；该记录不作为case_support。
