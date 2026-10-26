# case-11 foreach_addcdiv_scalar

R1：先保留原owner及单槽生命周期，将2048固定tile改为容量/API允许的参数T，首选比较4096/8192；不跨host chunk或tensor边界；保持Div→Muls→Add和原Cast。

完整路径：host按TensorList成员及8M元素chunk逐次启动；每chunk按核连续分块，T=2048；每tile三输入DMA、Div/Muls/Add及输出DMA，窄dtype额外三次入FP32和一次回写Cast；无GM中间张量。

原工作：4*N*s bytes GM，3*N arithmetic elements；L=sum_chunks,sum_cores ceil(Nc/2048) tiles，4*L DMA；窄dtype 4*N cast elements。

减少：4*(L2048-LT) DMA发射及相同数量级tile控制，LT=sum ceil(Nc/T)，比较T=4096或8192；GM必要字节不变

代价：单槽 U(T)=4*A(T*s)+[s=2]*4*A(4*T)+Bfixed；T=8192时FP32数据区131072B、窄dtype196608B，仍须加保留并满足Uavailable

最强替代：双槽流水可隐藏部分搬运但不减少DMA次数，增加4*A(T*s)字节、预取/排空与事件；在小tile多轮且各阶段接近时可优于仅增T。

残余：原3N算术、窄dtype4N Cast、4Ns必要GM、host chunk启动和单槽串行仍存在。

R2新增静态证据及复评：新增按源码物理分配计算：T=2048的FP32数据区32768B、窄dtype49152B；T=8192分别131072B和196608B。double-buffer T=2048分别65536B/65536B。窄dtype增T四倍可能挤掉流水空间，因此R2保留合并意图但将T=4096优先作条件候选，8192仅资源公式闭合后再比较；必要Cast不删除。

跨形态/代价反转纸面probe：反事实非实测：若Uavailable-Bfixed位于[98304,196608)B，窄dtype单槽T=4096可容纳而8192不可，双槽2048可容纳。若搬运/计算近均衡且长循环，流水可反转优先级；若传输发射主导且compute短，单槽4096仍合理。

Problem：problem.tiny_transfer_setup_amplification；替代problem.pipeline_serialization。Action：action.coalesce_contiguous_transfers；替代action.software_pipeline_stages。

实际读取P/O正文：
- skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md sha256:0a602958e66a719ea6d7a959a6d447ac684f2ef53a22fc1fe3dc838bde06edd4 lines:83-138。full structural：当前三输入同shape独立元素和连续owner匹配完整骨架；SDK与容量仍条件化。影响：先保留原owner及单槽生命周期，将2048固定tile改为容量/API允许的参数T，首选比较4096/8192；不跨host chunk或tensor边界；保持Div→Muls→Add和原Cast。 采用正文约束：单槽 U(T)=4*A(T*s)+[s=2]*4*A(4*T)+Bfixed；T=8192时FP32数据区131072B、窄dtype196608B，仍须加保留并满足Uavailable；替代边界：双槽流水可隐藏部分搬运但不减少DMA次数，增加4*A(T*s)字节、预取/排空与事件；在小tile多轮且各阶段接近时可优于仅增T。
- skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/coalesce.md sha256:ae97f3a0b11ed80146830606cd1cdd15eff6088336d43c639611ac5af7b4d96c lines:69-108。partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。影响：先保留原owner及单槽生命周期，将2048固定tile改为容量/API允许的参数T，首选比较4096/8192；不跨host chunk或tensor边界；保持Div→Muls→Add和原Cast。 采用正文约束：单槽 U(T)=4*A(T*s)+[s=2]*4*A(4*T)+Bfixed；T=8192时FP32数据区131072B、窄dtype196608B，仍须加保留并满足Uavailable；替代边界：双槽流水可隐藏部分搬运但不减少DMA次数，增加4*A(T*s)字节、预取/排空与事件；在小tile多轮且各阶段接近时可优于仅增T。
- skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md sha256:44a68a5b982eb4107ad17d4a133a9b4786646609ef41484c0dd68e7533124b01 lines:89-144。partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。影响：先保留原owner及单槽生命周期，将2048固定tile改为容量/API允许的参数T，首选比较4096/8192；不跨host chunk或tensor边界；保持Div→Muls→Add和原Cast。 采用正文约束：单槽 U(T)=4*A(T*s)+[s=2]*4*A(4*T)+Bfixed；T=8192时FP32数据区131072B、窄dtype196608B，仍须加保留并满足Uavailable；替代边界：双槽流水可隐藏部分搬运但不减少DMA次数，增加4*A(T*s)字节、预取/排空与事件；在小tile多轮且各阶段接近时可优于仅增T。

完整轻目录已检索，按源码展开Problem；额外正文反证：foreach必要Cast不可删除，Maximum已有Vector域不重复计收益，RoPE现有Cast不是算术Vector化，Transpose不能忽略局部重排，Resize派生几何复用不等于原输入驻留。停止比较因主要源码工作与最强替代已覆盖；性能主次与具体API/容量待后续授权实验。

未改算子、未编译SDK、未运行设备/正确性/计时；R1/R2均not_measured，性能接纳not_evaluated。P/O为真实内部router咨询，没有完整已确认C2，因此不伪造P_KEEP/C3实施。容量仅公式，actual cores/SDK/UB未知。


逐文档采用核对（此项为最终记录，替代前文合并描述）：
- skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md lines:83-138 sha256:0a602958e66a719ea6d7a959a6d447ac684f2ef53a22fc1fe3dc838bde06edd4；确认按连续输出owner分区和valid长度，tile容量必须计所有实际分配；单槽/双槽只是假设。foreach完整结构适用；Maximum只覆盖同形；RoPE伴随partner读不满足逐元素同下标前提，仅采用owner/容量原则。 full structural：当前三输入同shape独立元素和连续owner匹配完整骨架；SDK与容量仍条件化。
- skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/coalesce.md lines:69-108 sha256:ae97f3a0b11ed80146830606cd1cdd15eff6088336d43c639611ac5af7b4d96c；选择保持原owner、有效尾长和同dtype连续邻段，只增tile T减少4L接口数；原数值顺序和queue完成边保留，跨tensor/chunk不能合并。容量上升与失去双槽机会共同进入R2。 partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。
- skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md lines:89-144 sha256:44a68a5b982eb4107ad17d4a133a9b4786646609ef41484c0dd68e7533124b01；确认num=2不是重叠证明、物理槽数与queue depth不同；替代方案需要输入ready/free与输出ready/free四类完成边和0/1/2 tile排空。因保持scratch单份，不能擅自并发写FP32临时。 partial：仅采用容量、有效域、所有权/数值边界原则；未声称整套模板API已验证。

最终审核：同范围谓词已去重，并从C1真实实例scope调用routing_context和P/O route_candidates；action绑定咨询与全部正文采用见consultation-r1/r2.json。没有P_KEEP或正式C2/C3。R1/R2机器回执见validation-r1/r2.json。
