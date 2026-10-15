#!/usr/bin/env python3
from __future__ import annotations
import json, math, random, shutil, struct
from array import array
from pathlib import Path

SPEC = {
  "shape": [4096, 4096],
  "blockdim": 1,
  "tile_length": 256,
  "tile_num_mul": 1
}

CHUNK_ELEMENTS = 1 << 20

def align_up(value: int, align: int) -> int:
    return ((value + align - 1) // align) * align

def product(values: list[int]) -> int:
    result = 1
    for value in values:
        result *= value
    return result

def write_data(input_path: Path, golden_path: Path, n: int, stride: int) -> None:
    rng = random.Random(20260709)
    remaining = n
    with input_path.open("wb") as input_fp, golden_path.open("wb") as golden_fp:
        while remaining:
            count = min(CHUNK_ELEMENTS, remaining)
            x = array("f", (rng.uniform(-3.0, 3.0) for _ in range(count)))
            y = array("f", (v / (1.0 + math.exp(-1.702 * v)) for v in x))
            input_fp.write(x.tobytes())
            golden_fp.write(y.tobytes())
            remaining -= count
        padding = stride - n
        if padding:
            zeros = array("f", [0.0]) * padding
            input_fp.write(zeros.tobytes())
            golden_fp.write(zeros.tobytes())

def main() -> int:
    root = Path.cwd()
    data = root / "data"
    build_sim = root / "build_sim"
    data.mkdir(exist_ok=True)
    build_sim.mkdir(exist_ok=True)
    shape = [int(dim) for dim in SPEC["shape"]]
    n = product(shape)
    stride = align_up(n, 8)
    blockdim = int(SPEC["blockdim"])
    tile_len = align_up(int(SPEC["tile_length"]), 8)
    elems_per_core = (n + blockdim - 1) // blockdim
    base_tile_num = (elems_per_core + tile_len - 1) // tile_len
    tile_num = max(1, base_tile_num * int(SPEC["tile_num_mul"]))
    write_data(data / "input.bin", data / "golden.bin", n, stride)
    shutil.copyfile(data / "input.bin", build_sim / "input.bin")
    tiling = (n, n, stride, stride, elems_per_core, tile_len, align_up(tile_len, 8), tile_num, n % tile_len, 0)
    (build_sim / "tiling.bin").write_bytes(struct.pack("10I", *tiling))
    param_shape = shape if n == stride else [stride]
    op_config = {
        "kernel_name": "fast_gelu_kernel",
        "kernel_path": "./fast_gelu_kernel.o",
        "blockdim": blockdim,
        "mode": "ca",
        "device_id": 0,
        "magic": "RT_DEV_BINARY_MAGIC_ELF_AIVEC",
        "test_cases": [{
            "case_name": "fast_gelu_base_case0",
            "param_desc": [
                {"param_type": "input", "type": "float32", "shape": param_shape, "data_path": "./input.bin", "name": "x"},
                {"param_type": "output", "type": "float32", "shape": param_shape, "name": "y"},
                {"param_type": "tiling", "tiling_data_size": 40, "tiling_data_path": "./tiling.bin"}
            ]
        }]
    }
    (build_sim / "op_config.json").write_text(json.dumps(op_config, indent=2), encoding="utf-8")
    neutral = {"case_id": "fast_gelu_base", "kernel": "fast_gelu_kernel", "dtype": "float32", "shape": shape, "blockdim": blockdim, "tile_length": tile_len}
    (root / "case_metadata.json").write_text(json.dumps(neutral, indent=2), encoding="utf-8")
    print(json.dumps(neutral, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
