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
    g.main_foreach_norm(
        variant_name="inject_tiling_unreasonable",
        injected_label="tiling_unreasonable",
        injected_problem="tileLength=8 使规约切成 32 次/tensor，每次规约的 vector 计算量过小，规约开销主导。",
        default_num_tensors=32,
        default_tensor_length=256,
        default_tile_length=8,
        default_blockdim=4,
        variant_flags=0,
    )
