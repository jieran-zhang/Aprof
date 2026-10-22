# 平台身份、资源与来源

| 产品族 | ISA | 规划影响 |
| --- | --- | --- |
| 910B / Atlas A2 | DAV_2201 | Membase Vector；按可见资源分别规划 AIC/AIV |
| 910C / Atlas A3 | DAV_2201 | 同 ISA，保留实际 Ascend910_93xx 与 device/die/topology；不假定资源相等或翻倍 |
| 950 PR/DT | DAV_3510 | RegBase、SIMT/混合与新 DMA/CV 路径改变成本与实现选择，需 SDK/API 支持 |

官方 [GetCurNpuArch](https://asc.gitcode.com/api/Utils-API/platform_info/PlatformAscendC/GetCurNpuArch.html) 将 A2/A3 映射为 2201、950 PR/DT 映射为 3510。[GetSocVersion](https://asc.gitcode.com/api/Utils-API/platform_info/PlatformAscendC/GetSocVersion.html) 说明 A2/A3 共用枚举，建议 `aclrtGetSocName()` 区分。可保留 910C 产品标签，但准确 SKU 必须来自探测；未知市场别名不能覆盖观测 ISA。

## 获取实际值

Host Tiling 使用 `PlatformAscendC(context->GetPlatformInfo())`；直调在选定并初始化设备后可用 `PlatformAscendCManager::GetInstance()`，检查 null 与目标不匹配。查询 `GetCurNpuArch`、`GetCoreNumAic`、`GetCoreNumAiv` 和各内存层级 `GetCoreMemSize`。声明位于所选 SDK 的 `asc/include/utils/tiling/platform/platform_ascendc.h` 与 `include/platform/soc_spec.h`，目录与枚举随版本变化。

`GetCoreMemSize` 返回字节，支持类型见 [官方 API](https://www.hiascend.com/document/detail/en/canncommercial/850/API/ascendcopapi/atlasascendc_api_07_1034.html)。不能用物理 SRAM 替代扣除 runtime/compiler 保留后的可用容量。带宽来自匹配平台 API 或明确的 microbenchmark，保留单位并区分理论与可达值；由 SKU 频率/指令假设推导的峰值 FLOPS 只是估计。

A3 可用 `npu-smi info -t board -i <id> -c <chip_id>` 读取 Chip Name/NPU Name。[A3 算子文档](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/850alpha002/API/aolapi/context/aclnnMoeDistributeCombineV2.md) 描述每卡双 die、API 单 die 视角；单设备 kernel 不自动使用整封装核或 HBM。虚拟设备可见核更少，保留真实可见数。

## SDK 配置示例，不作运行时默认

2026-10-05 在本地 CANN 9.0.0 `aarch64-linux/data/platform_config` 检查得到：

| INI | AIC/AIV | UB/L0C KiB | Cube 频率 MHz |
| --- | --- | --- | --- |
| Ascend910B2.ini | 24/48 | 192/128 | 1800 |
| Ascend910_9391.ini | 24/48 | 192/128 | 1850 |
| Ascend950PR_9589.ini | 32/64 | 248/256 | 1650 |
| Ascend950PR_957b.ini | 28/56 | 248/256 | 1650 |

这些值说明 ISA 与 SKU 资源不同，不能安装成 fallback 常量。配置只用于规划证据时记录文件 hash；没有 runtime 探测则硬件观测保持未知。

## 能力选择

三态能力区分支持、不支持与未知。特化路线要求架构/API/dtype/编译选项有支持证据；缺工具、探测失败或查询不支持都保持未知。配置目标与 runtime 冲突时，解决前不执行特化；通用兼容 fallback 满足自身要求后仍可用。

asc.gitcode.com 来自 asc-devkit master（2026-10-05 观测版本 `5c07153f668d`），明确属于开发预览。准确 ABI/约束优先安装 SDK 与对应 hiascend 发布文档。早期上游标为经验值的 HBM 带宽、SSBuffer 容量、通用 Vector 双发射峰值未验证，不作为常量。
