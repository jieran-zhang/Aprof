#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True)
    args = parser.parse_args()
    metadata_path = Path(args.metadata)
    metadata = json.loads(metadata_path.read_text())
    expected_y = np.fromfile(metadata["golden_y"], dtype=np.int8)
    actual_y = np.fromfile(metadata["output_y"], dtype=np.int8)
    y_size_ok = expected_y.size == actual_y.size == metadata["numel"]
    if y_size_ok:
        y_diff = np.abs(actual_y.astype(np.int16) - expected_y.astype(np.int16))
        y_max_error = int(y_diff.max(initial=0))
        y_bad = int(np.count_nonzero(y_diff > 1))
    else:
        y_max_error, y_bad = 255, max(expected_y.size, actual_y.size)

    expected_scale = np.fromfile(metadata["golden_scale"], dtype=np.float32)
    actual_scale = np.fromfile(metadata["output_scale"], dtype=np.float32)
    scale_size_ok = expected_scale.size == actual_scale.size == metadata["token_count"]
    special_ok = False
    mere = float("inf")
    mare = float("inf")
    if scale_size_ok:
        special_ok = bool(
            np.array_equal(np.isnan(actual_scale), np.isnan(expected_scale))
            and np.array_equal(np.isposinf(actual_scale), np.isposinf(expected_scale))
            and np.array_equal(np.isneginf(actual_scale), np.isneginf(expected_scale))
        )
        finite = np.isfinite(actual_scale) & np.isfinite(expected_scale)
        if finite.any():
            rel = np.abs(actual_scale[finite] - expected_scale[finite]) / (np.abs(expected_scale[finite]) + 1e-7)
            mere = float(rel.mean(dtype=np.float64))
            mare = float(rel.max(initial=0))
        else:
            mere = mare = 0.0
    scale_threshold = 2 ** -13
    scale_passed = bool(special_ok and mere < scale_threshold and mare < 10 * scale_threshold)
    passed = bool(y_size_ok and y_bad == 0 and scale_passed)
    result = {
        "case_id": metadata["case_id"],
        "shape": metadata["shape"],
        "dtype": metadata["dtype"],
        "attrs": {},
        "numel": metadata["numel"],
        "token_count": metadata["token_count"],
        "y_max_abs_error": y_max_error,
        "y_elements_over_tolerance": y_bad,
        "y_tolerance": 1,
        "scale_mere": mere,
        "scale_mare": mare,
        "scale_threshold": scale_threshold,
        "scale_special_values_match": special_ok,
        "passed": passed,
    }
    (metadata_path.parent / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
