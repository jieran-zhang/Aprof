# 小搬运发射成本与带宽饱和

证据状态：paper/source_review；未构建、未运行、无profiling或性能结论。

## 输入与未知

纸面输入：源码有按小行循环执行的搬运，目标输出区域和有效长度可定位；没有设备计数器、有效带宽或发射耗时。此处不是一次实测记录。

## 机制比较与判别

前者预测：相同有效字节下减少调用次数可能减少setup成本；后者预测：即使调用更粗，若HBM字节不变且已饱和，收益仍受限。连续小搬运的源码事实不能区分这两个机制；调用数、有效字节／调用、实际持续带宽必须分别说明范围。

反证不是“没有计数器”：缺profile是unknown。如果同范围真实证据显示持续带宽已饱和，可以削弱纯setup解释；仍需检查是否存在其他阶段共存。`symptom.profile.mte_setup_dominated`是复合观察，不能只凭MTE占比填写true。

## Action实例与两阶段交接

可形成`action.coalesce_contiguous_transfers`待证据实例，目标绑定具体input或output行段。C2比较现有tile内连续段、规则stride搬运与重切任务；只有原所有权和自由度允许才P_KEEP。C3需原动作的profile前提、连续性／stride与有效尾条件全部满足后选coalesce或strided-pad。不得把同字节更少调用宣称减少HBM流量。

新增证据创建后继reasoning/C1/C2，不修改本纸面输入。机器记录见同名JSON；该记录不作为case_support。
