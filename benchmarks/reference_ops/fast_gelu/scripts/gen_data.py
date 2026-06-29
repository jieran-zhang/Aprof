#!/usr/bin/env python3
"""Generate FP32 input and golden data for FastGelu skeleton (stdlib only)."""

import os
import random
import struct
import sys


def normalize_dtype(dtype: str) -> str:
    if dtype not in ("fp32", "float32", "float"):
        raise ValueError(f"FastGelu skeleton currently supports FP32 only, got {dtype}")
    return "fp32"


def fast_gelu_scalar(x: float) -> float:
    import math

    return x / (math.exp(-1.702 * x) + 1.0)


def generate_data(m: int, n: int, dtype: str) -> None:
    normalize_dtype(dtype)
    os.makedirs("data", exist_ok=True)

    rng = random.Random(42)
    total = m * n
    input_vals = [rng.uniform(-3.0, 3.0) for _ in range(total)]
    golden_vals = [fast_gelu_scalar(x) for x in input_vals]

    with open("data/input.bin", "wb") as f:
        f.write(struct.pack(f"{total}f", *input_vals))
    with open("data/golden.bin", "wb") as f:
        f.write(struct.pack(f"{total}f", *golden_vals))

    print(f"[INFO] Generated input:  [{m}, {n}] fp32 ({total * 4} bytes)")
    print(f"[INFO] Generated golden: [{m}, {n}] fp32 ({total * 4} bytes)")
    print(f"[INFO] Input[0:4] = {input_vals[:4]}")
    print(f"[INFO] Golden[0:4] = {golden_vals[:4]}")


if __name__ == "__main__":
    m_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    n_arg = int(sys.argv[2]) if len(sys.argv) > 2 else 2048
    dtype_arg = sys.argv[3] if len(sys.argv) > 3 else "fp32"
    generate_data(m_arg, n_arg, dtype_arg)
