# Platform identity, resources and provenance

| Product family | ISA | Planning consequence |
| --- | --- | --- |
| 910B / Atlas A2 | DAV_2201 | Membase vector execution; plan AIC/AIV separately using visible resources |
| 910C / Atlas A3 | DAV_2201 | Same ISA; retain actual Ascend910_93xx identity and device/die/topology instead of assuming equal resources or double resources |
| 950 PR/DT | DAV_3510 | RegBase, SIMT/mixed and new DMA/CV paths can change plan costs and implementation options; check SDK/API support |

Official [GetCurNpuArch](https://asc.gitcode.com/api/Utils-API/platform_info/PlatformAscendC/GetCurNpuArch.html) maps A2/A3 to 2201 and 950 PR/DT to 3510. Official [GetSocVersion](https://asc.gitcode.com/api/Utils-API/platform_info/PlatformAscendC/GetSocVersion.html) states A2/A3 share the enum and recommends `aclrtGetSocName()` to distinguish them. The user-facing 910C label is retained, but exact SKU identity must come from a probe; unknown marketing aliases do not override observed ISA.

## Acquire actual values

In Host Tiling instantiate `PlatformAscendC(context->GetPlatformInfo())`; direct-launch code can use `PlatformAscendCManager::GetInstance()` after selecting/initializing the intended device. Check for null and target mismatch. Read `GetCurNpuArch`, `GetCoreNumAic`, `GetCoreNumAiv`, and `GetCoreMemSize` for each needed memory level. API declarations live under the selected SDK's `asc/include/utils/tiling/platform/platform_ascendc.h` and `include/platform/soc_spec.h`; layouts and enum availability vary by CANN release.

`GetCoreMemSize` returns bytes; [official API documentation](https://www.hiascend.com/document/detail/en/canncommercial/850/API/ascendcopapi/atlasascendc_api_07_1034.html) specifies the supported types. Do not substitute physical SRAM capacity for usable capacity after runtime/compiler reservation. If available, get bandwidth through the matching platform API or an explicitly measured microbenchmark; preserve units and distinguish theoretical from attainable values. Peak FLOPS derived from SKU frequency/instruction assumptions is an estimate, not an observed denominator.

For A3, `npu-smi info -t board -i <id> -c <chip_id>` exposes Chip Name/NPU Name. Official [A3 operator documentation](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/850alpha002/API/aolapi/context/aclnnMoeDistributeCombineV2.md) describes products with two dies per card and a single-die API view. A single-device kernel does not automatically use package-wide cores or HBM. A virtual device may expose fewer cores; always preserve its visible counts.

## SDK configuration examples, not runtime defaults

Locally inspected CANN 9.0.0 `aarch64-linux/data/platform_config` on 2026-10-05:

| INI | AIC/AIV | UB/L0C KiB | Cube frequency MHz |
| --- | --- | --- | --- |
| Ascend910B2.ini | 24/48 | 192/128 | 1800 |
| Ascend910_9391.ini | 24/48 | 192/128 | 1850 |
| Ascend950PR_9589.ini | 32/64 | 248/256 | 1650 |
| Ascend950PR_957b.ini | 28/56 | 248/256 | 1650 |

These values show why ISA and SKU resources are separate. Do not install them as fallback constants. Record the actual file hash when a configuration supplies planning-only evidence. Without a runtime probe, leave hardware observation unknown.

## Feature decisions

Tri-state capability values distinguish supported, unsupported and unknown. A specialized route requires supported architecture/API/dtype/compile-option evidence. Reserve unknown for missing tools, failed probes and unsupported query APIs. Contradictory configured/runtime targets block specialized execution until resolved. A generic compatible fallback remains available when its own requirements are satisfied.

The official asc.gitcode.com pages are generated from asc-devkit master (observed revision 5c07153f668d on 2026-10-05); they explicitly describe development previews. Prefer the installed SDK and corresponding versioned hiascend release for exact ABI and constraints. Earlier upstream skill values labeled experience-based (HBM bandwidth, SSBuffer capacity, universal vector dual-issue peaks) are not verified constants and are deliberately excluded.
