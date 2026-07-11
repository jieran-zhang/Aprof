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
        op_name="gelu_mul",
        variant_name="inject_excessive_barrier",
        injected_label="excessive_pipe_barrier",
        injected_problem="在每个 tile 边界插入双 PipeBarrier<PIPE_ALL>，强制流水 drain，破坏 MTE2→V→MTE3 overlap。",
        default_output_elements=16384,
        default_tile_length=256,
        default_blockdim=4,
        default_tile_num_mul=1,
        variant_flags=0,
    )
