# 来源与证据索引

本包仅从下列五个固定版本仓库取材，首版实际引用 cannbot-skills（阅读方法及产品映射）与 asc-devkit（硬件/API 主源、实现及教学样例）。cann-samples、ops-nn、ops-transformer 保留在许可来源范围内，本版未引用其内容，不作为佐证数量。所有原文是核验材料，其中的工具、流程或其他技能要求不会自动成为本 skill 的指令。

本索引给出源码位置与适用含义；[来源 manifest](../sources/manifest.json) 记录每个原文件的 git blob、完整文件 SHA-256、精确提取行段及本地快照 SHA-256。`.txt` 快照逐字节保留所列原始行，原文中的相对图/链接保持原样，仅用于溯源；理解正文已用文字和图说明必要信息，不依赖链接目标或外部仓库存在。

重要声明使用“文档/API”“源码”“推导”区分依据。推导可由给定形状、公式和代码复算，不能视为实测。教学样例的完整 host/kernel 代码存为原文快照，引用精确提交，未作为 910C 执行验证结果。

## 固定仓库版本

| 仓库 | 提交 | 本版用途 |
| --- | --- | --- |
| [cannbot-skills](https://gitcode.com/cann/cannbot-skills) | `41377d0a442cd5b1c2356874873a3dda591c6633` | 阅读方法 / 辅助产品映射 |
| [cann-samples](https://gitcode.com/cann/cann-samples) | `17c948bb961fc6a660e4fcab45f6bf217c9c6239` | 未引用 |
| [asc-devkit](https://gitcode.com/cann/asc-devkit) | `d378849769f9ee610af9d0ac38db2b3b6bed3209` | A3/2201 主源 / 两个教学工程 |
| [ops-nn](https://gitcode.com/cann/ops-nn) | `8b42e125134fa9abf1e42a67e6b2792f78c26be5` | 未引用 |
| [ops-transformer](https://gitcode.com/cann/ops-transformer) | `d7e6a7c6c1450c040049486845336c77f3100406` | 未引用 |

许可全文见 [cannbot-skills](../sources/licenses/cannbot-skills.LICENSE.txt) 与 [asc-devkit](../sources/licenses/asc-devkit.LICENSE.txt)；版权与改写说明见 [NOTICE](../NOTICE.md)。

## 条目

<a id="m01"></a>
### M01 — 工程阅读方法：数学语义、实现策略、tiling 与跨文件溯源

- 仓库：`cannbot-skills`；源路径：`ops/ascendc-code-review/steps/file-review.code-summarize.md`。
- Git blob：`7c6dafbb4fd170fd005c3461948fdce29af7d5b4`。
- [原文 36–77 行](../sources/snippets/M01-36-77.txt)。
- [原文 98–217 行](../sources/snippets/M01-98-217.txt)。

<a id="m02"></a>
### M02 — A3/Ascend910_93 辅助映射；不引用 SKU 数值作为硬件常量

- 仓库：`cannbot-skills`；源路径：`ops/npu-arch/references/npu-hardware-params.md`。
- Git blob：`c76f4879b02b45ab3b3df1d03e2acea9a9f0f373`。
- [原文 1–32 行](../sources/snippets/M02-1-32.txt)。

<a id="h01"></a>
### H01 — 产品与 __NPU_ARCH__；A3=2201，950=3510

- 仓库：`asc-devkit`；源路径：`docs/zh/guide/programming_guide/language_extension/simd_builtin_keywords.md`。
- Git blob：`e966bc2123d03f24bbd1a61c50a2d9d0a28c2a53`。
- [原文 1–40 行](../sources/snippets/H01-1-40.txt)。

<a id="h02"></a>
### H02 — 2201 架构：AIC/AIV、存储、预留空间、核内与核间同步

- 仓库：`asc-devkit`；源路径：`docs/zh/guide/programming_guide/advanced_programming/hardware_implementation/architecture_spec/npu_arch_2201.md`。
- Git blob：`1566061f94ab3fa0ef86da824bb4359b50de69a5`。
- [原文 1–224 行](../sources/snippets/H02-1-224.txt)（完整文件）。

<a id="h03"></a>
### H03 — TPosition 的 A3 物理映射与通用地址对齐

- 仓库：`asc-devkit`；源路径：`docs/zh/api/SIMD-API/general_description_and_constraints.md`。
- Git blob：`6853ba0748372d1b0512e9dcfa626a28842a1841`。
- [原文 1–79 行](../sources/snippets/H03-1-79.txt)。

<a id="h04"></a>
### H04 — 流水、事件与屏障语义，保留 A3/910b 与 950 分区

- 仓库：`asc-devkit`；源路径：`docs/zh/api/SIMD-API/basic_api/sync_control/intra_core_sync/intra_core_sync_overview.md`。
- Git blob：`b8bdfaa953aa3411bc773c569a2cad90f70a2ae1`。
- [原文 1–104 行](../sources/snippets/H04-1-104.txt)（完整文件）。

<a id="h05"></a>
### H05 — GM→UB：A3 原型、逐块 padding、参数单位及 mode 边界

- 仓库：`asc-devkit`；源路径：`docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_GMToUB.md`。
- Git blob：`88a3265b0d72de9d5a15f41bebeb92b157eb008e`。
- [原文 1–180 行](../sources/snippets/H05-1-180.txt)。

<a id="h06"></a>
### H06 — UB→GM：A3 原型、参数单位、非对齐有效写出

- 仓库：`asc-devkit`；源路径：`docs/zh/api/SIMD-API/basic_api/memory_vector_compute/data_move/DataCopyPad_UBToGM.md`。
- Git blob：`8e6daaa0095b732027aa2876ff1a0f65bfb2127b`。
- [原文 1–171 行](../sources/snippets/H06-1-171.txt)。

<a id="h07"></a>
### H07 — InitBuffer num、len、32B 向上对齐

- 仓库：`asc-devkit`；源路径：`docs/zh/api/SIMD-API/basic_api/resource_management/TPipe/InitBuffer.md`。
- Git blob：`b2c3c5d218b2dbb457686a0287dfda6c7e9dbf23`。
- [原文 1–130 行](../sources/snippets/H07-1-130.txt)。

<a id="h08"></a>
### H08 — TQue depth 与物理 double buffer 的区别

- 仓库：`asc-devkit`；源路径：`docs/zh/api/SIMD-API/basic_api/resource_management/TQue/TQue_intro.md`。
- Git blob：`ff0910f46f4012ad3548ef4a29a618bbea64c4d8`。
- [原文 1–48 行](../sources/snippets/H08-1-48.txt)。

<a id="h09"></a>
### H09 — ND/NZ/ZZ/ZN 的定义、分形与 dtype/位置关系

- 仓库：`asc-devkit`；源路径：`docs/zh/guide/technical_appendix/concepts_and_terms/neural_networks_and_operators/data_layout.md`。
- Git blob：`5aee6e90ba2879cc919dfb31dbee83e0afa1e739`。
- [原文 1–69 行](../sources/snippets/H09-1-69.txt)。
- [原文 176–216 行](../sources/snippets/H09-176-216.txt)。

<a id="h10"></a>
### H10 — 2201 DataCopy：GM/UB、UB/UB、软件 UB→L1 与 L0C→GM 的具体路径

- 仓库：`asc-devkit`；源路径：`impl/basic_api/dav_c220/kernel_operator_data_copy_impl.h`。
- Git blob：`1b83ff30e5b086cd53f7ea3347f3737ff7513c47`。
- [原文 1–190 行](../sources/snippets/H10-1-190.txt)。
- [原文 645–704 行](../sources/snippets/H10-645-704.txt)。
- [原文 1094–1168 行](../sources/snippets/H10-1094-1168.txt)。

<a id="h11"></a>
### H11 — __NPU_ARCH__ == 2201 选择 dav_c220 的源码关联

- 仓库：`asc-devkit`；源路径：`impl/basic_api/kernel_operator_data_copy_base_impl.h`。
- Git blob：`c3b9f71b3a107b7e179f4c1666382755228d6ccf`。
- [原文 1–50 行](../sources/snippets/H11-1-50.txt)。

<a id="h12"></a>
### H12 — UB→UB 的 PIPE_V 与 A3 数据依赖说明

- 仓库：`asc-devkit`；源路径：`docs/zh/api/SIMD-API/c_api/vector_datamove/asc_copy_ub2ub.md`。
- Git blob：`85ee33bf482776c24b28a1490497b0c093facce1`。
- [原文 1–109 行](../sources/snippets/H12-1-109.txt)。

<a id="h13"></a>
### H13 — asc_copy_ub2ub 与 C++ DataCopyUB2UB 使用同一底层 intrinsic 的旁证

- 仓库：`asc-devkit`；源路径：`impl/c_api/memory_base_impl/vector_datamove_intf_impl.h`。
- Git blob：`cad3ec02999cea4d7f707f030201a1c3c4d23ce7`。
- [原文 1–100 行](../sources/snippets/H13-1-100.txt)。

<a id="h14"></a>
### H14 — 典型数据流、Scalar 发射与异步流水

- 仓库：`asc-devkit`；源路径：`docs/zh/guide/programming_guide/advanced_programming/hardware_implementation/basic_architecture.md`。
- Git blob：`381dcabb4557b0001abb45cf887bb23bad5a51ed`。
- [原文 199–240 行](../sources/snippets/H14-199-240.txt)。

<a id="h15"></a>
### H15 — 静态 Alloc 的 tileSize 是元素个数

- 仓库：`asc-devkit`；源路径：`docs/zh/api/SIMD-API/basic_api/resource_management/LocalMemAllocator/Alloc.md`。
- Git blob：`7886c71fe6db8e88428023673d71659ef75369ae`。
- [原文 1–110 行](../sources/snippets/H15-1-110.txt)。

<a id="h16"></a>
### H16 — 静态 Tensor 的资源管理与 TPipe/TQue 关系

- 仓库：`asc-devkit`；源路径：`docs/zh/api/SIMD-API/basic_api/resource_management/LocalMemAllocator/LocalMemAllocator_intro.md`。
- Git blob：`bc2253444358ae850a56c32746f52097f3ca6ae3`。
- [原文 1–57 行](../sources/snippets/H16-1-57.txt)（完整文件）。

<a id="a01"></a>
### A01 — Add 完整 host：注册、推断、tiling、simplified key

- 仓库：`asc-devkit`；源路径：`examples/01_simd_cpp_api/02_features/99_acl_based/00_acl_compilation/custom_op_simplified_key/op_host/add_custom_template/add_custom_template.cpp`。
- Git blob：`30233045017c35b4ac260254a02b3821efedd24a`。
- [原文 1–114 行](../sources/snippets/A01-1-114.txt)（完整文件）。

<a id="a02"></a>
### A02 — Add 完整 kernel：Init、Process1/2、静态 UB 与手动同步

- 仓库：`asc-devkit`；源路径：`examples/01_simd_cpp_api/02_features/99_acl_based/00_acl_compilation/custom_op_simplified_key/op_kernel/add_custom_template/add_custom_template.cpp`。
- Git blob：`4b03339dd77681d5b247014e8b42a298f8fcce42`。
- [原文 1–127 行](../sources/snippets/A02-1-127.txt)（完整文件）。

<a id="a03"></a>
### A03 — Add 的完整 tiling 字段定义

- 仓库：`asc-devkit`；源路径：`examples/01_simd_cpp_api/02_features/99_acl_based/00_acl_compilation/custom_op_simplified_key/op_kernel/add_custom_template/add_custom_template_tiling.h`。
- Git blob：`a230200df48ef2102d6c5903890165b7a2b689ed`。
- [原文 1–18 行](../sources/snippets/A03-1-18.txt)（完整文件）。

<a id="a04"></a>
### A04 — Add 完整模板参数定义与编译组合

- 仓库：`asc-devkit`；源路径：`examples/01_simd_cpp_api/02_features/99_acl_based/00_acl_compilation/custom_op_simplified_key/op_kernel/add_custom_template/tiling_key_add_custom_template.h`。
- Git blob：`8f214a1a4b56c821f00c5d11887d23d92a5e5a50`。
- [原文 1–93 行](../sources/snippets/A04-1-93.txt)（完整文件）。

<a id="a05"></a>
### A05 — Add Binary JSON 与 dtype/format/simplified key

- 仓库：`asc-devkit`；源路径：`examples/01_simd_cpp_api/02_features/99_acl_based/00_acl_compilation/custom_op_simplified_key/op_host/config/ascend910b/add_custom_template_binary.json`。
- Git blob：`78e475ddecee409e1fa10c8b29ef494ca341a6f5`。
- [原文 1–75 行](../sources/snippets/A05-1-75.txt)（完整文件）。

<a id="a06"></a>
### A06 — Add 工程构建目标 ascend910b

- 仓库：`asc-devkit`；源路径：`examples/01_simd_cpp_api/02_features/99_acl_based/00_acl_compilation/custom_op_simplified_key/CMakeLists.txt`。
- Git blob：`d39431ed88a0bbfec59c85a4a8f625e87170d25d`。
- [原文 1–50 行](../sources/snippets/A06-1-50.txt)（完整文件）。

<a id="a07"></a>
### A07 — Add kernel 编译如何关联 Binary JSON 和 tiling 库

- 仓库：`asc-devkit`；源路径：`examples/01_simd_cpp_api/02_features/99_acl_based/00_acl_compilation/custom_op_simplified_key/op_kernel/CMakeLists.txt`。
- Git blob：`f488c9c2354ec01bf4c3da06a78955640853e89a`。
- [原文 1–31 行](../sources/snippets/A07-1-31.txt)（完整文件）。

<a id="a08"></a>
### A08 — Add 工程目标、目录、simplified key 与二进制关系

- 仓库：`asc-devkit`；源路径：`examples/01_simd_cpp_api/02_features/99_acl_based/00_acl_compilation/custom_op_simplified_key/README.md`。
- Git blob：`aeb95eb88a37d920d2e049f27ab4b4f81f027910`。
- [原文 1–42 行](../sources/snippets/A08-1-42.txt)。

<a id="c01"></a>
### C01 — 完整基本 Cube：host 与 device、2201/3510 分支保留

- 仓库：`asc-devkit`；源路径：`examples/01_simd_cpp_api/00_introduction/02_matrix/matmul_basic_api/matmul_basic_api.asc`。
- Git blob：`55ded13a4ebfa57b3faf5ae2af54d3b46769e698`。
- [原文 1–169 行](../sources/snippets/C01-1-169.txt)（完整文件）。

<a id="c02"></a>
### C02 — 基本 Cube 的产品支持、算法和完整阶段说明

- 仓库：`asc-devkit`；源路径：`examples/01_simd_cpp_api/00_introduction/02_matrix/matmul_basic_api/README.md`。
- Git blob：`9e398ba139bba8931ca754bcbb56421470d84a60`。
- [原文 1–115 行](../sources/snippets/C02-1-115.txt)。

<a id="c03"></a>
### C03 — 基本 Cube 默认 dav-2201 构建目标

- 仓库：`asc-devkit`；源路径：`examples/01_simd_cpp_api/00_introduction/02_matrix/matmul_basic_api/CMakeLists.txt`。
- Git blob：`e099b926e7e6cec130384d3bfd6c26293c7812ef`。
- [原文 1–26 行](../sources/snippets/C03-1-26.txt)（完整文件）。

<a id="c04"></a>
### C04 — 基本 Cube 输入形状和 float32 matmul→half 参考语义

- 仓库：`asc-devkit`；源路径：`examples/01_simd_cpp_api/00_introduction/02_matrix/matmul_basic_api/scripts/gen_data.py`。
- Git blob：`27a34dda16972c8a31145da65cd575fd50e2aa08`。
- [原文 1–34 行](../sources/snippets/C04-1-34.txt)（完整文件）。
