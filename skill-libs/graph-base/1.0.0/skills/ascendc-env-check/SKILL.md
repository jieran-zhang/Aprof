---
name: ascendc-env-check
description: Inspect the local CANN toolchain, device visibility, profiling tools, and target identity before an AProf build or measurement.
---

# AProf environment preflight

Record the selected device, raw SoC name, CANN/compiler versions, build target and exact commands. Inspect `ASCEND_HOME_PATH`, `command -v bisheng`, `command -v npu-compute`, `command -v msprof`, `command -v cannsim`, and `npu-smi info`; absence is a missing capability, not evidence of a particular model. Do not install or reset devices as part of preflight.

Use the bundled `npu-arch` capability to construct the architecture profile. In a cross-compile or simulator environment distinguish the configured target from the executing device. A target INI proves SDK configuration, not the hardware's available resources. Check that compiler target, generated binary and runtime SoC agree before launching.

Before profiling, build the isolated candidate and run the complete declared correctness matrix. Preserve stdout/stderr, exit status, timeout and hashes with the AProf stage runner. Reuse existing user execution authorization; a dry run is useful validation, not a new approval requirement.

Profiler routing is architecture-specific: verified npu-compute support is 950/dav-3510; 910C/A3 uses msprof. Check the selected executable's actual capabilities and matching CANN version. Do not install a tool or upgrade the system CANN/driver during this preflight.
