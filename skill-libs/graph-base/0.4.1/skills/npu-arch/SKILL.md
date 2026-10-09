---
name: npu-arch
description: Build an evidence-backed AProf architecture profile and distinguish 910B/A2, 910C/A3 and 950/3510 capabilities before parallel planning or execution tuning.
---

# AProf architecture profile

Preserve the raw SoC name, ISA architecture, device/die view, installed CANN/compiler and observed visible resources separately. Read [platform identity and evidence](references/platform-evidence.md) before selecting capabilities, and [RegBase/SIMT](references/regbase-simt.md) only for a confirmed 3510 path.

`architecture_id` is `910b`, `910c`, `950` or `unknown`; it is a product-family label, not the ISA. A2 and A3 share `DAV_2201`, and `GetSocVersion()` can return the same enum for both. Distinguish them using `aclrtGetSocName()` and observed device/board identity. An unrecognized name stays unknown rather than being guessed from a substring.

Get visible AIC/AIV counts and usable UB/L1/L0/L2 from `PlatformAscendC`, preserving each value's source. Unknown values are null; do not use them as denominators or permit a capacity-dependent specialization. Confirmed ISA features still require matching SDK APIs and compile options. No fixed core count, bandwidth or peak FLOPS is implied by the family name.

Construct and validate the strict architecture artifact:

```bash
aprofctl contract validate --kind architecture_profile --input <architecture.json>
```

Preserve the canonical content hash in the parallel plan and context evidence. Configured SDK/INI targets and simulator profiles must remain distinguishable from runtime hardware observations. Do not describe simulator timing as hardware performance.
