#!/usr/bin/env python3
"""Verify FP32 FastGelu skeleton output against generated golden data (stdlib only)."""

import os
import struct
import sys


def normalize_dtype(dtype: str) -> str:
    if dtype not in ("fp32", "float32", "float"):
        raise ValueError(f"FastGelu skeleton currently supports FP32 only, got {dtype}")
    return "fp32"


def read_floats(path: str) -> list[float]:
    with open(path, "rb") as f:
        data = f.read()
    if len(data) % 4 != 0:
        raise ValueError(f"Invalid float32 file size: {path}")
    count = len(data) // 4
    return list(struct.unpack(f"{count}f", data))


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

    golden = read_floats(golden_path)
    output = read_floats(output_path)
    if len(golden) != len(output):
        print(f"[ERROR] Shape mismatch: golden {len(golden)}, output {len(output)}")
        sys.exit(1)

    abs_err = [abs(g - o) for g, o in zip(golden, output)]
    rel_err = [ae / max(abs(g), 1e-8) for ae, g in zip(abs_err, golden)]
    max_abs = max(abs_err) if abs_err else 0.0
    max_rel = max(rel_err) if rel_err else 0.0

    print(f"[INFO] Comparing {len(golden)} fp32 elements")
    print(f"[INFO] Max abs error: {max_abs:.6e}")
    print(f"[INFO] Max rel error: {max_rel:.6e}")

    rtol, atol = 1e-4, 1e-4
    for idx, (g, o, ae) in enumerate(zip(golden, output, abs_err)):
        if ae > atol + rtol * abs(g):
            print("[FAIL] Tolerance exceeded (rtol=1e-4, atol=1e-4)")
            print(f"[FAIL] Worst index {idx}: golden={g:.6f}, output={o:.6f}, abs_err={ae:.6e}")
            sys.exit(1)

    print("[PASS] All elements within tolerance")


if __name__ == "__main__":
    dtype_arg = sys.argv[1] if len(sys.argv) > 1 else "fp32"
    verify(dtype_arg)
