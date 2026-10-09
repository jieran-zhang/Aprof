---
name: ascendc-runtime-debug
description: Triage an AProf candidate runtime failure from exact command, binary identity, runtime logs and SDK/device compatibility.
---

# AProf runtime failure

Preserve exit status, stdout/stderr, first runtime error, selected device/key, binary/source hashes and SDK/runtime versions. Distinguish build/load/launch/synchronize failures and accuracy failure. Read the installed SDK's error definitions; do not guess error-code meanings.

Check toolchain/runtime target compatibility, stale binary paths, library search paths, launch signature and tiling ABI, workspace allocation and output synchronization. Use the bundled `ascendc-env-check` only for environment issues. Reproduce the smallest allowed input on the same target while keeping the original failed attempt unchanged.

For timeout, illegal access, AIC error or deadlock use bundled `ascendc-crash-debug`. A repair is a child candidate, not an overwrite of the failed evidence. Never reset a shared device or kill another user's job as a generic recovery step.
