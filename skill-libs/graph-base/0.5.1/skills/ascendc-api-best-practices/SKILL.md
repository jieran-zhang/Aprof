---
name: ascendc-api-best-practices
description: Check Ascend C copy, queue, synchronization, reduction and matrix API constraints against the installed SDK before an AProf execution edit.
---

# AProf API checks

Read [API and memory contracts](references/api-contracts.md) for copy alignment, queue lifetime, event order, repeat/mask limits, reduction and matrix boundaries. Read [RegBase and SIMT](../npu-arch/references/regbase-simt.md) only for a confirmed supported target.

The installed target SDK headers and version-matched official documentation determine exact overloads, units, supported dtypes and compilation macros. Record the header path/version or official URL with the candidate; do not infer signatures from a different SDK. The bundled `ascendc-docs-search` describes this lookup without an external skill dependency.
