#!/usr/bin/env python3
from __future__ import annotations
import math, struct
from pathlib import Path

def read_floats(path: Path):
    data = path.read_bytes()
    return struct.unpack(f"{len(data)//4}f", data)

def main() -> int:
    out = Path("build/output/output.bin")
    golden = Path("data/golden.bin")
    if not out.is_file():
        raise SystemExit(f"missing {out}")
    actual = read_floats(out)
    expect = read_floats(golden)
    if len(actual) != len(expect):
        raise SystemExit(f"size mismatch: {len(actual)} vs {len(expect)}")
    max_err = 0.0
    bad = 0
    for a, e in zip(actual, expect):
        err = abs(a - e)
        max_err = max(max_err, err)
        if err > 1e-4 + 1e-4 * abs(e):
            bad += 1
            if bad <= 5:
                print(f"mismatch: actual={a} expected={e} err={err}")
    print(f"checked={len(actual)} bad={bad} max_err={max_err}")
    return 0 if bad == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
