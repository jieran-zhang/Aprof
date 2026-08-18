#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path
import numpy as np
import torch
from cases import get_case

TORCH_DTYPES = {
    'float16': torch.float16, 'float32': torch.float32, 'bfloat16': torch.bfloat16,
    'int32': torch.int32, 'int64': torch.int64,
}

def values(rng, size, bounds, dtype):
    lo, hi = bounds
    if dtype.startswith('int'):
        return torch.from_numpy(rng.integers(int(lo), int(hi) + 1, size=size, dtype=np.int64)).to(TORCH_DTYPES[dtype])
    if math.isnan(lo):
        return torch.full((size,), float('nan'), dtype=TORCH_DTYPES[dtype])
    if math.isinf(lo):
        x = np.empty(size, dtype=np.float32)
        x[0::2] = -np.inf
        x[1::2] = np.inf
    elif lo == hi:
        x = np.full(size, lo, dtype=np.float32)
    else:
        x = rng.uniform(lo, hi, size=size).astype(np.float32)
    return torch.from_numpy(x).to(TORCH_DTYPES[dtype])

def write_tensor(path, tensor, dtype):
    tensor = tensor.contiguous().cpu()
    raw = tensor.view(torch.uint16).numpy() if dtype == 'bfloat16' else tensor.numpy()
    path.write_bytes(raw.tobytes())

def write_values(path, shape, bounds, dtype, rng):
    total = math.prod(shape)
    with path.open('wb') as f:
        for start in range(0, total, 1_000_000):
            tensor = values(rng, min(1_000_000, total - start), bounds, dtype)
            raw = tensor.view(torch.uint16).numpy() if dtype == 'bfloat16' else tensor.numpy()
            f.write(raw.tobytes())

def unique_indices(data_shape, index_shape, dim, dtype):
    dim_n = dim if dim >= 0 else len(index_shape) + dim
    D, n = int(data_shape[dim_n]), int(index_shape[dim_n])
    moved_shape = list(index_shape[:dim_n]) + list(index_shape[dim_n + 1:]) + [n]
    slices = math.prod(moved_shape[:-1])
    g = torch.Generator().manual_seed(0)
    out = torch.empty((slices, n), dtype=torch.int64)
    chunk = max(1, min(slices, max(1, (1 << 22) // D)))
    for start in range(0, slices, chunk):
        stop = min(start + chunk, slices)
        out[start:stop] = torch.rand(stop - start, D, generator=g).argsort(dim=1)[:, :n]
    moved = out.reshape(moved_shape)
    result = moved.movedim(-1, dim_n).contiguous()
    return result.to(TORCH_DTYPES[dtype])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', type=int, required=True)
    parser.add_argument('--output', default='build/cases')
    args = parser.parse_args()
    case = get_case(args.case)
    directory = Path(args.output) / f"case_{args.case:02d}"
    directory.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20260811 + args.case)
    data_path, index_path, update_path = directory/'data.bin', directory/'indices.bin', directory/'updates.bin'
    write_values(data_path, case['data_shape'], case['value_ranges'][0], case['data_dtype'], rng)
    if case['reduce'] is None:
        indices = unique_indices(case['data_shape'], case['index_shape'], case['dim'], case['index_dtype'])
        write_tensor(index_path, indices, case['index_dtype'])
    else:
        write_values(index_path, case['index_shape'], case['value_ranges'][1], case['index_dtype'], rng)
    write_values(update_path, case['update_shape'], case['value_ranges'][2], case['data_dtype'], rng)
    metadata = {
        **case,
        'data_numel': math.prod(case['data_shape']),
        'update_numel': math.prod(case['index_shape']),
        'data': str(data_path.resolve()),
        'indices': str(index_path.resolve()),
        'updates': str(update_path.resolve()),
        'output': str((directory/'output.bin').resolve()),
    }
    (directory/'metadata.json').write_text(json.dumps(metadata, indent=2, allow_nan=True))
    print(directory/'metadata.json')

if __name__ == '__main__':
    main()
