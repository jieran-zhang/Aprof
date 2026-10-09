---
name: ascendc-docs-search
description: Resolve an Ascend C API uncertainty from installed CANN headers and official versioned documentation without an external search skill or service.
---

# AProf API source lookup

Start with the executing/build SDK under `ASCEND_HOME_PATH`; use `rg` for the exact API and inspect its declaration, specialization and target guards. Record the actual SDK version and the file hash. For platform APIs inspect `include/platform/soc_spec.h` and `asc/include/utils/tiling/platform/platform_ascendc.h` (layout varies by SDK).

If local headers do not settle semantics, use official `https://www.hiascend.com/document` documentation for the matching CANN version, or the CANN organization source at `https://gitcode.com/cann/asc-devkit`. The official `https://asc.gitcode.com` rendering tracks master; record its revision and do not silently treat it as the installed release.

Return the exact declaration, supported architecture/dtype, units/alignment/lifetime constraints, evidence location and remaining uncertainty. A documentation lookup does not prove a speedup. No API key, external skill installation, custom search backend or copied private documentation is required.
