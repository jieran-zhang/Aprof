# resize_bilinear：R1自主静态方案

目标910C/A3按包内平台映射声明dav-2201适用域，不是设备探测。20个原case完整保留。

ResizeOne每输出计算linear%outputSpatial、nc、oh/ow和两次ResizeCoord，四个GM标量读取，逐输出FP32加权。

FP16/BF16只把最终1024个结果Cast并DataCopy；输入转换为手写bit解码，FP32结果直接GM逐元素写。

case18/20的scale_factor在gen_data转成size；oracle F.interpolate(size=resolved_output_size)，并要求NaN/Inf mask一致。

ResizeCoord对每个输出列给出相邻w0/w1，scale<1时邻接输出可复用同源索引，scale=2时pair分离；原四点值只读。

ResizeCoord只由shape/align/out坐标决定，无数据相关地址；输入只读、输出唯一owner，无归约；clamp后两源点均在原输入域。

候选比较：

vectorize_scalar_loop：把逐输出输入解码和插值运算移到UB/Vector，地址按连续输出row分段，直接减少主体Scalar数据处理。；状态=selected；case=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20

hoist_invariant_control：每row只算ih/h0/h1/dh，宽坐标按列计算或缓存可减少重复坐标，但仍4个GM标量读及输入解码。；状态=deferred；case=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20

reuse_input_tiles：上采样同源行/列强复用；整2倍下采样邻居不重叠，统一驻留整源行可能多搬无用字节。；状态=deferred；case=4,5,7,13,14,18,19,20

选定具体方案：固定(nc,oh)后按Wtile∈{64,128,256}输出列分片；用原FP32 ResizeCoord直接算每个ow的w0/w1/dw，禁止累加scale递推。读入所需两源行的有界区间，按索引从UB取a/b/c/d，再批量执行原a*ah*aw+b*ah*dw+c*dh*aw+d*dh*dw的乘加顺序和最终Cast，不启FMA。强下采样若连续源span大于4*Wtile则用保守索引fallback或仅搬稀疏需要点；上采样保留两源行窗口。容量2*A(span*s)+至少A(7*4*Wtile)+输出raw+索引表+Tmp+reserve≤UB。所有20case分组执行，输出连续片归单核。

性能待判：Vector与UB Gather是否摊薄索引准备成本、强下采样span带来额外字节是否抵消Scalar指令减少。

合法性缺项：

constraint.capacity：连续源span随缩放比变化，实际UB及Gather临时区未知，需逐tile而非只按Wtile预算。

constraint.target_api：目标SDK的UB Gather/index单位、half/bf16输入Cast、count乘加及特殊值行为未核验。

constraint.numeric_order：原四项FP32累加顺序与源手工解码特殊值必须保留，Vector Cast/融合对NaN/Inf和bf16 round的等价需要核验。

停止比较的理由：主体数据通路、控制、复用与数值边界已分开比较；剩余问题需要目标SDK/UB和后续合法实验，不能通过继续阅读推出当前时延。

完整语义条件修正：ResizeCoord索引域和四项插值表达式可由源码恢复，但手写half/BF16解码的次正规数/NaN处理与目标Cast、Vector乘加舍入/融合、正负零和Inf传播的全域等价尚未核验。完整constraint.semantic_equivalence保持unknown，不由clamp/地址证明推成true。 数学映射另记为source.element_mapping_equivalence=true；Vector方案继续作为条件方案。
