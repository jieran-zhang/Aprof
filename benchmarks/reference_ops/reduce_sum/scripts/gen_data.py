#!/usr/bin/env python3
"""Generate FP32 input and golden data for ReduceSum skeleton."""

import os
import sys

import numpy as np


def normalize_dtype(dtype: str) -> str:
    if dtype not in ("fp32", "float32", "float"):
        raise ValueError(f"ReduceSum_template currently supports FP32 only, got {dtype}")
    return "fp32"


def generate_data(m: int, n: int, dtype: str) -> None:
    normalize_dtype(dtype)
    os.makedirs("data", exist_ok=True)

    rng = np.random.default_rng(42)
    input_data = rng.uniform(-10.0, 10.0, size=(m, n)).astype(np.float32)
    golden_data = input_data.sum(axis=1, dtype=np.float32)

    input_data.tofile("data/input.bin")
    golden_data.tofile("data/golden.bin")

    print(f"[INFO] Generated input:  [{m}, {n}] fp32 ({input_data.nbytes} bytes)")
    print(f"[INFO] Generated golden: [{m}] fp32 ({golden_data.nbytes} bytes)")
    print(f"[INFO] Input[0, 0:4] = {input_data[0, :min(4, n)]}")
    print(f"[INFO] Golden[0:4]   = {golden_data[:min(4, m)]}")


if __name__ == "__main__":
    m_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    n_arg = int(sys.argv[2]) if len(sys.argv) > 2 else 2048
    dtype_arg = sys.argv[3] if len(sys.argv) > 3 else "fp32"
    generate_data(m_arg, n_arg, dtype_arg)
