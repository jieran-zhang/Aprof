#!/usr/bin/env python3
"""Shared stdlib-only data generator for AProf inject benchmark cases."""
from __future__ import annotations

import argparse
import json
import math
import random
import struct
from pathlib import Path
from typing import Callable


def align_up(value: int, align: int) -> int:
    return ((value + align - 1) // align) * align


def fast_gelu_golden(x: list[float]) -> list[float]:
    return [v / (1.0 + math.exp(-1.702 * v)) for v in x]


def mish_golden(x: list[float]) -> list[float]:
    out = []
    for v in x:
        out.append(v * math.tanh(math.log1p(math.exp(v))))
    return out


def swi_glu_golden(x: list[float], output_elements: int) -> list[float]:
    out = []
    for i in range(output_elements):
        a = x[i]
        b = x[output_elements + i]
        out.append((a / (1.0 + math.exp(-a))) * b)
    return out


GOLDEN_FUNCS: dict[str, Callable] = {
    "fast_gelu": lambda x, n: fast_gelu_golden(x[:n]),
    "mish": lambda x, n: mish_golden(x[:n]),
    "swi_glu": swi_glu_golden,
}


def write_floats(path: Path, values: list[float]) -> None:
    path.write_bytes(struct.pack(f"{len(values)}f", *values))


def main_with_config(
    *,
    op_name: str,
    variant_name: str,
    injected_label: str,
    injected_problem: str,
    default_output_elements: int,
    default_tile_length: int,
    default_blockdim: int,
    default_tile_num_mul: int,
    variant_flags: int,
) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-elements", type=int, default=default_output_elements)
    parser.add_argument("--tile-length", type=int, default=default_tile_length)
    parser.add_argument("--blockdim", type=int, default=default_blockdim)
    parser.add_argument("--tile-num-mul", type=int, default=default_tile_num_mul)
    parser.add_argument("--seed", type=int, default=20260611)
    args = parser.parse_args()

    root = Path.cwd()
    data_dir = root / "data"
    build_sim = root / "build_sim"
    data_dir.mkdir(exist_ok=True)
    build_sim.mkdir(exist_ok=True)

    output_elements = args.output_elements
    input_logical = output_elements * (2 if op_name == "swi_glu" else 1)
    output_stride = align_up(output_elements, 8)
    input_stride = align_up(input_logical, 8)
    tile_length = max(8, align_up(args.tile_length, 8))
    tile_length = min(tile_length, max(8, input_stride))
    elems_per_core = math.ceil(output_elements / args.blockdim)
    base_tile_num = math.ceil(elems_per_core / tile_length) if tile_length else 0
    tile_num = max(1, base_tile_num * max(1, args.tile_num_mul))
    tail_length = output_elements % tile_length

    rng = random.Random(args.seed)
    logical_x = [rng.uniform(-3.0, 3.0) for _ in range(input_logical)]
    padded_x = [0.0] * input_stride
    padded_x[:input_logical] = logical_x
    golden_fn = GOLDEN_FUNCS[op_name]
    y = golden_fn(logical_x, output_elements)
    padded_y = [0.0] * output_stride
    padded_y[:output_elements] = y

    write_floats(data_dir / "input.bin", padded_x)
    write_floats(data_dir / "golden.bin", padded_y)
    write_floats(build_sim / "input.bin", padded_x)

    tiling = (
        input_logical,
        output_elements,
        input_stride,
        output_stride,
        elems_per_core,
        tile_length,
        align_up(tile_length, 8),
        tile_num,
        tail_length,
        variant_flags,
    )
    (build_sim / "tiling.bin").write_bytes(struct.pack("10I", *tiling))

    op_config = {
        "kernel_name": f"{op_name}_kernel",
        "kernel_path": f"./{op_name}_kernel.o",
        "blockdim": args.blockdim,
        "mode": "ca",
        "device_id": 0,
        "magic": "RT_DEV_BINARY_MAGIC_ELF_AIVEC",
        "test_cases": [
            {
                "case_name": f"{op_name}_{variant_name}_case0",
                "param_desc": [
                    {
                        "param_type": "input",
                        "type": "float32",
                        "shape": [input_stride],
                        "data_path": "./input.bin",
                        "name": "x",
                    },
                    {"param_type": "output", "type": "float32", "shape": [output_stride], "name": "y"},
                    {"param_type": "tiling", "tiling_data_size": 40, "tiling_data_path": "./tiling.bin"},
                ],
            }
        ],
    }
    (build_sim / "op_config.json").write_text(json.dumps(op_config, indent=2), encoding="utf-8")

    metadata = {
        "op_name": op_name,
        "variant": variant_name,
        "injected_label": injected_label,
        "injected_problem": injected_problem,
        "output_elements": output_elements,
        "input_stride": input_stride,
        "output_stride": output_stride,
        "blockdim": args.blockdim,
        "tile_length": tile_length,
        "tile_num": tile_num,
        "tail_length": tail_length,
        "tile_num_multiplier": args.tile_num_mul,
        "variant_flags": variant_flags,
    }
    (root / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    (build_sim / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
