#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch

from cases import get_case

def make_values(rng, count, value_range):
    lo, hi = value_range
    if math.isinf(lo) or math.isinf(hi):
        pattern = np.array([-np.inf, np.inf, -1.0, 1.0, 0.0], dtype=np.float32)
        return np.resize(pattern, count)
    if lo == hi:
        return np.full(count, lo, dtype=np.float32)
    return rng.uniform(lo, hi, size=count).astype(np.float32)

def as_input(values, dtype):
    tensor = torch.from_numpy(values)
    return tensor.to({'float16': torch.float16, 'float32': torch.float32,
                      'bfloat16': torch.bfloat16}[dtype])

def raw_bytes(tensor):
    if tensor.dtype == torch.float32:
        return tensor.numpy().tobytes()
    return tensor.view(torch.uint16).numpy().tobytes()

def json_float(value):
    if value == float('inf'): return 'inf'
    if value == -float('inf'): return '-inf'
    return value

def main():
    p = argparse.ArgumentParser(); p.add_argument('--case', type=int, required=True)
    p.add_argument('--output', default='build/cases'); a = p.parse_args()
    c = get_case(a.case); d = Path(a.output) / f"case_{a.case:02d}"; d.mkdir(parents=True, exist_ok=True)
    input_path, golden_path = d / 'input.bin', d / 'golden.bin'
    rng = np.random.default_rng(20260811 + a.case)
    lengths = [math.prod(shape) for shape in c['shapes']]
    with input_path.open('wb') as fi, golden_path.open('wb') as fg:
        for n in lengths:
            tensor = as_input(make_values(rng, n, c['value_range']), c['dtype'])
            fi.write(raw_bytes(tensor))
            compute = tensor.float() if tensor.dtype in (torch.float16, torch.bfloat16) else tensor
            golden = torch.norm(compute, p=c['scalar']).to(tensor.dtype)
            fg.write(raw_bytes(golden.reshape(1)))
            del tensor, compute, golden
    scalar_json = 'inf' if c['scalar'] == float('inf') else c['scalar']
    meta = {**c, 'scalar': scalar_json,
            'value_range': [json_float(v) for v in c['value_range']],
            'lengths': lengths, 'list_length': len(lengths),
            'input': str(input_path.resolve()), 'golden': str(golden_path.resolve()),
            'output': str((d / 'output.bin').resolve())}
    (d / 'metadata.json').write_text(json.dumps(meta, indent=2, allow_nan=False))
    print(d / 'metadata.json')

if __name__ == '__main__': main()
