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
    g.main_with_config(
        op_name="fast_gelu",
        variant_name="inject_tilelen_large",
        injected_label="tileLength_too_large",
        injected_problem="tileLength 过大，导致 UB 压力变高、流水粒度过粗。",
        default_output_elements=8192,
        default_tile_length=4096,
        default_blockdim=1,
        default_tile_num_mul=1,
        variant_flags=0,
    )
