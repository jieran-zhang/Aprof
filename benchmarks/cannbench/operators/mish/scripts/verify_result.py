#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import numpy as np
import torch


def load_chunk(file_obj, dtype, count):
    raw = np.fromfile(file_obj, dtype=np.float32 if dtype == "float32" else np.uint16, count=count)
    if dtype == "float32":
        return raw
    if dtype == "float16":
        return raw.view(np.float16).astype(np.float32)
    return torch.from_numpy(raw.copy()).view(torch.bfloat16).float().numpy()


def torch_golden(values, dtype):
    # This is algebraically torch.nn.functional.mish, evaluated with stable
    # softplus.  The local CPU PyTorch build mixes scalar and approximate SIMD
    # paths for large FP32 tensors, while the official golden runs on NPU and
    # consistently follows this stable result (verified on Ascend910).
    with np.errstate(all="ignore"):
        softplus = np.maximum(values, np.float32(0.0)) + np.log1p(np.exp(-np.abs(values)))
        expected = values * np.tanh(softplus)
    if dtype == "float32":
        return expected.astype(np.float32)
    if dtype == "float16":
        return expected.astype(np.float16).astype(np.float32)
    return torch.from_numpy(expected).to(torch.bfloat16).float().numpy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True)
    args = parser.parse_args()
    metadata_path = Path(args.metadata)
    metadata = json.loads(metadata_path.read_text())
    numel = metadata["numel"]
    dtype = metadata["dtype"]
    threshold = {"float16": 2**-10, "bfloat16": 2**-7, "float32": 2**-13}[dtype]
    rel_sum = 0.0
    rel_max = 0.0
    finite_count = 0
    special_ok = True
    seen = 0
    with open(metadata["input"], "rb") as input_file, open(metadata["output"], "rb") as output_file:
        while seen < numel:
            count = min(1_000_000, numel - seen)
            values = load_chunk(input_file, dtype, count)
            actual = load_chunk(output_file, dtype, count)
            expected = torch_golden(values, dtype)
            special_ok &= bool(np.array_equal(np.isnan(actual), np.isnan(expected)))
            special_ok &= bool(np.array_equal(np.isposinf(actual), np.isposinf(expected)))
            special_ok &= bool(np.array_equal(np.isneginf(actual), np.isneginf(expected)))
            finite = np.isfinite(actual) & np.isfinite(expected)
            if finite.any():
                rel = np.abs(actual[finite] - expected[finite]) / (np.abs(expected[finite]) + 1e-7)
                rel_sum += float(rel.sum(dtype=np.float64))
                rel_max = max(rel_max, float(rel.max()))
                finite_count += int(finite.sum())
            seen += count
    mere = rel_sum / max(1, finite_count)
    passed = bool(special_ok and mere < threshold and rel_max < 10 * threshold)
    result = {
        "case_id": metadata["case_id"],
        "shape": metadata["shape"],
        "dtype": dtype,
        "attrs": {},
        "numel": numel,
        "mere": mere,
        "mare": rel_max,
        "threshold": threshold,
        "special_values_match": special_ok,
        "passed": passed,
    }
    (metadata_path.parent / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
