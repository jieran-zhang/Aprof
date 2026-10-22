#!/usr/bin/env python3
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cases = [json.loads((root/'build'/'cases'/f'case_{i:02d}'/'result.json').read_text()) for i in range(1,21)]
summary = {'operator': 'foreach_norm',
           'schema': 'foreach_norm(Tensor[] x, float scalar) -> Tensor[] y',
           'soc_version': 'Ascend910_9362', 'npu_arch': 'dav-2201', 'device': 2,
           'total_cases': 20, 'passed_cases': sum(c['passed'] for c in cases),
           'all_passed': all(c['passed'] for c in cases), 'cases': cases}
(root/'results.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({k: summary[k] for k in ('operator','total_cases','passed_cases','all_passed')}))
raise SystemExit(0 if summary['all_passed'] else 1)
