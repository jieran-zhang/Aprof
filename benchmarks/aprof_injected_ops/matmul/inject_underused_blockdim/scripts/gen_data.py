#!/usr/bin/env python3
import os
import sys
from pathlib import Path


def _bootstrap_common() -> None:
    candidates = []
    if os.environ.get("APROF_INJECT_COMMON"):
        candidates.append(Path(os.environ["APROF_INJECT_COMMON"]))
    here = Path(__file__).resolve()
    candidates.extend([here.parents[2] / "common", here.parents[3] / "common"])
    for cand in candidates:
        if (cand / "inject_gen_data.py").is_file():
            sys.path.insert(0, str(cand))
            return
    raise SystemExit("[ERROR] cannot locate benchmarks/aprof_injected_ops/common")


_bootstrap_common()
import inject_gen_data as g

if __name__ == "__main__":
    g.main_matmul(
        variant_name="inject_underused_blockdim",
        injected_label="underused_blockdim",
        injected_problem="blockDim 低于可用核数，AI Core 核利用率低。",
        default_m=128,
        default_n=128,
        default_k=64,
        default_tile_m=32,
        default_tile_n=32,
        default_blockdim=1,
        variant_flags=0,
    )
