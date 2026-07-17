#!/usr/bin/env python3
from __future__ import annotations
import json, math, random, struct
from pathlib import Path

SPEC = {
  "output_elements": 2048,
  "blockdim": 4,
  "tile_length": 256,
  "tile_num_mul": 1
}

def align_up(value: int, align: int) -> int:
    return ((value + align - 1) // align) * align

def main() -> int:
    root = Path.cwd()
    data = root / "data"
    build_sim = root / "build_sim"
    data.mkdir(exist_ok=True)
    build_sim.mkdir(exist_ok=True)

    n = int(SPEC["output_elements"])
    stride = align_up(n, 8)
    blockdim = int(SPEC["blockdim"])
    tile_len = align_up(int(SPEC["tile_length"]), 8)
    elems_per_core = (n + blockdim - 1) // blockdim
    base_tile_num = (elems_per_core + tile_len - 1) // tile_len
    tile_num = max(1, base_tile_num * int(SPEC["tile_num_mul"]))
    rng = random.Random(20260709)
    x = [rng.uniform(-3.0, 3.0) for _ in range(n)] + [0.0] * (stride - n)
    y = [v * v / (1.0 + math.exp(-1.702 * v)) for v in x[:n]] + [0.0] * (stride - n)
    blob_x = struct.pack(f"{len(x)}f", *x)
    blob_y = struct.pack(f"{len(y)}f", *y)
    (data / "input.bin").write_bytes(blob_x)
    (data / "golden.bin").write_bytes(blob_y)
    (build_sim / "input.bin").write_bytes(blob_x)
    tiling = (n, n, stride, stride, elems_per_core, tile_len, align_up(tile_len, 8), tile_num, n % tile_len, 0)
    (build_sim / "tiling.bin").write_bytes(struct.pack("10I", *tiling))
    shape_in = stride
    shape_out = stride

    op_config = {
        "kernel_name": "gelu_mul_kernel",
        "kernel_path": "./gelu_mul_kernel.o",
        "blockdim": blockdim,
        "mode": "ca",
        "device_id": 0,
        "magic": "RT_DEV_BINARY_MAGIC_ELF_AIVEC",
        "test_cases": [{
            "case_name": "op_0004_case0",
            "param_desc": [
                {"param_type": "input", "type": "float32", "shape": [shape_in], "data_path": "./input.bin", "name": "x"},
                {"param_type": "output", "type": "float32", "shape": [shape_out], "name": "y"},
                {"param_type": "tiling", "tiling_data_size": 40, "tiling_data_path": "./tiling.bin"}
            ]
        }]
    }
    (build_sim / "op_config.json").write_text(json.dumps(op_config, indent=2), encoding="utf-8")
    neutral = {
        "case_id": "op_0004",
        "kernel": "gelu_mul_kernel",
        "dtype": "float32",
        "shape": [n],
        "blockdim": blockdim,
        "tile_length": tile_len
    }
    (root / "case_metadata.json").write_text(json.dumps(neutral, indent=2), encoding="utf-8")
    print(json.dumps(neutral, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
