#!/usr/bin/env python3
from __future__ import annotations
import struct
from pathlib import Path

CHUNK_ELEMENTS = 1 << 20
FLOAT_BYTES = 4

def read_float_chunks(path: Path):
    with path.open("rb") as fp:
        while True:
            data = fp.read(CHUNK_ELEMENTS * FLOAT_BYTES)
            if not data:
                return
            if len(data) % FLOAT_BYTES != 0:
                raise SystemExit(f"unaligned float data in {path}: {len(data)} bytes")
            yield struct.unpack(f"{len(data) // FLOAT_BYTES}f", data)

def main() -> int:
    out = Path("build/output/output.bin")
    golden = Path("data/golden.bin")
    if not out.is_file():
        raise SystemExit(f"missing {out}")
    actual_bytes = out.stat().st_size
    expect_bytes = golden.stat().st_size
    if actual_bytes != expect_bytes:
        raise SystemExit(f"size mismatch: {actual_bytes // FLOAT_BYTES} vs {expect_bytes // FLOAT_BYTES}")
    max_err = 0.0
    bad = 0
    checked = 0
    for actual, expect in zip(read_float_chunks(out), read_float_chunks(golden)):
        for a, e in zip(actual, expect):
            err = abs(a - e)
            max_err = max(max_err, err)
            if err > 1e-4 + 1e-4 * abs(e):
                bad += 1
                if bad <= 5:
                    print(f"mismatch: actual={a} expected={e} err={err}")
            checked += 1
    print(f"checked={checked} bad={bad} max_err={max_err}")
    return 0 if bad == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
