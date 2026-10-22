#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch

from cases import get_case


def write_input(path, case, numel):
    rng = np.random.default_rng(20260811 + case["case_id"])
    lo, hi = case["value_range"]
    with path.open("wb") as output:
        for start in range(0, numel, 1_000_000):
            count = min(1_000_000, numel - start)
            if math.isnan(lo):
                values = np.full(count, np.nan, dtype=np.float32)
            elif math.isinf(lo):
                values = np.empty(count, dtype=np.float32)
                # Continue the global alternating pattern across chunks.
                parity = np.arange(start, start + count) & 1
                values[:] = np.where(parity == 0, -np.inf, np.inf)
            elif lo == hi:
                values = np.full(count, lo, dtype=np.float32)
            else:
                values = rng.uniform(lo, hi, size=count).astype(np.float32)
            if case["dtype"] == "float16":
                raw = values.astype(np.float16)
            else:
                raw = torch.from_numpy(values).to(torch.bfloat16).view(torch.uint16).numpy()
            output.write(raw.tobytes())


def load_rows(raw_map, dtype, start, count, row_length):
    storage = np.array(raw_map[start * row_length:(start + count) * row_length], copy=True)
    tensor = torch.from_numpy(storage)
    if dtype == "bfloat16":
        tensor = tensor.view(torch.bfloat16)
    return tensor.reshape(count, row_length)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=int, required=True)
    parser.add_argument("--output", default="build/cases")
    args = parser.parse_args()
    case = get_case(args.case)
    numel = math.prod(case["shape"])
    row_length = case["shape"][-1]
    token_count = numel // row_length
    case_dir = Path(args.output) / f"case_{args.case:02d}"
    case_dir.mkdir(parents=True, exist_ok=True)
    input_path = case_dir / "input.bin"
    golden_y_path = case_dir / "golden_y.bin"
    golden_scale_path = case_dir / "golden_scale.bin"
    write_input(input_path, case, numel)
    storage_dtype = np.float16 if case["dtype"] == "float16" else np.uint16
    raw_map = np.memmap(input_path, mode="r", dtype=storage_dtype, shape=(numel,))
    rows_per_chunk = max(1, 1_000_000 // row_length)
    with golden_y_path.open("wb") as y_file, golden_scale_path.open("wb") as scale_file:
        for start in range(0, token_count, rows_per_chunk):
            count = min(rows_per_chunk, token_count - start)
            x = load_rows(raw_map, case["dtype"], start, count, row_length).float()
            abs_max = torch.max(torch.abs(x), dim=-1, keepdim=True)[0]
            scale = abs_max.clamp(min=1e-12) / 127.0
            y = torch.clamp(torch.round(x / scale), -128, 127).to(torch.int8)
            y.contiguous().numpy().tofile(y_file)
            scale.squeeze(-1).contiguous().numpy().tofile(scale_file)
    metadata = {
        **case,
        "attrs": {},
        "numel": numel,
        "row_length": row_length,
        "token_count": token_count,
        "input": str(input_path.resolve()),
        "golden_y": str(golden_y_path.resolve()),
        "golden_scale": str(golden_scale_path.resolve()),
        "output_y": str((case_dir / "output_y.bin").resolve()),
        "output_scale": str((case_dir / "output_scale.bin").resolve()),
    }
    (case_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=True))
    print(case_dir / "metadata.json")


if __name__ == "__main__":
    main()
