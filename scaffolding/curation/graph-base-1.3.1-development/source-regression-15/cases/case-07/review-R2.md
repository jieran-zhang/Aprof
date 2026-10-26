# strided_slice R2第二次静态复核

重算所有mask、shrink/new-axis/ellipsis后得到连续组2/7/10/11/13/14/16/17/18/19/20；81处边界断言验证run内source(root+k)=source(root)+k且最大地址在输入内。case16/17的size1新轴不能阻止合轴；case20 run=127，跨行有空洞，不能把整个输出当连续。

条件后继：目标DataCopyPad的字节长度/地址对齐和实际UB证据齐备后实现；先完整20case位模式oracle。若127等短段发射过多，再比较保持相同地址集的多块strided API；run1组另开增量地址方案，不从本轮无测结果推断。

修订方案：基于归一化metadata合并最长连续尾段：跳过size1轴，要求最后有效axis step=1，继续合轴条件sourceStep[d]=当前run长度。每核仍持有原64B边界输出区间，与run交集切段；每段起点只解码一次，用DataCopyPad按有效字节搬入单独UB槽并搬出同宽位模式。T∈{256,1024,4096}元素，U=2*Align32(T*itemBytes)+API_reserved≤availableUB；不补读GM、不跨不连续行空洞。run=1、负stride、未支持API保留原逐元素路径。

未执行候选、构建、native、oracle或性能计时；保留原始父本。
