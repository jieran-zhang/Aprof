#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import numpy as np
import torch

NP_DTYPES = {'int16': np.int16, 'int32': np.int32, 'int64': np.int64}

def load(path, shape, dtype):
    return torch.from_numpy(np.fromfile(path, dtype=NP_DTYPES[dtype])).reshape(shape)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--metadata', required=True)
    a = p.parse_args()
    mp = Path(a.metadata)
    m = json.loads(mp.read_text())
    dtype = NP_DTYPES[m['dtype']]
    mismatches = 0
    # Equal-shape cases include the largest tensors.  Verify every element in
    # bounded chunks so the official int16 widening path does not require
    # several full-size int32 temporaries at once.
    if m['input_shapes'][0] == m['input_shapes'][1]:
        x1 = np.memmap(m['x1'], dtype=dtype, mode='r')
        x2 = np.memmap(m['x2'], dtype=dtype, mode='r')
        actual = np.memmap(m['output'], dtype=dtype, mode='r')
        for start in range(0, m['numel'], 1_000_000):
            end = min(start + 1_000_000, m['numel'])
            a = torch.from_numpy(np.array(x1[start:end], copy=True))
            b = torch.from_numpy(np.array(x2[start:end], copy=True))
            if m['dtype'] == 'int16':
                expected = torch.gcd(a.int(), b.int()).to(torch.int16).numpy()
            else:
                expected = torch.gcd(a, b).numpy()
            mismatches += int(np.count_nonzero(np.asarray(actual[start:end]) != expected))
    else:
        x1 = load(m['x1'], m['input_shapes'][0], m['dtype'])
        x2 = load(m['x2'], m['input_shapes'][1], m['dtype'])
        actual = load(m['output'], m['output_shape'], m['dtype'])
        # Match authoritative golden.py: int16 promotes before gcd; wider
        # dtypes explicitly broadcast before gcd.
        if m['dtype'] == 'int16':
            expected = torch.gcd(x1.int(), x2.int()).to(torch.int16)
        else:
            expected = torch.gcd(*torch.broadcast_tensors(x1, x2))
        mismatches = int(torch.count_nonzero(actual != expected))
    exact = mismatches == 0
    result = {'case_id': m['case_id'], 'input_shapes': m['input_shapes'],
              'output_shape': m['output_shape'], 'dtype': m['dtype'], 'numel': m['numel'],
              'exact_match': exact, 'mismatch_count': mismatches, 'passed': exact}
    (mp.parent / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    if not exact:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
