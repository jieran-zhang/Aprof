# 3510 执行选择：RegBase 与 SIMT

只有架构档案确认支持且已安装 SDK 兼容时启用。NpuArch 3510 表示 ISA；产品名或另一 SDK 的头文件不证明当前二进制支持该 API。

RegBase 在 VF 内用寄存器保存 Vector 中间值，减少多操作链的 UB 往返。保留显式 load/store、mask、dtype 转换和 Scalar/VF 调用限制。检查生成代码与资源：存活寄存器过多或融合过大可能溢出、降低吞吐；短单操作链未必获益。`RegTensor`、mask、VF 准确 API 以已安装头文件为准。

SIMT 适用于非规则索引/控制与受支持 Scalar 操作，不自动替代批量 SIMD。lane 分组应合并 GM 访问并减少分歧；编译期 launch bound 与实际线程一致，检查寄存器/栈。混合 SIMD/SIMT 显式同步，并核算共享 UB 所有权。

SIMD 可见 UB 不全可供 SIMT：计入 DCache 与编译器/系统保留，只扣一次，并记录平台查询是否已扣除。官方 950 示例为 256 KiB 物理 UB 减 8 KiB 系统及至少 32 KiB DCache；以当前编译器/平台预算为准，不推广成未来 SKU 常量。

3510 的 UB→L1、L1→UB、L0C→UB 可避免 GM 中转。基础 UB→L1 硬件路径可能需要 `ENABLE_CV_COMM_VIA_SSBUF`，未启用时 API 可能走软件中转；归因流量减少前核验真实 flag 与 trace。旧 GM→L0A/B、L1→GM 直达路径不可直接迁移。按版本迁移指南验证精度，包括目标/API/编译设置影响的次正规数。

来源：[官方新特性](https://asc.gitcode.com/guide/cross_gen_migration_guide/instructions_for_new_features/3510_new_features.html)、[迁移变化](https://asc.gitcode.com/guide/cross_gen_migration_guide/3510_arch_migration/2201_to_3510_arch_changes.html)、[SIMT 性能示例](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/920beta1/programug/Ascendcopdevg/docs/zh/guide/%E7%AE%97%E5%AD%90%E5%AE%9E%E8%B7%B5%E5%8F%82%E8%80%83/%E4%BC%98%E7%A7%80%E5%AE%9E%E8%B7%B5/MC-%E7%AE%97%E5%AD%90%E6%80%A7%E8%83%BD%E8%B0%83%E4%BC%98%E6%A1%88%E4%BE%8B.md)。来源提供指导，不是 AProf 候选实测证据。
