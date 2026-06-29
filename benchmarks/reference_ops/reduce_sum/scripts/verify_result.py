#!/usr/bin/env python3
"""Verify FP32 ReduceSum skeleton output against generated golden data."""

import os
import sys

import numpy as np


def normalize_dtype(dtype: str) -> str:
    if dtype not in ("fp32", "float32", "float"):
        raise ValueError(f"ReduceSum_template currently supports FP32 only, got {dtype}")
    return "fp32"


def verify(dtype: str) -> None:
    normalize_dtype(dtype)
    golden_path = "data/golden.bin"
    output_path = "build/output/output.bin"

    if not os.path.exists(golden_path):
        print(f"[ERROR] Golden file not found: {golden_path}")
        sys.exit(1)
    if not os.path.exists(output_path):
        print(f"[ERROR] Output file not found: {output_path}")
        sys.exit(1)

    golden = np.fromfile(golden_path, dtype=np.float32)
    output = np.fromfile(output_path, dtype=np.float32)
    if golden.shape != output.shape:
        print(f"[ERROR] Shape mismatch: golden {golden.shape}, output {output.shape}")
        sys.exit(1)

    abs_err = np.abs(golden - output)
    rel_err = abs_err / np.maximum(np.abs(golden), 1e-8)
    max_abs = float(abs_err.max()) if abs_err.size else 0.0
    max_rel = float(rel_err.max()) if rel_err.size else 0.0

    print(f"[INFO] Comparing {golden.size} fp32 elements")
    print(f"[INFO] Max abs error: {max_abs:.6e}")
    print(f"[INFO] Max rel error: {max_rel:.6e}")

    if not np.allclose(golden, output, rtol=1e-5, atol=1e-5):
        worst_idx = int(np.argmax(abs_err))
        print("[FAIL] Tolerance exceeded (rtol=1e-5, atol=1e-5)")
        print(
            f"[FAIL] Worst index {worst_idx}: golden={golden[worst_idx]:.6f}, "
            f"output={output[worst_idx]:.6f}, abs_err={abs_err[worst_idx]:.6e}"
        )
        sys.exit(1)

    print("[PASS] All elements within tolerance")


if __name__ == "__main__":
    dtype_arg = sys.argv[1] if len(sys.argv) > 1 else "fp32"
    verify(dtype_arg)
