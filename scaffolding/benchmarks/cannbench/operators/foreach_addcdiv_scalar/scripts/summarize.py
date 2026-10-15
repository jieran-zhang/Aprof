#!/usr/bin/env python3
import json
import math
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cases = [json.loads((root / 'build' / 'cases' / f'case_{i:02d}' / 'result.json').read_text()) for i in range(1, 21)]
for case in cases:
    scalar = case['attrs']['scalar']
    if isinstance(scalar, float) and not math.isfinite(scalar):
        case['attrs']['scalar'] = 'nan' if math.isnan(scalar) else ('inf' if scalar > 0 else '-inf')
summary = {
    'operator': 'foreach_addcdiv_scalar',
    'schema': 'foreach_addcdiv_scalar(Tensor[] x1, Tensor[] x2, Tensor[] x3, float scalar) -> Tensor[] y',
    'soc_version': 'Ascend910_9362', 'npu_arch': 'dav-2201', 'device': 0,
    'total_cases': len(cases), 'passed_cases': sum(c['passed'] for c in cases),
    'all_passed': all(c['passed'] for c in cases), 'cases': cases,
}
(root / 'results.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
print(json.dumps({k: summary[k] for k in ('operator','total_cases','passed_cases','all_passed')}))
if not summary['all_passed']: raise SystemExit(1)
