#!/usr/bin/env python3
"""Shared stdlib-only data generator for AProf inject benchmark cases."""
from __future__ import annotations

import argparse
import json
import math
import os
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


def gelu_mul_golden(x: list[float]) -> list[float]:
    # y = x * fast_gelu(x) = x * (x / (1 + exp(-1.702 * x)))
    return [v * v / (1.0 + math.exp(-1.702 * v)) for v in x]


def fast_gelu_grad_golden(x: list[float], grad: list[float]) -> list[float]:
    # y = x / (1 + exp(-s x)), s = 1.702
    # dy/dx = (1 + exp(-s x) * (1 - s x)) / (1 + exp(-s x))^2
    s = 1.702
    out = []
    for v, g in zip(x, grad):
        e = math.exp(-s * v)
        denom = (1.0 + e) ** 2
        dydx = (1.0 + e * (1.0 - s * v)) / denom
        out.append(g * dydx)
    return out


def foreach_norm_golden(x: list[float], num_tensors: int, tensor_length: int) -> list[float]:
    out = []
    for i in range(num_tensors):
        s = 0.0
        base = i * tensor_length
        for j in range(tensor_length):
            v = x[base + j]
            s += v * v
        out.append(math.sqrt(s))
    return out


def matmul_golden(a: list[float], b: list[float], m: int, n: int, k: int) -> list[float]:
    """C[M,N] = A[M,K] * B[K,N], row-major."""
    out = [0.0] * (m * n)
    for i in range(m):
        for j in range(n):
            s = 0.0
            for p in range(k):
                s += a[i * k + p] * b[p * n + j]
            out[i * n + j] = s
    return out


def conv2d_golden(x: list[float], w: list[float], n: int, c: int, h: int, wd: int,
                  oc: int, kh: int, kw: int, stride: int, pad: int) -> list[float]:
    """Simple conv2d NCHW, output = [N, OC, OH, OW]."""
    oh = (h + 2 * pad - kh) // stride + 1
    ow = (wd + 2 * pad - kw) // stride + 1
    out = [0.0] * (n * oc * oh * ow)
    for ni in range(n):
        for oci in range(oc):
            for ohi in range(oh):
                for owi in range(ow):
                    s = 0.0
                    for ci in range(c):
                        for ki in range(kh):
                            for kj in range(kw):
                                ih = ohi * stride - pad + ki
                                iw = owi * stride - pad + kj
                                if 0 <= ih < h and 0 <= iw < wd:
                                    xv = x[((ni * c + ci) * h + ih) * wd + iw]
                                    wv = w[((oci * c + ci) * kh + ki) * kw + kj]
                                    s += xv * wv
                    out[((ni * oc + oci) * oh + ohi) * ow + owi] = s
    return out


def layer_norm_golden(x: list[float], num_rows: int, feat_len: int, eps: float = 1e-5) -> list[float]:
    """y[i,j] = (x[i,j] - mean_i) / sqrt(var_i + eps), per-row normalize."""
    out = [0.0] * (num_rows * feat_len)
    for i in range(num_rows):
        base = i * feat_len
        mean = sum(x[base:base + feat_len]) / feat_len
        var = sum((v - mean) ** 2 for v in x[base:base + feat_len]) / feat_len
        std = math.sqrt(var + eps)
        for j in range(feat_len):
            out[base + j] = (x[base + j] - mean) / std
    return out


def topk_golden(x: list[float], num_rows: int, row_len: int, k: int) -> list[float]:
    """Top-K largest values per row, sorted descending."""
    out = [0.0] * (num_rows * k)
    for i in range(num_rows):
        base = i * row_len
        row = sorted(x[base:base + row_len], reverse=True)
        for j in range(k):
            out[i * k + j] = row[j]
    return out


