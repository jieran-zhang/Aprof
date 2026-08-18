#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch

from cases import get_case


def storage_dtype(dtype):
    return {
        "float16": np.float16,
        "float32": np.float32,
        "bfloat16": np.uint16,
        "int32": np.int32,
        "int64": np.int64,
    }[dtype]


def write_input(path, case, numel):
    rng = np.random.default_rng(20260811 + case["case_id"])
    lo, hi = case["value_range"]
    with path.open("wb") as output:
        for start in range(0, numel, 1_000_000):
            size = min(1_000_000, numel - start)
            if case["dtype"] in ("int32", "int64"):
                if lo == hi:
                    raw = np.full(size, lo, dtype=storage_dtype(case["dtype"]))
                else:
                    raw = rng.integers(lo, hi + 1, size=size, dtype=storage_dtype(case["dtype"]))
            else:
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


def load_tensor(path, case):
    raw = np.memmap(path, mode="r", dtype=storage_dtype(case["dtype"]), shape=(math.prod(case["shape"]),))
    tensor = torch.from_numpy(raw)
    if case["dtype"] == "bfloat16":
        tensor = tensor.view(torch.bfloat16)
    return tensor.reshape(case["shape"])


def output_shape(shape, dim, keepdim):
    axis = dim if dim >= 0 else dim + len(shape)
    result = list(shape)
    if keepdim:
        result[axis] = 1
    else:
        result.pop(axis)
    return result


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
    golden_path = case_dir / "golden.bin"
    write_input(input_path, case, numel)
    values = load_tensor(input_path, case)
    expected = torch.argmax(values, dim=case["dim"], keepdim=case["keepdim"])
    expected.contiguous().numpy().tofile(golden_path)
    metadata = {
        **case,
        "attrs": {"dim": case["dim"], "keepdim": case["keepdim"]},
        "numel": numel,
        "output_shape": output_shape(case["shape"], case["dim"], case["keepdim"]),
        "output_numel": expected.numel(),
        "input": str(input_path.resolve()),
        "golden": str(golden_path.resolve()),
        "output": str((case_dir / "output.bin").resolve()),
    }
    (case_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=True))
    print(case_dir / "metadata.json")


if __name__ == "__main__":
    main()
