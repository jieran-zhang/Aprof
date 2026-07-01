#!/usr/bin/env python3
"""Generate input.bin / tiling.bin for FastGelu msprof simulator --config mode."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import numpy as np

TILE_LENGTH = 4096


def compute_tiling(total_length: int, core_num: int) -> dict[str, int]:
    total_tiles = (total_length + TILE_LENGTH - 1) // TILE_LENGTH
    tiles_per_core = (total_tiles + core_num - 1) // core_num
    block_num = (total_tiles + tiles_per_core - 1) // tiles_per_core
    num_per_core = tiles_per_core * TILE_LENGTH
    tail_num_last_core = total_length - num_per_core * (block_num - 1)
    return {
        "totalLength": total_length,
        "numPerCore": num_per_core,
        "tailNumLastCore": tail_num_last_core,
        "blockNum": block_num,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--m", type=int, default=8)
    parser.add_argument("--n", type=int, default=2048)
    parser.add_argument("--cores", type=int, default=1)
    parser.add_argument("--out", default="build_sim")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    total_length = args.m * args.n
    tiling = compute_tiling(total_length, args.cores)

    rng = np.random.default_rng(42)
    rng.uniform(-3.0, 3.0, size=total_length).astype(np.float32).tofile(out_dir / "input.bin")
    open(out_dir / "tiling.bin", "wb").write(
        struct.pack(
            "4I",
            tiling["totalLength"],
            tiling["numPerCore"],
            tiling["tailNumLastCore"],
            tiling["blockNum"],
        )
    )
    print(f"[INFO] totalLength={total_length}, tiling={tiling}")
    print(f"[done] Wrote {out_dir/'input.bin'} and {out_dir/'tiling.bin'}")


if __name__ == "__main__":
    main()
