#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

from golden import apply_adam_w


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/smoke"
DEVICE = 0


def run_valid(name, numel, attrs, values, shape):
    case_dir = OUT / name
    input_dir = case_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    arrays = []
    for tensor_name, value in zip(("var", "grad", "m", "v"), values):
        array = np.full(numel, value, dtype=np.float32) if np.isscalar(value) else np.asarray(value, dtype=np.float32)
        assert array.size == numel
        array.tofile(input_dir / f"{tensor_name}.bin")
        arrays.append(array)
    output = case_dir / "output.bin"
    command = [str(ROOT / "build/apply_adam_w"), "--numel", str(numel), "--dtype", "float32",
        "--input-dir", str(input_dir), "--output", str(output), "--lr", str(attrs["lr"]),
        "--beta1", str(attrs["beta1"]), "--beta2", str(attrs["beta2"]),
        "--weight-decay", str(attrs["weight_decay"]), "--epsilon", str(attrs["epsilon"]),
        "--step", str(attrs["step"]), "--maximize", str(int(attrs["maximize"])), "--device", str(DEVICE)]
    subprocess.run(command, check=True)
    actual = np.fromfile(output, dtype=np.float32)
    with np.errstate(all="ignore"):
        expected = apply_adam_w(*arrays, attrs)
    special = (np.array_equal(np.isnan(actual), np.isnan(expected)) and
               np.array_equal(np.isposinf(actual), np.isposinf(expected)) and
               np.array_equal(np.isneginf(actual), np.isneginf(expected)))
    finite = np.isfinite(actual) & np.isfinite(expected)
    close = np.allclose(actual[finite], expected[finite], rtol=5e-3, atol=1e-6)
    passed = bool(special and close and actual.size == expected.size)
    record = {"name": name, "shape": shape, "numel": numel, "attrs": attrs,
              "command": command, "passed": passed}
    (case_dir / "result.json").write_text(json.dumps(record, indent=2))
    if not passed:
        raise RuntimeError(f"smoke case failed: {name}")
    return record


def run_invalid(name, overrides):
    case_dir = OUT / name
    input_dir = case_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    for tensor_name in ("var", "grad", "m", "v"):
        np.zeros(8, dtype=np.float32).tofile(input_dir / f"{tensor_name}.bin")
    attrs = {"lr": 1e-3, "beta1": 0.9, "beta2": 0.999, "weight_decay": 0.0,
             "epsilon": 1e-8, "step": 1, "maximize": False, "dtype": "float32"}
    attrs.update(overrides)
    command = [str(ROOT / "build/apply_adam_w"), "--numel", "8", "--dtype", attrs["dtype"],
        "--input-dir", str(input_dir), "--output", str(case_dir / "output.bin"), "--lr", str(attrs["lr"]),
        "--beta1", str(attrs["beta1"]), "--beta2", str(attrs["beta2"]),
        "--weight-decay", str(attrs["weight_decay"]), "--epsilon", str(attrs["epsilon"]),
        "--step", str(attrs["step"]), "--maximize", "0", "--device", str(DEVICE)]
    completed = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    passed = completed.returncode != 0
    record = {"name": name, "command": command, "returncode": completed.returncode,
              "stderr": completed.stderr, "passed": passed}
    (case_dir / "result.json").write_text(json.dumps(record, indent=2))
    if not passed:
        raise RuntimeError(f"invalid smoke case was accepted: {name}")
    return record


def main():
    global DEVICE
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", type=int, default=0)
    DEVICE = parser.parse_args().device
    base = {"lr": 1e-3, "beta1": 0.9, "beta2": 0.999, "weight_decay": 0.0,
            "epsilon": 1e-8, "step": 1, "maximize": False}
    records = [
        run_valid("level0_8", 8, base, (0.5, 0.25, 0.1, 0.2), [8]),
        run_valid("level0_16_step2", 16, {**base, "step": 2}, (0.5, 0.25, 0.1, 0.2), [16]),
        run_valid("step100_beta_near1", 16, {**base, "beta1": 0.9999, "beta2": 0.9999, "step": 100},
                  (0.5, 0.25, 0.1, 0.2), [2, 8]),
        run_valid("negative_vhat", 8, base, (0.5, 0.0, 0.1, -1.0), [8]),
        run_valid("zero_div_zero", 8, {**base, "epsilon": 0.0}, (0.0, 0.0, 0.0, 0.0), [8]),
        run_valid("positive_div_zero", 8, {**base, "epsilon": 0.0}, (0.0, 0.0, 1.0, 0.0), [8]),
        run_valid("minimum_shape", 1, base, (0.5, 0.25, 0.1, 0.2), [1]),
        run_valid("shape_8d", 256, base, (0.5, 0.25, 0.1, 0.2), [2, 2, 2, 2, 2, 2, 2, 2]),
        run_invalid("invalid_step", {"step": 0}),
        run_invalid("invalid_beta", {"beta1": 1.0}),
        run_invalid("invalid_dtype", {"dtype": "float64"}),
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(records, indent=2))
    print(f"apply_adam_w smoke: {sum(r['passed'] for r in records)}/{len(records)} passed")


if __name__ == "__main__":
    main()
