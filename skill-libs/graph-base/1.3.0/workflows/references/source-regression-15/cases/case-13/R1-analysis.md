# apply_rotary_pos_emb：R1自主静态方案

目标910C/A3按包内平台映射声明dav-2201适用域，不是设备探测。20个原case完整保留。

Row将q/k/cos/sin搬入UB后，for(d<D)逐d GetValue多次并SetValue两输出，q/k分别先两乘再加。

layout0同seq的连续N个head复用trig；layout1相邻row是seq变化，cosBatched属于host参数。

原20case由gen_data生成cos_shape=[S,D/2]，全部cosBatched=false；kernel同时支持batched，但不能把该能力当本矩阵case。

Row在MTE2、Cast后、Scalar SetValue后和输出Cast后调用PIPE_ALL，必须保持原生产消费完成边。

两个输出每一维只读本行q/k及同一trig，不是归约；half mode partner=d±H，独立输出在原owner内；输入输出host分开分配。

候选比较：

vectorize_scalar_loop：half mode的partner是连续半区，逐元素volatile标量乘加可表达为逐半区Vector，仍保留运算边界。；状态=selected；case=1,2,3,4,7,8,9,11,13,14,15,16,18,19

reuse_input_tiles：layout0且N>1同seq重复读取cos/sin，复用可省trig读但不消除大部分逐元素算术；layout1需改任务顺序。；状态=deferred；case=1,2,3,5,7,8,10,11,14,16,18,20

narrow_sync_scope：多次PIPE_ALL可能过宽，但当前V cast→Scalar GetValue与Scalar SetValue→V cast均有跨流水边，不能直接删。；状态=deferred；case=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20

选定具体方案：先对half rotary mode按H=D/2两个连续半区使用FP32 Mul/Mul/Add，负半保留sign乘法或经数值审查的Neg，不用FMA；q/k各两半，输出最终Cast保持half CAST_NONE、bf16 CAST_ROUND。按原row owner处理，行批R∈{1,2,4,8}，原5D个FP32元素和低精度5D个raw元素，加双乘积scratch最多4D float：UB≤A(36RD)+I16*A(10RD)+Tmp+reserve。interleaved保持原路径，待SDK确认去交错/重排索引后独立候选。全部20case原路径覆盖。

性能待判：改Vector后是否主要受每row短DMA/同步限制；H=32/64的Vector发射数相对Scalar节省是否抵消新增scratch。

合法性缺项：

constraint.capacity：实际UB与Mul临时区/保留未知；R=1..8须按36RD+低精度10RD+Tmp+reserve逐组预算。

constraint.target_api：目标SDK Mul/Muls/Add count以及alias、尾长度、完成边支持未验证。

constraint.numeric_order：Vector逐步舍入与原volatile float乘加及bf16 CAST_ROUND须核对；不允许FMA融合或改变特殊值规则。

停止比较的理由：主体数据通路、控制、复用与数值边界已分开比较；剩余问题需要目标SDK/UB和后续合法实验，不能通过继续阅读推出当前时延。

完整语义条件修正：half-mode partner/row映射和目标算术表达式已经静态证明，但目标Vector Mul/Muls/Add是否保留原volatile FP32逐步舍入、正负零、NaN/Inf传播，以及half CAST_NONE和BF16 CAST_ROUND，尚无完整API/编译语义依据。constraint.semantic_equivalence包含这些条件，故保持unknown；不能用数学映射代替全域等价。 数学映射另记为source.element_mapping_equivalence=true；Vector方案继续作为条件方案。
