#!/usr/bin/env python3
from __future__ import annotations
import json, math, random, struct
from pathlib import Path

SPEC = {
  "m": 128, "n": 128, "k": 64,
  "tile_m": 8, "tile_n": 8,
  "blockdim": 4
}

def align_up(v, a): return ((v + a - 1) // a) * a

def matmul_golden(a, b, m, n, k):
    out = [0.0] * (m * n)
    for i in range(m):
        for j in range(n):
            s = 0.0
            for p in range(k):
                s += a[i * k + p] * b[p * n + j]
            out[i * n + j] = s
    return out

def main() -> int:
    root = Path.cwd(); data = root / "data"; build_sim = root / "build_sim"
    data.mkdir(exist_ok=True); build_sim.mkdir(exist_ok=True)
    m = align_up(SPEC["m"], 8); n = align_up(SPEC["n"], 8); k = align_up(SPEC["k"], 8)
    tile_m = align_up(SPEC["tile_m"], 8); tile_n = align_up(SPEC["tile_n"], 8)
    blockdim = SPEC["blockdim"]
    a_elems, b_elems, c_elems = m*k, k*n, m*n
    in_stride = align_up(a_elems + b_elems, 8); out_stride = align_up(c_elems, 8)
    rows_per_core = (m + blockdim - 1) // blockdim
    rng = random.Random(20260709)
    a = [rng.uniform(-1.0, 1.0) for _ in range(a_elems)]
    b = [rng.uniform(-1.0, 1.0) for _ in range(b_elems)]
    c = matmul_golden(a, b, m, n, k)
    xin = [0.0]*in_stride; xin[:a_elems]=a; xin[a_elems:a_elems+b_elems]=b
    yout = [0.0]*out_stride; yout[:c_elems]=c
    (data/"input.bin").write_bytes(struct.pack(f"{len(xin)}f", *xin))
    (data/"golden.bin").write_bytes(struct.pack(f"{len(yout)}f", *yout))
    (build_sim/"input.bin").write_bytes(struct.pack(f"{len(xin)}f", *xin))
    tiling = (m,n,k,tile_m,tile_n,tile_m,tile_n,rows_per_core,in_stride,out_stride,blockdim,0)
    (build_sim/"tiling.bin").write_bytes(struct.pack("12I", *tiling))
    op_config = {
        "kernel_name": "matmul_kernel", "kernel_path": "./matmul_kernel.o",
        "blockdim": blockdim, "mode": "ca", "device_id": 0,
        "magic": "RT_DEV_BINARY_MAGIC_ELF_AIVEC",
        "test_cases": [{"case_name": "op_0003_case0", "param_desc": [
            {"param_type":"input","type":"float32","shape":[in_stride],"data_path":"./input.bin","name":"ab"},
            {"param_type":"output","type":"float32","shape":[out_stride],"name":"c"},
            {"param_type":"tiling","tiling_data_size":48,"tiling_data_path":"./tiling.bin"}
        ]}]
    }
    (build_sim/"op_config.json").write_text(json.dumps(op_config, indent=2), encoding="utf-8")
    neutral = {"case_id":"op_0003","kernel":"matmul_kernel","dtype":"float32","shape":[m,n,k],"blockdim":blockdim,"tile_m":tile_m,"tile_n":tile_n}
    (root/"case_metadata.json").write_text(json.dumps(neutral, indent=2), encoding="utf-8")
    print(json.dumps(neutral, indent=2)); return 0

if __name__ == "__main__":
    raise SystemExit(main())
