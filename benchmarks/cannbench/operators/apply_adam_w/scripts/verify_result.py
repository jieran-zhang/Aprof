#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import numpy as np
from gen_data import bf16_to_f32, raw_dtype

ROOT = Path(__file__).resolve().parents[1]


def resolve(path):
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def read(path, dtype):
    x = np.fromfile(path, dtype=raw_dtype(dtype))
    return bf16_to_f32(x) if dtype == "bfloat16" else x.astype(np.float32)


def main():
    p = argparse.ArgumentParser(); p.add_argument("--metadata", required=True); p.add_argument("--output")
    args = p.parse_args(); meta = json.loads(Path(args.metadata).read_text()); dtype = meta["dtype"]
    actual = read(resolve(args.output or meta["output"]), dtype); expected = read(resolve(meta["golden"]), dtype)
    special_ok = np.array_equal(np.isnan(actual), np.isnan(expected)) and np.array_equal(np.isposinf(actual), np.isposinf(expected)) and np.array_equal(np.isneginf(actual), np.isneginf(expected))
    finite = np.isfinite(actual) & np.isfinite(expected)
    # CANN-Bench benchmark_spec.md: denominator is abs(golden)+1e-7;
    # MERE is mean relative error and MARE is maximum relative error.
    diff = np.abs(actual[finite] - expected[finite]); rel = diff / (np.abs(expected[finite]) + 1e-7)
    mere = float(np.mean(rel)) if rel.size else 0.0; mare = float(np.max(rel)) if rel.size else 0.0
    threshold = {"float32": 0.005, "float16": 0.01, "bfloat16": 0.01}[dtype]
    passed = actual.size == expected.size and special_ok and mere < threshold and mare < 10 * threshold
    result = {"case_id": meta["case_id"], "dtype": dtype, "numel": meta["numel"], "MERE": mere, "MARE": mare,
              "threshold": threshold, "special_values_match": special_ok, "precision_pass": passed}
    out = Path(args.metadata).with_name("precision.json"); out.write_text(json.dumps(result, indent=2)); print(json.dumps(result))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__": main()
