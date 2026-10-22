#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch

from cases import get_case

CHUNK = 1_000_000

def make_values(rng, count, value_range):
    lo, hi = value_range
    if math.isnan(lo) or math.isnan(hi):
        return np.full(count, np.nan, dtype=np.float32)
    if math.isinf(lo) or math.isinf(hi):
        if math.isinf(lo) and math.isinf(hi):
            pattern = np.array([-np.inf, np.inf, -1.0, 1.0], dtype=np.float32)
        elif math.isinf(hi):
            pattern = np.array([lo, np.inf, max(float(lo), 1.0), np.inf], dtype=np.float32)
        else:
            pattern = np.array([-np.inf, hi, -np.inf, min(float(hi), -1.0)], dtype=np.float32)
        return np.resize(pattern, count)
    if lo == hi:
        return np.full(count, lo, dtype=np.float32)
    return rng.uniform(lo, hi, size=count).astype(np.float32)

def raw_bytes(x, dtype):
    if dtype == 'float32':
        return x.astype(np.float32, copy=False).tobytes()
    if dtype == 'float16':
        return x.astype(np.float16).tobytes()
    return torch.from_numpy(x).to(torch.bfloat16).view(torch.uint16).numpy().tobytes()

def input_float(x, dtype):
    if dtype == 'float32':
        return x.astype(np.float32, copy=False)
    if dtype == 'float16':
        return x.astype(np.float16).astype(np.float32)
    return torch.from_numpy(x).to(torch.bfloat16).float().numpy()

def quantize(x, dtype):
    if dtype == 'float32':
        return x.astype(np.float32).tobytes()
    if dtype == 'float16':
        return x.astype(np.float16).tobytes()
    return torch.from_numpy(x.astype(np.float32)).to(torch.bfloat16).view(torch.uint16).numpy().tobytes()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case', type=int, required=True)
    p.add_argument('--output', default='build/cases')
    a = p.parse_args()
    c = get_case(a.case)
    d = Path(a.output) / f"case_{a.case:02d}"
    d.mkdir(parents=True, exist_ok=True)
    paths = {name: d / f'{name}.bin' for name in ('x1', 'x2', 'x3', 'golden')}
    rng = np.random.default_rng(20260811 + a.case)
    lengths = [math.prod(shape) for shape in c['shapes']]
    with paths['x1'].open('wb') as f1, paths['x2'].open('wb') as f2, \
         paths['x3'].open('wb') as f3, paths['golden'].open('wb') as fg:
        for n in lengths:
            for start in range(0, n, CHUNK):
                count = min(CHUNK, n - start)
                x1 = make_values(rng, count, c['value_ranges'][0])
                x2 = make_values(rng, count, c['value_ranges'][1])
                x3 = make_values(rng, count, c['value_ranges'][2])
                f1.write(raw_bytes(x1, c['dtype']))
                f2.write(raw_bytes(x2, c['dtype']))
                f3.write(raw_bytes(x3, c['dtype']))
                a1 = input_float(x1, c['dtype'])
                a2 = input_float(x2, c['dtype'])
                a3 = input_float(x3, c['dtype'])
                with np.errstate(all='ignore'):
                    expected = a1 + (a2 / a3) * np.float32(c['scalar'])
                fg.write(quantize(expected, c['dtype']))
    meta = {
        **c,
        'lengths': lengths,
        'list_length': len(lengths),
        'x1': str(paths['x1'].resolve()),
        'x2': str(paths['x2'].resolve()),
        'x3': str(paths['x3'].resolve()),
        'golden': str(paths['golden'].resolve()),
        'output': str((d / 'output.bin').resolve()),
    }
    (d / 'metadata.json').write_text(json.dumps(meta, indent=2, allow_nan=True))
    print(d / 'metadata.json')

if __name__ == '__main__':
    main()
