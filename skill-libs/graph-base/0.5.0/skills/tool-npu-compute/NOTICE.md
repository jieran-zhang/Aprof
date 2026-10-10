# Provenance and compatibility

This is an AProf-local distillation of CANNBot's npu-compute operator guidance.
It is self-contained and does not load the upstream skill at runtime.

- Source: [cann/cannbot-skills tool-npu-compute](https://gitcode.com/cann/cannbot-skills/tree/1fd7ec9770ecde574be5888c992997ffff910e71/tools/tool-npu-compute).
- Pinned revision: `1fd7ec9770ecde574be5888c992997ffff910e71`; local source inspected 2026-10-10.
- Distilled material: collection/CLI guidance, metric foundations, summary,
  data availability, hardware identity and Pipeline interpretation.
- Retained upstream files, without modification: `cli_support.py`,
  `scripts/inspect_pipe_trace.py`, `assets/pipe-trace-catalog.json`.
- Copyright (c) 2026 Huawei Technologies Co., Ltd. Distribution terms and
  retained notices are in [LICENSE](LICENSE).

Hardware support was checked against the official
[npu-compute documentation](https://gitcode.com/cann/asc-tools/blob/8b15e97b18375f12e90884eee052d09ca36dcac7/docs/zh/06_npu_compute.md),
asc-tools revision `8b15e97b18375f12e90884eee052d09ca36dcac7`.
That documented scope is Ascend 950 / dav-3510, Ascend C kernels and one operator
invocation. It does not establish support for 910C/A3. Inspect installed-version
capabilities before actual execution; do not silently generalize master claims
to a different toolchain.

The upstream real-capture fixture is from Ascend950PR_9599 / 3510. Offline fixture
validation demonstrates parser compatibility, not a 950 capture on the current
A3 machine. AProf keeps the A3 route on msprof and preserves the system CANN and
driver. The release-level validation report records actual machine results.
