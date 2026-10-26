# 融合与真实片上驻留

证据状态：paper/source_review；未构建、未运行、无profiling或性能结论。

## 输入与未知

纸面输入：tensor T从生产者P写GM，由消费者C读回；两阶段之间的布局、元素范围和生命周期可审读，但中间GM流量放大及可用容量尚无实测证据。

## 机制比较与判别

融合边界、数据通路、流水重叠是三个不同问题。Vector链在合法region内可以复用片上数据；Cube–Vector实现也可能仍经GM交接。一个kernel不自动消除GM写读，950专用通路也不自动支持910C。

比较是否同一owner、是否需全局归约或重排、所有消费者是否在region内、数值边界是否可保留。若消费者必须跨owner读取，简单UB驻留可能不合法；这削弱当前驻留方案，不必否认所有融合方案。

## Action实例与两阶段交接

实例绑定T、P、C和当前GM边。既定region已授权且预算有效可P_KEEP；改变region、owner、通路或跨阶段协议需C2。C2只选计划并给O提示；C3再选vector_chain_residency、reuse或对应交接方法。`keep_intermediate_onchip`的gm_traffic_amplified原前提没有profile时保持unknown，不拿GM交接配方冒充片上驻留。

新增证据创建后继reasoning/C1/C2，不修改本纸面输入。机器记录见同名JSON；该记录不作为case_support。
