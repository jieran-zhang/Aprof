---
name: ascendc-crash-debug
description: Triage an Ascend C timeout, illegal access, AIC exception or synchronization hang from preserved AProf gate evidence.
---

# AProf crash and hang triage

Record the first failed launch, device/key, timeout, source/binary/tiling hashes and logs. Stop that candidate's performance collection. Check host/kernel argument agreement, per-core valid ranges, last-tile bounds, workspace sizing and buffer reuse before rerunning.

For hangs, draw the actual producer/wait/consumer dependencies: matching EnQue/DeQue, FreeTensor after last use, SetFlag/WaitFlag ordering, barrier participation and cross-core ownership. A missing participant or wait-before-produce is not repaired by arbitrary sleeps.

Use installed `msSanitizer` or supported simulator diagnostics only if available for this SDK/target; inspect the tool's help before forming the command. Keep sanitizer/simulator timing labeled diagnostic/proxy. Preserve logs and the first failing gate; any repaired child must repeat build, full correctness and timing gates.
