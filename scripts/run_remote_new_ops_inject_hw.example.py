#!/usr/bin/env python3
"""Example remote 910B runner for upgraded aprof_injected_ops (direct-invoke).

Copy to run_remote_new_ops_inject_hw.py (gitignored) and set credentials, or set:
  APROF_REMOTE_HOST, APROF_REMOTE_PORT, APROF_REMOTE_USER, APROF_REMOTE_PASS

Optional:
  INJECT_OPS=gelu_mul,mish
  INJECT_CASES_gelu_mul=baseline,op_0001
  ASC_ARCH_HW=dav-2201
"""
# See scripts/run_remote_new_ops_inject_hw.py for the full implementation used locally.
raise SystemExit(
    "Copy the local gitignored runner or implement from README: "
    "upload baseline/op_XXXX, then bash run.sh all && bash run.sh hw"
)
