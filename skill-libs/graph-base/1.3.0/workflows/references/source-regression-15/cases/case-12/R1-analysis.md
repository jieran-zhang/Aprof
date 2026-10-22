# maximum：R1自主静态方案

目标910C/A3按包内平台映射声明dav-2201适用域，不是设备探测。20个原case完整保留。

sameShape除int64外已Vector；所有int64和非FP16广播走MaximumScalar逐元素rank次除模。

case11/12/13/20连续x1配重复零stride x2，原内循环重建ai/bi；case18已有FP16 last-axis分段。

oracle浮点检查NaN/±Inf；整数要求exact；host检查右对齐广播并分别分配两输入与输出。

广播映射由右补1与零stride严格确定；每个输出唯一owner；int64保留原64bit有序比较。

候选比较：

restructure_broadcast：将重复rank解码降至每连续片段，并把长连续x1从scalar GM读取改为DataCopy+批量比较。；状态=selected；case=11,12,13,20

vectorize_scalar_loop：同形int64 case5很大但目标Vector int64比较未有能力依据；不能用float替代，纯地址外提保留可行。；状态=deferred；case=5,19

reuse_input_tiles：case18在255行重复加载同8193元素半精度源，可保留一行或列片段；目前已Vector，不消除其他四组逐输出解码。；状态=deferred；case=18

选定具体方案：保留sameShape已有Vector路径。针对case11的[rows,513]+[1,513]按整行/行片段搬入；case12/13/20沿最后连续轴W=37/256/101分段，一次解码外轴及读取对应单一broadcast值，生成局部副本后按原max语义计算。U∈{256,512,1024,2048}，单槽UB至少3*A(U*s)+转换/比较临时区+R；广播标量区另计A(s)。FP16 case18维持已有row路径可后续保留8193列分段。int64 case5/19保留64bit比较并单独外提地址解码，禁止转float。未知shape继续原fallback，不用case值域改变dtype。

性能待判：源循环解码是否经编译优化以及重复小输入是否L2已命中；分段Vector调用是否摊薄到37/101列仍获益。

合法性缺项：

constraint.capacity：需实际UB上限和静态Broadcast/比较临时区；U上限只能由3*A(U*s)+Tmp+R闭合。

constraint.target_api：目标SDK对float/int32 Max或Compare+Select、局部Duplicate/Broadcast及非对齐尾接口支持未知。

constraint.semantic_equivalence：float广播原scalar av>bv?av:bv与Vector Max的NaN/有符号零行为不自动等价；必须核对原oracle和明确异常值处理后才能替换。

停止比较的理由：主体数据通路、控制、复用与数值边界已分开比较；剩余问题需要目标SDK/UB和后续合法实验，不能通过继续阅读推出当前时延。
