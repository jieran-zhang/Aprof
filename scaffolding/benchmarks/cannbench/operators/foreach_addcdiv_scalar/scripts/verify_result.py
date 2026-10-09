#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch

CHUNK = 1_000_000

def load_chunk(f, dtype, count):
    raw = np.fromfile(f, dtype=np.float32 if dtype == 'float32' else np.uint16, count=count)
    if dtype == 'float32': return raw
    if dtype == 'float16': return raw.view(np.float16).astype(np.float32)
    return torch.from_numpy(raw.copy()).view(torch.bfloat16).float().numpy()

def main():
    p = argparse.ArgumentParser(); p.add_argument('--metadata', required=True); a = p.parse_args()
    mp = Path(a.metadata); m = json.loads(mp.read_text()); n = sum(m['lengths']); dt = m['dtype']
    threshold = {'float16': .01, 'bfloat16': .01, 'float32': .005}[dt]
    rel_sum = 0.; rel_max = 0.; finite_count = 0; special_ok = True; seen = 0
    with open(m['golden'], 'rb') as fg, open(m['output'], 'rb') as fo:
        while seen < n:
            count = min(CHUNK, n - seen)
            expected = load_chunk(fg, dt, count); actual = load_chunk(fo, dt, count)
            if len(actual) != count or len(expected) != count:
                raise RuntimeError('output or golden file is truncated')
            special_ok &= bool(np.array_equal(np.isnan(actual), np.isnan(expected)))
            special_ok &= bool(np.array_equal(np.isposinf(actual), np.isposinf(expected)))
            special_ok &= bool(np.array_equal(np.isneginf(actual), np.isneginf(expected)))
            finite = np.isfinite(actual) & np.isfinite(expected)
            if finite.any():
                rel = np.abs(actual[finite] - expected[finite]) / (np.abs(expected[finite]) + 1e-7)
                rel_sum += float(rel.sum(dtype=np.float64)); rel_max = max(rel_max, float(rel.max()))
                finite_count += int(finite.sum())
            seen += count
    mere = rel_sum / max(1, finite_count)
    passed = bool(special_ok and mere < threshold and rel_max < 10 * threshold)
    scalar = m['scalar']
    if isinstance(scalar, float) and not math.isfinite(scalar):
        scalar = 'nan' if math.isnan(scalar) else ('inf' if scalar > 0 else '-inf')
    result = {
        'case_id': m['case_id'], 'shapes': m['shapes'], 'dtype': dt,
        'attrs': {'scalar': scalar}, 'list_length': m['list_length'], 'numel': n,
        'mere': mere, 'mare': rel_max, 'threshold': threshold,
        'special_values_match': special_ok, 'passed': passed,
    }
    (mp.parent / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False))
    print(json.dumps(result, allow_nan=False))
    if not passed: raise SystemExit(1)

if __name__ == '__main__':
    main()
