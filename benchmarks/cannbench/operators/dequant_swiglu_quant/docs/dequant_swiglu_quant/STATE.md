# dequant_swiglu_quant state

- [x] Authoritative level-3 specification and original 20 cases inspected
- [x] SoC fixed to Ascend910_9362 / dav-2201
- [x] Definition and device-side design documented
- [x] CMake, host, kernel, run, case generation, and verifier implemented
- [x] dav-2201 build succeeds
- [x] Original 20 cases pass on real NPU (physical device1, visible device0)
- [x] `results.json` records 20/20 and final boundary audit passes

Test gate is disabled by repository configuration. Correctness-only route: profiling and performance optimization are intentionally omitted.

Final command: `ASCEND_RT_VISIBLE_DEVICES=1 ./run.sh --all --skip-build --device 0`. Result: 20/20 passed on 2026-08-12.
