---
name: npu-arch
description: 在并行规划或执行调优前，建立有证据的 AProf 架构档案，区分 910B/A2、910C/A3 与 950/3510 能力。
---

# AProf 架构档案

分别保留原始 SoC 名、ISA、device/die 视角、已安装 CANN/编译器和可见资源。先读 [平台身份与证据](references/platform-evidence.md)；仅在确认 3510 路径后读 [RegBase/SIMT](references/regbase-simt.md)。

`architecture_id` 为 `910b`、`910c`、`950` 或 `unknown`，表示产品族而非 ISA。A2/A3 共用 `DAV_2201`，`GetSocVersion()` 可能相同，需用 `aclrtGetSocName()` 及设备/板卡身份区分。未知名称保持 unknown，不能靠子串猜测。

从 `PlatformAscendC` 获取可见 AIC/AIV 和可用 UB/L1/L0/L2，记录每个值的来源。未知值为 null，不可用作分母或授权容量相关特化。ISA 特性还需匹配 SDK API 和编译选项；产品族不隐含固定核数、带宽或峰值 FLOPS。

```bash
aprofctl contract validate --kind architecture_profile --input <architecture.json>
```

在并行计划与上下文保留规范内容 hash。SDK/INI 配置、simulator 档案与真实硬件观测须明确区分，模拟计时不能称为硬件性能。
