# foreach_addcdiv_scalar：R1自主静态方案

目标910C/A3按包内平台映射声明dav-2201适用域，不是设备探测。20个原case完整保留。

Process明确CopyIn→Compute→CopyOut；4个TQue均num=1，2048元素tile；输入3读输出1写。

低精度Cast三输入至fp1/fp2/fp3，Div写fpOut再Muls/Add并最终Cast；不是连续宽窄往返。

host按每tensor分8*1024*1024元素chunk，每chunk一个launch；tensor间无kernel中间值或消费者链。

每个tile相同地址、相同有效count、相同dtype和算术顺序，三个输入只读且host分别分配输出；没有跨tile数学依赖。

候选比较：

software_pipeline_stages：跨tile预取释放单槽依赖，必要GM流量仍为4Ns，代价是更多raw槽及序言尾声。；状态=selected；case=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20

reuse_disjoint_onchip_buffers：将Div后的fc区用于之后Cast(a)可从四FP32 scratch降至三块，但需先延后Cast(a)并核对API alias/事件；尚未知道容量是否限制tile。；状态=deferred；case=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20

coalesce_cast：三输入各只扩位一次、输出只缩位一次；删除Cast会变更FP32除法路径，case12/13异常值不允许用scalar特化跳过算术。；状态=rejected；case=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20

选定具体方案：保留TensorList逐tensor、8Mi元素host chunk、每元素Div→Muls→Add及原Cast。核内用U∈{1024,2048,4096}、输入/输出物理槽d∈{1,2}；首轮CopyIn(0)，DeQue后允许CopyIn(1)，按队列契约交错计算与搬出，末轮drain。d=2仅用于本核tileCount≥2且8*A(U*s)+4*A(4U)*(s!=4)+R≤UB_available；单tile保留d=1。不把模板depth和物理num混为一谈。

性能待判：当前单槽循环的DMA/Vector是否已有编译调度重叠，Div是否主导，额外槽/较短tile是否增大控制成本。

合法性缺项：

constraint.capacity：缺实际可用UB及编译器/API预留R；需比较候选65536/131072B加R而非把配置示例当实值。

constraint.target_api：目标安装SDK的TQue物理num=2、depth=1交错EnQue/DeQue与尾DataCopyPad支持尚未核验。

停止比较的理由：主体数据通路、控制、复用与数值边界已分开比较；剩余问题需要目标SDK/UB和后续合法实验，不能通过继续阅读推出当前时延。
