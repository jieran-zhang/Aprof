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
    g.main_simple_op(
        op_name="layer_norm",
        kernel_name="layer_norm_kernel",
        variant_name="inject_redundant_vector",
        injected_label="redundant_cast_or_vector_copy",
        injected_problem="redundant Adds(+0) vector op wasting V cycles",
        default_output_elements=4096,
        default_tile_length=256,
        default_blockdim=4,
        variant_flags=0,
        golden_fn=lambda x, n: [(v - 1.0) / 2.0 for v in x[:n]],
    )
