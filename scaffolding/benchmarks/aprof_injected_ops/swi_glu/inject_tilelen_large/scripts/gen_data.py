#!/usr/bin/env python3
import argparse
import json
import math
import struct
from pathlib import Path

import numpy as np

OP_NAME = "swi_glu"
VARIANT_NAME = "inject_tilelen_large"
DEFAULT_OUTPUT_ELEMENTS = 8192
DEFAULT_TILE_LENGTH = 4096
DEFAULT_BLOCKDIM = 1
DEFAULT_TILE_NUM_MUL = 1
VARIANT_FLAGS = 0
INJECTED_LABEL = "tileLength_too_large"
INJECTED_PROBLEM = "tileLength 过大，导致 UB 压力变高、流水粒度过粗。"


def align_up(value, align):
    return ((value + align - 1) // align) * align


def golden(op, x, output_elements):
    if op == "fast_gelu":
        return (x[:output_elements] / (1.0 + np.exp(-1.702 * x[:output_elements]))).astype(np.float32)
    if op == "mish":
        y = x[:output_elements] * np.tanh(np.log1p(np.exp(x[:output_elements])))
        return y.astype(np.float32)
    if op == "swi_glu":
        a = x[:output_elements]
        b = x[output_elements:output_elements * 2]
        y = (a / (1.0 + np.exp(-a))) * b
        return y.astype(np.float32)
    raise ValueError(op)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-elements", type=int, default=DEFAULT_OUTPUT_ELEMENTS)
    parser.add_argument("--tile-length", type=int, default=DEFAULT_TILE_LENGTH)
    parser.add_argument("--blockdim", type=int, default=DEFAULT_BLOCKDIM)
    parser.add_argument("--tile-num-mul", type=int, default=DEFAULT_TILE_NUM_MUL)
    parser.add_argument("--seed", type=int, default=20260611)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    build_sim = root / "build_sim"
    data_dir.mkdir(exist_ok=True)
    build_sim.mkdir(exist_ok=True)

    output_elements = args.output_elements
    input_logical = output_elements * (2 if OP_NAME == "swi_glu" else 1)
    output_stride = align_up(output_elements, 8)
    input_stride = align_up(input_logical, 8)
    tile_length = max(8, align_up(args.tile_length, 8))
    tile_length = min(tile_length, max(8, input_stride))
    elems_per_core = math.ceil(output_elements / args.blockdim)
    base_tile_num = math.ceil(elems_per_core / tile_length) if tile_length else 0
    tile_num = max(1, base_tile_num * max(1, args.tile_num_mul))
    tail_length = output_elements % tile_length

    rng = np.random.default_rng(args.seed)
    logical_x = rng.uniform(-3.0, 3.0, size=input_logical).astype(np.float32)
    padded_x = np.zeros(input_stride, dtype=np.float32)
    padded_x[:input_logical] = logical_x
    y = golden(OP_NAME, logical_x, output_elements)
    padded_y = np.zeros(output_stride, dtype=np.float32)
    padded_y[:output_elements] = y

    padded_x.tofile(data_dir / "input.bin")
    padded_y.tofile(data_dir / "golden.bin")
    padded_x.tofile(build_sim / "input.bin")

    tiling = (input_logical, output_elements, input_stride, output_stride, elems_per_core,
              tile_length, align_up(tile_length, 8), tile_num, tail_length, VARIANT_FLAGS)
    (build_sim / "tiling.bin").write_bytes(struct.pack("10I", *tiling))

    op_config = {
        "kernel_name": f"{OP_NAME}_kernel",
        "kernel_path": f"./{OP_NAME}_kernel.o",
        "blockdim": args.blockdim,
        "mode": "ca",
        "device_id": 0,
        "magic": "RT_DEV_BINARY_MAGIC_ELF_AIVEC",
        "test_cases": [{
            "case_name": f"{OP_NAME}_{VARIANT_NAME}_case0",
            "param_desc": [
                {"param_type": "input", "type": "float32", "shape": [input_stride], "data_path": "./input.bin", "name": "x"},
                {"param_type": "output", "type": "float32", "shape": [output_stride], "name": "y"},
                {"param_type": "tiling", "tiling_data_size": 40, "tiling_data_path": "./tiling.bin"},
            ],
        }],
    }
    (build_sim / "op_config.json").write_text(json.dumps(op_config, indent=2), encoding="utf-8")

    metadata = {
        "op_name": OP_NAME,
        "variant": VARIANT_NAME,
        "injected_label": INJECTED_LABEL,
        "injected_problem": INJECTED_PROBLEM,
        "output_elements": output_elements,
        "input_stride": input_stride,
        "output_stride": output_stride,
        "blockdim": args.blockdim,
        "tile_length": tile_length,
        "tile_num": tile_num,
        "tail_length": tail_length,
        "tile_num_multiplier": args.tile_num_mul,
        "variant_flags": VARIANT_FLAGS,
    }
    (root / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    (build_sim / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
