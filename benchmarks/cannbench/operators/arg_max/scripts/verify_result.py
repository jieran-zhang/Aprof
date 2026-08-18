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
    expected = np.fromfile(metadata["golden"], dtype=np.int64)
    actual = np.fromfile(metadata["output"], dtype=np.int64)
    size_ok = actual.size == metadata["output_numel"] == expected.size
    equal = size_ok and np.array_equal(actual, expected)
    mismatches = int(np.count_nonzero(actual != expected)) if size_ok else max(actual.size, expected.size)
    first_mismatch = None
    if size_ok and mismatches:
        first_mismatch = int(np.flatnonzero(actual != expected)[0])
    result = {
        "case_id": metadata["case_id"],
        "shape": metadata["shape"],
        "dtype": metadata["dtype"],
        "attrs": metadata["attrs"],
        "output_shape": metadata["output_shape"],
        "output_numel": metadata["output_numel"],
        "mismatches": mismatches,
        "first_mismatch": first_mismatch,
        "bitwise_equal": bool(equal),
        "passed": bool(equal),
    }
    (metadata_path.parent / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    if not equal:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
