#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch

from cases import get_case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=int, required=True)
    parser.add_argument("--output", default="build/cases")
    args = parser.parse_args()
    case = get_case(args.case)
    numel = math.prod(case["shape"])
    case_dir = Path(args.output) / f"case_{args.case:02d}"
    case_dir.mkdir(parents=True, exist_ok=True)
    input_path = case_dir / "input.bin"
    rng = np.random.default_rng(20260811 + args.case)
    with input_path.open("wb") as output:
        for start in range(0, numel, 1_000_000):
            size = min(1_000_000, numel - start)
            lo, hi = case["value_range"]
            if math.isnan(lo):
                values = np.full(size, np.nan, dtype=np.float32)
            elif math.isinf(lo):
                values = np.empty(size, dtype=np.float32)
                values[0::2] = -np.inf
                values[1::2] = np.inf
            elif lo == hi:
                values = np.full(size, lo, dtype=np.float32)
            else:
                values = rng.uniform(lo, hi, size=size).astype(np.float32)
            if case["dtype"] == "float32":
                raw = values
            elif case["dtype"] == "float16":
                raw = values.astype(np.float16)
            else:
                raw = torch.from_numpy(values).to(torch.bfloat16).view(torch.uint16).numpy()
            output.write(raw.tobytes())
    metadata = {
        **case,
        "numel": numel,
        "input": str(input_path.resolve()),
        "output": str((case_dir / "output.bin").resolve()),
    }
    (case_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=True))
    print(case_dir / "metadata.json")


if __name__ == "__main__":
    main()
