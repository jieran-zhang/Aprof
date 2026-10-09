#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path
import numpy as np
import torch
from cases import get_case

NP_DTYPES = {'int16': np.int16, 'int32': np.int32, 'int64': np.int64}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case', type=int, required=True)
    p.add_argument('--output', default='build/cases')
    a = p.parse_args()
    c = get_case(a.case)
    d = Path(a.output) / f"case_{a.case:02d}"
    d.mkdir(parents=True, exist_ok=True)
    paths = [d / 'x1.bin', d / 'x2.bin']
    rng = np.random.default_rng(20260811 + a.case)
    dtype = NP_DTYPES[c['dtype']]
    for path, shape, bounds in zip(paths, c['input_shapes'], c['value_ranges']):
        n = math.prod(shape)
        lo, hi = bounds
        with path.open('wb') as f:
            for start in range(0, n, 1_000_000):
                count = min(1_000_000, n - start)
                if lo == hi:
                    values = np.full(count, lo, dtype=dtype)
                else:
                    values = rng.integers(lo, hi, endpoint=True, size=count, dtype=dtype)
                f.write(values.tobytes())
    out_shape = torch.broadcast_shapes(*[tuple(x) for x in c['input_shapes']])
    meta = {**c, 'output_shape': list(out_shape), 'numel': math.prod(out_shape),
            'x1': str(paths[0].resolve()), 'x2': str(paths[1].resolve()),
            'output': str((d / 'output.bin').resolve())}
    (d / 'metadata.json').write_text(json.dumps(meta, indent=2))
    print(d / 'metadata.json')

if __name__ == '__main__':
    main()
