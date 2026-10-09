#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path
import numpy as np
import torch
from cases import get_case

RAW = {"float16": np.float16, "bfloat16": np.uint16, "int8": np.int8,
       "int32": np.int32, "int64": np.int64, "float32": np.float32}

def write_values(path, shape, dtype, value_range, rng):
    count = math.prod(shape)
    out = np.memmap(path, dtype=RAW[dtype], mode="w+", shape=(count,))
    for off in range(0, count, 2_000_000):
        size = min(2_000_000, count - off)
        lo, hi = value_range
        if dtype.startswith("int"):
            values = rng.integers(int(lo), int(hi), endpoint=True, size=size, dtype=RAW[dtype])
        else:
            values = rng.uniform(lo, hi, size).astype(np.float32)
        if dtype == "bfloat16":
            out[off:off + size] = torch.from_numpy(values).to(torch.bfloat16).view(torch.uint16).numpy()
        else:
            out[off:off + size] = values.astype(RAW[dtype])
    out.flush()

parser = argparse.ArgumentParser()
parser.add_argument("--case", type=int, required=True)
parser.add_argument("--output", default="build/cases")
args = parser.parse_args()
case = get_case(args.case)
case_dir = Path(args.output) / f"case_{args.case:02d}"
case_dir.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(20260812 + args.case)
shapes, dtypes, ranges = case["input_shape"], case["dtype"], case["value_range"]
a, h = shapes[0]
n, e = shapes[1]
files = {}
tokens_path = (case_dir / "tokens.bin").resolve()
write_values(tokens_path, shapes[0], dtypes[0], ranges[0], rng)
files["tokens"] = str(tokens_path)
# This exactly follows golden.get_input: every cell is positive and the final
# cell absorbs the remainder, so the sum is A for every authoritative case.
base, remainder = divmod(a, n * e)
if base < 1:
    raise ValueError(f"case violates positive-count contract: A={a}, N*E={n*e}")
counts = np.full((n, e), base, dtype=RAW[dtypes[1]])
counts[-1, -1] += remainder
counts_path = (case_dir / "counts.bin").resolve()
counts.tofile(counts_path)
files["counts"] = str(counts_path)
if shapes[2] is not None:
    scales_path = (case_dir / "scales.bin").resolve()
    write_values(scales_path, shapes[2], "float32", ranges[2], rng)
    files["scales"] = str(scales_path)
outputs = {name: str((case_dir / f"{name}.bin").resolve())
           for name in ("output_tokens", "output_scales", "output_index", "output_count")}
metadata = {
    "case_id": args.case, "input_shape": shapes, "dtype": dtypes,
    "attrs": case["attrs"], "tokens": a, "hidden": h, "ranks": n, "experts": e,
    "files": files, "outputs": outputs, "note": case.get("note", "")
}
(case_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
print(case_dir / "metadata.json")
