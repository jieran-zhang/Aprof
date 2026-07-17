#!/usr/bin/env python3
from __future__ import annotations
import json, struct
from pathlib import Path

def read_floats(path: Path):
    data = path.read_bytes()
    return list(struct.unpack(f"{len(data)//4}f", data))

def main() -> int:
    meta = json.loads(Path("case_metadata.json").read_text(encoding="utf-8"))
    tile = int(meta.get("tile_length", 256))
    actual = read_floats(Path("build/output/output.bin"))
    expect = read_floats(Path("data/golden.bin"))
    n = min(len(actual), len(expect), int(meta["shape"][0]) if meta.get("shape") else len(expect))
    bad = 0
    max_err = 0.0
    for off in range(0, n, tile):
        err = abs(actual[off] - expect[off])
        max_err = max(max_err, err)
        if err > 1e-3 + 1e-3 * abs(expect[off]):
            bad += 1
            if bad <= 5:
                print(f"mismatch tile@{off}: actual={actual[off]} expected={expect[off]}")
    print(f"tile_head_checked={(n + tile - 1)//tile} bad={bad} max_err={max_err}")
    return 0 if bad == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