def max_pool_golden(x: list[float], num_channels: int, hw: int, kh: int, kw: int,
                    stride: int) -> list[float]:
    """1D-flattened max pool: each channel is a 1D row of length hw, pool window kh*kw flattened to kw."""
    ohw = (hw - kw) // stride + 1
    out = [0.0] * (num_channels * ohw)
    for c in range(num_channels):
        base = c * hw
        for i in range(ohw):
            mv = x[base + i * stride]
            for j in range(1, kw):
                mv = max(mv, x[base + i * stride + j])
            out[c * ohw + i] = mv
    return out


GOLDEN_FUNCS: dict[str, Callable] = {
    "fast_gelu": lambda x, n: fast_gelu_golden(x[:n]),
    "mish": lambda x, n: mish_golden(x[:n]),
    "swi_glu": swi_glu_golden,
    "gelu_mul": lambda x, n: gelu_mul_golden(x[:n]),
    "fast_gelu_grad": lambda x, n: fast_gelu_grad_golden(x[:n], x[:n]),  # grad = x for benchmark
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
        "mode": os.environ.get("MSPROF_OP_CONFIG_MODE", "ca"),
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


def main_foreach_norm(
    *,
    variant_name: str,
    injected_label: str,
    injected_problem: str,
    default_num_tensors: int,
    default_tensor_length: int,
    default_tile_length: int,
    default_blockdim: int,
    variant_flags: int,
) -> None:
    """Generator for foreach_norm: N tensors of length L -> N L2-norm scalars."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-tensors", type=int, default=default_num_tensors)
    parser.add_argument("--tensor-length", type=int, default=default_tensor_length)
    parser.add_argument("--tile-length", type=int, default=default_tile_length)
    parser.add_argument("--blockdim", type=int, default=default_blockdim)
    parser.add_argument("--seed", type=int, default=20260611)
    args = parser.parse_args()

    root = Path.cwd()
    data_dir = root / "data"
    build_sim = root / "build_sim"
    data_dir.mkdir(exist_ok=True)
    build_sim.mkdir(exist_ok=True)

    num_tensors = max(1, args.num_tensors)
    tensor_length = max(8, align_up(args.tensor_length, 8))
    tile_length = max(8, align_up(args.tile_length, 8))
    tile_length = min(tile_length, tensor_length)

    total_elems = num_tensors * tensor_length
    input_stride = align_up(total_elems, 8)
    output_stride = align_up(num_tensors, 8)
    tensors_per_core = math.ceil(num_tensors / args.blockdim)

    rng = random.Random(args.seed)
    logical_x = [rng.uniform(-3.0, 3.0) for _ in range(total_elems)]
    padded_x = [0.0] * input_stride
    padded_x[:total_elems] = logical_x
    y = foreach_norm_golden(logical_x, num_tensors, tensor_length)
    padded_y = [0.0] * output_stride
    padded_y[:num_tensors] = y

    write_floats(data_dir / "input.bin", padded_x)
    write_floats(data_dir / "golden.bin", padded_y)
    write_floats(build_sim / "input.bin", padded_x)

    # AprofForeachTilingData: 9 uint32 fields = 36 bytes
    tiling = (
        num_tensors,
        tensor_length,
        tile_length,
        align_up(tile_length, 8),
        tensors_per_core,
        input_stride,
        output_stride,
        args.blockdim,
        variant_flags,
    )
    (build_sim / "tiling.bin").write_bytes(struct.pack("9I", *tiling))

    op_config = {
        "kernel_name": "foreach_norm_kernel",
        "kernel_path": "./foreach_norm_kernel.o",
        "blockdim": args.blockdim,
        "mode": os.environ.get("MSPROF_OP_CONFIG_MODE", "ca"),
        "device_id": 0,
        "magic": "RT_DEV_BINARY_MAGIC_ELF_AIVEC",
        "test_cases": [
            {
                "case_name": f"foreach_norm_{variant_name}_case0",
                "param_desc": [
                    {
                        "param_type": "input",
                        "type": "float32",
                        "shape": [input_stride],
                        "data_path": "./input.bin",
                        "name": "x",
                    },
                    {"param_type": "output", "type": "float32", "shape": [output_stride], "name": "y"},
                    {"param_type": "tiling", "tiling_data_size": 36, "tiling_data_path": "./tiling.bin"},
                ],
            }
        ],
    }
    (build_sim / "op_config.json").write_text(json.dumps(op_config, indent=2), encoding="utf-8")

    metadata = {
        "op_name": "foreach_norm",
        "variant": variant_name,
        "injected_label": injected_label,
        "injected_problem": injected_problem,
        "num_tensors": num_tensors,
        "tensor_length": tensor_length,
        "tile_length": tile_length,
        "tensors_per_core": tensors_per_core,
        "blockdim": args.blockdim,
        "input_stride": input_stride,
        "output_stride": output_stride,
        "variant_flags": variant_flags,
    }
    (root / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    (build_sim / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


def _write_op_config(build_sim: Path, kernel_name: str, blockdim: int,
                     params: list, tiling_size: int = 40) -> None:
    op_config = {
        "kernel_name": kernel_name,
        "kernel_path": f"./{kernel_name}.o",
        "blockdim": blockdim,
        "mode": os.environ.get("MSPROF_OP_CONFIG_MODE", "ca"),
        "device_id": 0,
        "magic": "RT_DEV_BINARY_MAGIC_ELF_AIVEC",
        "test_cases": [{
            "case_name": f"{kernel_name}_case0",
            "param_desc": params + [
                {"param_type": "tiling", "tiling_data_size": tiling_size, "tiling_data_path": "./tiling.bin"},
            ],
        }],
    }
    (build_sim / "op_config.json").write_text(json.dumps(op_config, indent=2), encoding="utf-8")


def main_matmul(
    *, variant_name: str, injected_label: str, injected_problem: str,
    default_m: int, default_n: int, default_k: int,
    default_tile_m: int, default_tile_n: int, default_blockdim: int, variant_flags: int,
) -> None:
    """C[M,N] = A[M,K] * B[K,N]. Input = A++B concatenated, output = C."""
    parser = argparse.ArgumentParser()
    for opt, default in [("--m", default_m), ("--n", default_n), ("--k", default_k),
                         ("--tile-m", default_tile_m), ("--tile-n", default_tile_n),
                         ("--blockdim", default_blockdim)]:
        parser.add_argument(opt, type=int, default=default)
    parser.add_argument("--seed", type=int, default=20260611)
    args = parser.parse_args()

    root = Path.cwd()
    data_dir, build_sim = root / "data", root / "build_sim"
    data_dir.mkdir(exist_ok=True); build_sim.mkdir(exist_ok=True)

    m, n, k = max(8, align_up(args.m, 8)), max(8, align_up(args.n, 8)), max(8, align_up(args.k, 8))
    tile_m, tile_n = max(8, align_up(args.tile_m, 8)), max(8, align_up(args.tile_n, 8))
    a_elems, b_elems, c_elems = m * k, k * n, m * n
    input_stride = align_up(a_elems + b_elems, 8)
    output_stride = align_up(c_elems, 8)
    rows_per_core = math.ceil(m / args.blockdim)

    rng = random.Random(args.seed)
    a = [rng.uniform(-1.0, 1.0) for _ in range(a_elems)]
    b = [rng.uniform(-1.0, 1.0) for _ in range(b_elems)]
    c = matmul_golden(a, b, m, n, k)
    padded_in = [0.0] * input_stride
    padded_in[:a_elems] = a; padded_in[a_elems:a_elems + b_elems] = b
    padded_out = [0.0] * output_stride; padded_out[:c_elems] = c
    write_floats(data_dir / "input.bin", padded_in)
    write_floats(data_dir / "golden.bin", padded_out)
    write_floats(build_sim / "input.bin", padded_in)

    # AprofMatmulTilingData: 12 uint32 = 48 bytes
    tiling = (m, n, k, tile_m, tile_n, align_up(tile_m, 8), align_up(tile_n, 8),
              rows_per_core, input_stride, output_stride, args.blockdim, variant_flags)
    (build_sim / "tiling.bin").write_bytes(struct.pack("12I", *tiling))

    _write_op_config(build_sim, "matmul_kernel", args.blockdim, [
        {"param_type": "input", "type": "float32", "shape": [input_stride], "data_path": "./input.bin", "name": "ab"},
        {"param_type": "output", "type": "float32", "shape": [output_stride], "name": "c"},
    ], tiling_size=48)

    metadata = {"op_name": "matmul", "variant": variant_name, "injected_label": injected_label,
                "injected_problem": injected_problem, "m": m, "n": n, "k": k,
                "tile_m": tile_m, "tile_n": tile_n, "blockdim": args.blockdim,
                "input_stride": input_stride, "output_stride": output_stride, "variant_flags": variant_flags}
    for p in [root / "metadata.json", build_sim / "metadata.json"]:
        p.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


def main_simple_op(
    *, op_name: str, kernel_name: str, variant_name: str, injected_label: str,
    injected_problem: str, default_output_elements: int, default_tile_length: int,
    default_blockdim: int, variant_flags: int, golden_fn: Callable,
) -> None:
    """Generic generator for single-input single-output flattened ops (layer_norm, topk, max_pool)."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-elements", type=int, default=default_output_elements)
    parser.add_argument("--tile-length", type=int, default=default_tile_length)
    parser.add_argument("--blockdim", type=int, default=default_blockdim)
    parser.add_argument("--seed", type=int, default=20260611)
    args = parser.parse_args()

    root = Path.cwd()
    data_dir, build_sim = root / "data", root / "build_sim"
    data_dir.mkdir(exist_ok=True); build_sim.mkdir(exist_ok=True)

    output_elements = max(8, align_up(args.output_elements, 8))
    tile_length = max(8, align_up(args.tile_length, 8))
    tile_length = min(tile_length, output_elements)
    input_stride = align_up(output_elements, 8)
    output_stride = align_up(output_elements, 8)
    elems_per_core = math.ceil(output_elements / args.blockdim)
    base_tile_num = math.ceil(elems_per_core / tile_length) if tile_length else 0
    tile_num = max(1, base_tile_num)
    tail_length = output_elements % tile_length

    rng = random.Random(args.seed)
    logical_x = [rng.uniform(-3.0, 3.0) for _ in range(output_elements)]
    padded_x = [0.0] * input_stride; padded_x[:output_elements] = logical_x
    golden_fn = golden_fn
    y = golden_fn(logical_x, output_elements)
    padded_y = [0.0] * output_stride; padded_y[:output_elements] = y

    write_floats(data_dir / "input.bin", padded_x)
    write_floats(data_dir / "golden.bin", padded_y)
    write_floats(build_sim / "input.bin", padded_x)

    tiling = (output_elements, output_elements, input_stride, output_stride,
              elems_per_core, tile_length, align_up(tile_length, 8),
              tile_num, tail_length, variant_flags)
    (build_sim / "tiling.bin").write_bytes(struct.pack("10I", *tiling))

    _write_op_config(build_sim, kernel_name, args.blockdim, [
        {"param_type": "input", "type": "float32", "shape": [input_stride], "data_path": "./input.bin", "name": "x"},
        {"param_type": "output", "type": "float32", "shape": [output_stride], "name": "y"},
    ], tiling_size=40)

    metadata = {"op_name": op_name, "variant": variant_name, "injected_label": injected_label,
                "injected_problem": injected_problem, "output_elements": output_elements,
                "input_stride": input_stride, "output_stride": output_stride,
                "blockdim": args.blockdim, "tile_length": tile_length, "tile_num": tile_num,
                "tail_length": tail_length, "variant_flags": variant_flags}
    for p in [root / "metadata.json", build_sim / "metadata.json"]:
        p.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
