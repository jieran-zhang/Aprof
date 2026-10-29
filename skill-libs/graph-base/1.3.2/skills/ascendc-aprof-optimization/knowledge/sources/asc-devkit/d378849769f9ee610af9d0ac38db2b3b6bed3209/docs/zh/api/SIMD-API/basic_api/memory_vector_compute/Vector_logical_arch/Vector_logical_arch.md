# Vector逻辑架构<a name="ZH-CN_TOPIC_0000002573902865"></a>

## Vector逻辑架构说明

Vector计算单元专用于执行向量计算。如下图所示，高亮部分展示了Vector计算单元及其关联的存储单元。

<!-- npu="A3,910b" id1 -->
- 针对Atlas A3系列产品、Atlas A2系列产品，Vector逻辑架构如下图1所示。

  **图1** 向量计算单元架构图

  ![](../../../../figures/a2a3_npu_arch.png)

  **表1** 向量计算单元关联的存储单元

  | 存储单元 | 说明 | 
  | --- | --- |
  | Unified Buffer（UB） | AI Core内部物理存储单元，通常用于存储向量计算的输入/输出数据。 |

<!-- end id1 -->

<!-- npu="950" id2 -->
- 针对Ascend 950PR&950DT系列产品，Vector逻辑架构如下图2所示。

  **图2** 向量计算单元架构图

  ![](../../../../figures/npu_3510_hw_arch_vector.png)

  **表2** 向量计算单元关联的存储单元

  | 存储单元 | 说明 | 
  | --- | --- |
  | UB | AI Core内部物理存储单元，通常用于存储向量计算的输入/输出数据。 |
  | SIMD Register File | AI Core内部物理存储单元，在SIMD程序中，数据从UB搬运到Register进行计算，产生的中间结果可以不用传回UB，直接在寄存器计算。 |

<!-- end id2 -->

## UB介绍<a name="ZH-CN_TOPIC_0000002574022839"></a>

### UB的通用约束说明

- UB地址对齐约束，请参考通用地址对齐约束。
- UB地址重叠约束，请参考通用地址重叠约束。

### UB的内存结构与bank冲突

为了提高数据访问的效率和吞吐量，UB采用了大小相等的内存模块（bank）结构设计。当多条读写指令同时访问UB时，由于硬件资源的限制，这些指令不能同时执行，从而引发bank冲突。在这种情况下，指令需要排队等待资源，无法在一个指令周期内完成。

<!-- npu="A3,910b" id3 -->
- 针对Atlas A3系列产品、Atlas A2系列产品
  - UB的内存结构

    **图3** UB的内存结构图

    ![](../../../../figures/a2a3_ub_memory_structure.png)

    如图3所示，UB总大小为192KB，包含16个bank group（BG0 ~ BG15），每个bank group包含3个bank。每个bank大小为4KB，由128行组成，每行长度为32B。
    - **读写冲突**：读操作和写操作同时尝试访问同一个bank。
    - **写写冲突**：多个写操作同时尝试访问同一个bank group。
    - **读读冲突**：多个读操作同时尝试访问同一个bank group。

  - bank冲突优化

    可参考避免bank冲突（NPU架构版本2201）。
<!-- end id3 -->

<!-- npu="950" id4 -->
- 针对Ascend 950PR&950DT系列产品
  - UB的内存结构

    **图4** UB的内存结构图

    ![](../../../../figures/950_ub_memory_structure.png)

    如图4所示，UB总大小为256KB，包含8个bank group（BG0 ~ BG7），每个bank group包含2个bank。每个bank大小为16KB，由512行组成，每行长度为32B。
    - **读写冲突**：读操作和写操作同时尝试访问同一个bank。
    - **写写冲突**：多个写操作同时尝试访问同一个bank group。
    - **读读冲突**：两个读操作同时尝试访问同一个bank，或者两个以上读操作同时尝试访问同一个bank group。
  
  - bank冲突优化

    可参考避免bank冲突（NPU架构版本3510）。
<!-- end id4 -->

> 文档适配说明：本页已修复引用；缺失材料的链接已移除，同名补充参考不代表历史原件。来源及历史回放使用[保留的证据原文](../../../../../../../../../../../../../sources/document-originals/3ea2f2b1805ea780d7a3b675bea3288878477fcb8a8fb3b94817f5cc004d91ea.txt)。
