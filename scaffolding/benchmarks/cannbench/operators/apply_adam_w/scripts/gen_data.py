#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path
import numpy as np
from cases import get_case
from golden import apply_adam_w


NAMES = ("var", "grad", "m", "v")


def f32_to_bf16(x):
    u = np.asarray(x, dtype=np.float32).view(np.uint32)
    return ((u + np.uint32(0x7FFF) + ((u >> 16) & 1)) >> 16).astype(np.uint16)


def bf16_to_f32(x):
    return (np.asarray(x, dtype=np.uint16).astype(np.uint32) << 16).view(np.float32)


def decode(raw, dtype):
    if dtype == "float32": return np.asarray(raw, dtype=np.float32)
    if dtype == "float16": return np.asarray(raw, dtype=np.float16).astype(np.float32)
    return bf16_to_f32(raw)


def encode(x, dtype):
    if dtype == "float32": return np.asarray(x, dtype=np.float32)
    if dtype == "float16": return np.asarray(x, dtype=np.float16)
    return f32_to_bf16(x)


def raw_dtype(dtype):
    return {"float32": np.float32, "float16": np.float16, "bfloat16": np.uint16}[dtype]


def finite_or_special(rng, count, bounds):
    lo, hi = bounds
    if isinstance(lo, str) and lo.lower() == "nan": return np.full(count, np.nan, np.float32)
    if isinstance(lo, str) and "inf" in lo.lower():
        out = np.empty(count, np.float32); out[0::2] = -np.inf; out[1::2] = np.inf; return out
    lo, hi = float(lo), float(hi)
    if math.isnan(lo) or math.isnan(hi): return np.full(count, np.nan, np.float32)
    if math.isinf(lo) or math.isinf(hi):
        out = np.empty(count, np.float32); out[0::2] = lo; out[1::2] = hi; return out
    if lo == hi: return np.full(count, lo, np.float32)
    return rng.uniform(lo, hi, count).astype(np.float32)


def main():
    p = argparse.ArgumentParser(); p.add_argument("--case", type=int, required=True)
    p.add_argument("--output", default="build/cases"); p.add_argument("--seed", type=int, default=20260811)
    args = p.parse_args(); case = get_case(args.case); numel = math.prod(case["shape"])
    root = Path(args.output) / f"case_{args.case:02d}"; inp = root / "input"; inp.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed + args.case); chunk = 1 << 20
    for name, bounds in zip(NAMES, case["ranges"]):
        mm = np.memmap(inp / f"{name}.bin", mode="w+", dtype=raw_dtype(case["dtype"]), shape=(numel,))
        for start in range(0, numel, chunk):
            end = min(numel, start + chunk); mm[start:end] = encode(finite_or_special(rng, end-start, bounds), case["dtype"])
        mm.flush(); del mm
    inputs = [np.memmap(inp / f"{n}.bin", mode="r", dtype=raw_dtype(case["dtype"]), shape=(numel,)) for n in NAMES]
    golden = np.memmap(root / "golden.bin", mode="w+", dtype=raw_dtype(case["dtype"]), shape=(numel,))
    for start in range(0, numel, chunk):
        end = min(numel, start + chunk)
        values = [decode(x[start:end], case["dtype"]) for x in inputs]
        golden[start:end] = encode(apply_adam_w(*values, case["attrs"]), case["dtype"])
    golden.flush()
    metadata = {**case, "numel": numel, "seed": args.seed + args.case, "input_dir": str(inp),
                "golden": str(root / "golden.bin"), "output": str(root / "output.bin")}
    (root / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__": main()
