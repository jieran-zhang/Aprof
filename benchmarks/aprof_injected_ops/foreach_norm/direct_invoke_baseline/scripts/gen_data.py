#!/usr/bin/env python3
from __future__ import annotations
import json, math, random, struct
from pathlib import Path

SPEC = {
  "num_tensors": 32,
  "tensor_length": 256,
  "tile_length": 128,
  "blockdim": 4
}

def align_up(v, a): return ((v + a - 1) // a) * a

def main() -> int:
    root = Path.cwd(); data = root / "data"; build_sim = root / "build_sim"
    data.mkdir(exist_ok=True); build_sim.mkdir(exist_ok=True)
    n = SPEC["num_tensors"]; L = align_up(SPEC["tensor_length"], 8)
    tile = align_up(SPEC["tile_length"], 8); tile = min(tile, L)
    blockdim = SPEC["blockdim"]
    tpc = (n + blockdim - 1) // blockdim
    in_stride = align_up(n * L, 8); out_stride = align_up(n, 8)
    rng = random.Random(20260709)
    x = [rng.uniform(-3.0, 3.0) for _ in range(n * L)] + [0.0] * (in_stride - n * L)
    y = []
    for i in range(n):
        s = sum(v*v for v in x[i*L:(i+1)*L])
        y.append(math.sqrt(s))
    y = y + [0.0] * (out_stride - n)
    (data/"input.bin").write_bytes(struct.pack(f"{len(x)}f", *x))
    (data/"golden.bin").write_bytes(struct.pack(f"{len(y)}f", *y))
    (build_sim/"input.bin").write_bytes(struct.pack(f"{len(x)}f", *x))
    tiling = (n, L, tile, tile, tpc, in_stride, out_stride, blockdim, 0)
    (build_sim/"tiling.bin").write_bytes(struct.pack("9I", *tiling))
    op_config = {
        "kernel_name": "foreach_norm_kernel", "kernel_path": "./foreach_norm_kernel.o",
        "blockdim": blockdim, "mode": "ca", "device_id": 0,
        "magic": "RT_DEV_BINARY_MAGIC_ELF_AIVEC",
        "test_cases": [{"case_name": "baseline_case0", "param_desc": [
            {"param_type":"input","type":"float32","shape":[in_stride],"data_path":"./input.bin","name":"x"},
            {"param_type":"output","type":"float32","shape":[out_stride],"name":"y"},
            {"param_type":"tiling","tiling_data_size":36,"tiling_data_path":"./tiling.bin"}
        ]}]
    }
    (build_sim/"op_config.json").write_text(json.dumps(op_config, indent=2), encoding="utf-8")
    neutral = {"case_id":"baseline","kernel":"foreach_norm_kernel","dtype":"float32","shape":[n,L],"blockdim":blockdim,"tile_length":tile}
    (root/"case_metadata.json").write_text(json.dumps(neutral, indent=2), encoding="utf-8")
    print(json.dumps(neutral, indent=2)); return 0

if __name__ == "__main__":
    raise SystemExit(main())
