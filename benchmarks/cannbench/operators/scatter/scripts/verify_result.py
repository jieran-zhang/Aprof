#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import numpy as np
import torch

NP_DTYPES = {
    'float16': np.float16, 'float32': np.float32, 'bfloat16': np.uint16,
    'int32': np.int32, 'int64': np.int64,
}

def load(path, shape, dtype):
    array = np.fromfile(path, dtype=NP_DTYPES[dtype])
    tensor = torch.from_numpy(array.copy()).view(torch.bfloat16) if dtype == 'bfloat16' else torch.from_numpy(array)
    return tensor.reshape(shape)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--metadata', required=True)
    args = parser.parse_args()
    metadata_path = Path(args.metadata)
    m = json.loads(metadata_path.read_text())
    dtype = m['data_dtype']
    data = load(m['data'], m['data_shape'], dtype)
    indices = load(m['indices'], m['index_shape'], m['index_dtype']).long()
    updates = load(m['updates'], m['update_shape'], dtype)
    actual = load(m['output'], m['data_shape'], dtype)
    expected = data.clone()
    reduction = m['reduce']
    if reduction is None:
        expected.scatter_(m['dim'], indices, updates)
    elif reduction == 'add':
        expected.scatter_add_(m['dim'], indices, updates)
    else:
        torch_reduce = {'multiply': 'prod', 'amin': 'amin', 'amax': 'amax'}[reduction]
        expected.scatter_reduce_(m['dim'], indices, updates, reduce=torch_reduce, include_self=True)
    exact = bool(torch.equal(actual, expected))
    special_ok = True
    mere = mare = 0.0
    if dtype in ('float16', 'float32', 'bfloat16'):
        special_ok = bool(
            torch.equal(torch.isnan(actual), torch.isnan(expected)) and
            torch.equal(torch.isposinf(actual), torch.isposinf(expected)) and
            torch.equal(torch.isneginf(actual), torch.isneginf(expected)))
        finite = torch.isfinite(actual) & torch.isfinite(expected)
        if finite.any():
            relative = (actual[finite].float() - expected[finite].float()).abs() / (expected[finite].float().abs() + 1e-7)
            mere = float(relative.double().mean())
            mare = float(relative.max())
        threshold = {'float16': 2**-10, 'bfloat16': 2**-7, 'float32': 2**-13}[dtype]
        passed = bool(special_ok and mere < threshold and mare < 10 * threshold)
    else:
        threshold = 0.0
        passed = exact
    result = {
        'case_id': m['case_id'], 'data_shape': m['data_shape'], 'index_shape': m['index_shape'],
        'data_dtype': dtype, 'index_dtype': m['index_dtype'], 'dim': m['dim'], 'reduce': reduction,
        'data_numel': m['data_numel'], 'update_numel': m['update_numel'], 'exact_match': exact,
        'mere': mere, 'mare': mare, 'threshold': threshold,
        'special_values_match': special_ok, 'passed': passed,
    }
    (metadata_path.parent/'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    if not passed:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
