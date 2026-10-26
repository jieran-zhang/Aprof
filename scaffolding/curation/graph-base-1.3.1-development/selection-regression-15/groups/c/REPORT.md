# autonomy-c：case-11..15

五个独立source任务已完成R1/R2，每轮decision-v2及C1 sidecar均通过冻结runtime真实校验。所有原始source逐文件hash未变。

|case|主Action|R2新增静态依据|
|---|---|---|
|11 foreach|coalesce_contiguous_transfers|逐dtype物理分配账与8M host chunk计数，将大tile容量代价和双槽替代同列|
|12 maximum|restructure_broadcast|区分FP32 GT+Select与int32 Max；加入256B/predicate/8KB/尾写，513/37/101短行预算实质调整计算路线；其它dtype保持|
|13 RoPE|vectorize_scalar_loop|BSND/BNSD trig复用距离、head=1域及20D/30D物理分配|
|14 transpose|reorder_contiguous_access|保留后缀、二维/批二维与一般perm分域；Raw位宽和局部重排成本|
|15 resize|vectorize_scalar_loop|几何与nc无关而原值依赖nc；上/下采样窗口代价，并显式登记未注册geometry意图|

每case的rounds.json是入口，引用两轮decision、C1、retrieval、expansion、实际按Action scope的P/O内部router、正文采用记录与校验回执。每case REPORT.md/R1.md/R2.md给中文解释与明确反事实纸面probe。SUMMARY.json可供汇总。

实际读取正文在consultation-r1/r2.json有包内路径/hash/lines定位、before/after及full/partial适用解释；无完整确认C2，无P_KEEP/O_KEEP，无C3实施。新增静态证据在r2-new-static-evidence.json，绑定同一父source/workload和implementation_hash=null。

装配期间修正了authority schema、not_measured性能预测不能携带静态evidence refs、comparison_basis只能引用最强替代的格式要求；均为任务记录修正，无冻结包修改或设备动作。最终十轮回执均valid。

未编译SDK、未运行设备、未改算子；R1/R2均not_measured，正确性not_tested、结构not_implemented、性能接纳not_evaluated。剩余风险是具体API/语义闭合、真实UB预算和收益尚未验证；源码次数不是指令数或速度承诺。
