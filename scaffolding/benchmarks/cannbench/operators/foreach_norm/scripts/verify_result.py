#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import numpy as np
import torch

def load(path, dtype):
    if dtype == 'float32': return np.fromfile(path, dtype=np.float32)
    raw = np.fromfile(path, dtype=np.uint16)
    if dtype == 'float16': return raw.view(np.float16).astype(np.float32)
    return torch.from_numpy(raw.copy()).view(torch.bfloat16).float().numpy()

def main():
    p = argparse.ArgumentParser(); p.add_argument('--metadata', required=True); a = p.parse_args()
    mp = Path(a.metadata); m = json.loads(mp.read_text()); dt = m['dtype']
    expected, actual = load(m['golden'], dt), load(m['output'], dt)
    if actual.shape != expected.shape: raise RuntimeError(f'output shape {actual.shape}, expected {expected.shape}')
    special_ok = bool(np.array_equal(np.isnan(actual), np.isnan(expected)) and
                      np.array_equal(np.isposinf(actual), np.isposinf(expected)) and
                      np.array_equal(np.isneginf(actual), np.isneginf(expected)))
    finite = np.isfinite(actual) & np.isfinite(expected)
    rel = np.abs(actual[finite] - expected[finite]) / (np.abs(expected[finite]) + 1e-7)
    mere = float(rel.mean()) if rel.size else 0.0; mare = float(rel.max()) if rel.size else 0.0
    threshold = {'float16': 2**-10, 'bfloat16': 2**-7, 'float32': 2**-13}[dt]
    passed = bool(special_ok and mere < threshold and mare < 10 * threshold)
    result = {'case_id': m['case_id'], 'shapes': m['shapes'], 'dtype': dt,
              'attrs': {'scalar': m['scalar']}, 'list_length': m['list_length'],
              'numel': sum(m['lengths']), 'mere': mere, 'mare': mare,
              'threshold': threshold, 'special_values_match': special_ok, 'passed': passed}
    (mp.parent / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result)); raise SystemExit(0 if passed else 1)

if __name__ == '__main__': main()
