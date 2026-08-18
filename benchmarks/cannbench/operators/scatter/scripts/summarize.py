#!/usr/bin/env python3
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = sorted((root/'build/cases').glob('case_*/result.json'))
cases = [json.loads(path.read_text()) for path in files]
result = {
    'operator': 'scatter', 'level': 2, 'soc_version': 'Ascend910_9362', 'npu_arch': 'dav-2201',
    'device': 4, 'total_cases': 20, 'passed_cases': sum(bool(case['passed']) for case in cases),
    'all_passed': len(cases) == 20 and all(case['passed'] for case in cases), 'cases': cases,
}
(root/'results.json').write_text(json.dumps(result, indent=2))
print(json.dumps({key: value for key, value in result.items() if key != 'cases'}))
if not result['all_passed']:
    raise SystemExit(1)
