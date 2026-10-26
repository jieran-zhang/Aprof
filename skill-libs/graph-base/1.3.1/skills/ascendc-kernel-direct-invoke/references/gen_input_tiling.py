"""Generate input.bin and tiling.bin for `msprof op simulator --config`.

This is a *template*. Replace the body of `gen_input_for_<op>` /
`gen_tiling_for_<op>` for each new operator. The ReduceSum example below is
proven against benchmarks/reference_ops/reduce_sum/.

Usage examples
--------------
# ReduceSum, M=1 N=8 fp32, blockdim=1
python3 gen_input_tiling.py --op reduce_sum --m 1 --n 8 --dtype fp32 --cores 1

# Generic: just call your custom function
python3 gen_input_tiling.py --op <your_op> ...
"""

from __future__ import annotations
import argparse
import struct
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# Per-op generators
# ---------------------------------------------------------------------------

def gen_reduce_sum(out_dir: Path, m: int, n: int, dtype: str, cores: int) -> None:
    """Reproduces benchmarks/reference_ops/reduce_sum tiling layout."""
    if dtype != "fp32":
        raise SystemExit(f"reduce_sum sample only supports fp32, got {dtype}")
    elems_per_blk = 32 // 4  # 32 bytes block / 4 bytes per fp32 = 8

    def align_up(v: int, a: int) -> int:
        return (v + a - 1) // a * a

    input_stride_n = align_up(n, elems_per_blk)
    rows_per_core = (m + cores - 1) // cores
    per_loop_n = min(n, 240 * 1024 // 4)  # 240 KB usable UB / 4 B
    per_loop_n = max(elems_per_blk, (per_loop_n // elems_per_blk) * elems_per_blk)
    per_loop_n = min(per_loop_n, n)
    per_loop_n_aligned = align_up(per_loop_n, elems_per_blk)
    loop_count = (n + per_loop_n - 1) // per_loop_n
    tail_n = n % per_loop_n

    # Input data: linear ramp, easy to verify by eye
    np.arange(m * n, dtype=np.float32).tofile(out_dir / "input.bin")
    # 8 uint32 to match ReduceSumTilingData in op_kernel/reduce_sum_tiling.h
    open(out_dir / "tiling.bin", "wb").write(
        struct.pack(
            "8I",
            m, n, input_stride_n, rows_per_core,
            per_loop_n, per_loop_n_aligned, loop_count, tail_n,
        )
    )
    print(
        f"[reduce_sum] input.bin: {m*n*4} B; tiling: "
        f"m={m} n={n} stride={input_stride_n} rowsPerCore={rows_per_core} "
        f"perLoopN={per_loop_n} aligned={per_loop_n_aligned} loop={loop_count} tail={tail_n}"
    )


# Register new ops here.
GENERATORS = {
    "reduce_sum": gen_reduce_sum,
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--op", required=True, help=f"operator name; one of {list(GENERATORS)}")
    parser.add_argument("--out", default="build_sim", help="output dir (default: build_sim)")
    parser.add_argument("--m", type=int, default=1)
    parser.add_argument("--n", type=int, default=8)
    parser.add_argument("--dtype", default="fp32")
    parser.add_argument("--cores", type=int, default=1)
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.op not in GENERATORS:
        raise SystemExit(
            f"[ERROR] No input/tiling generator registered for op={args.op!r}. "
            f"Add a function to this script (see gen_reduce_sum as template)."
        )

    GENERATORS[args.op](out_dir, m=args.m, n=args.n, dtype=args.dtype, cores=args.cores)
    print(f"[done] Wrote {out_dir/'input.bin'} and {out_dir/'tiling.bin'}")


if __name__ == "__main__":
    main()
