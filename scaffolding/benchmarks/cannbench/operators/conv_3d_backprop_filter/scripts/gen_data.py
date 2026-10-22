#!/usr/bin/env python3
import argparse, json, math
from pathlib import Path
import numpy as np, torch
from cases import get_case

def encode(values, dtype):
    if dtype == 'float16': return values.astype(np.float16)
    return torch.from_numpy(values.astype(np.float32)).to(torch.bfloat16).view(torch.uint16).numpy()
def values(rng, count, vr):
    lo, hi = vr
    if math.isnan(lo): return np.full(count, np.nan, np.float32)
    if math.isinf(lo):
        v = np.empty(count, np.float32); v[0::2] = -np.inf; v[1::2] = np.inf; return v
    if lo == hi: return np.full(count, lo, np.float32)
    return rng.uniform(lo, hi, count).astype(np.float32)
def write(path, count, vr, dtype, rng):
    with path.open('wb') as f:
        for start in range(0, count, 1_000_000): f.write(encode(values(rng, min(1_000_000, count - start), vr), dtype).tobytes())
def main():
    p = argparse.ArgumentParser(); p.add_argument('--case', type=int, required=True); p.add_argument('--output', default='build/cases'); args = p.parse_args(); c = get_case(args.case)
    d = Path(args.output) / f"case_{args.case:02d}"; d.mkdir(parents=True, exist_ok=True); rng = np.random.default_rng(20260812 + args.case)
    paths = {k: d / f'{k}.bin' for k in ('x', 'grad', 'output')}
    write(paths['x'], math.prod(c['x_shape']), c['value_range'][0], c['dtype'], rng); write(paths['grad'], math.prod(c['grad_shape']), c['value_range'][1], c['dtype'], rng)
    metadata = {**c, 'output_shape': c['attrs']['filter_size'], 'numel': math.prod(c['attrs']['filter_size']), **{k: str(v.resolve()) for k, v in paths.items()}}
    (d / 'metadata.json').write_text(json.dumps(metadata, indent=2, allow_nan=True)); print(d / 'metadata.json')
if __name__ == '__main__': main()
