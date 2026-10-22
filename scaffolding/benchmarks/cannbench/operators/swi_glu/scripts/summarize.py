#!/usr/bin/env python3
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
cases=[]
for path in sorted((root/'build'/'cases').glob('case_*/result.json')):
    cases.append(json.loads(path.read_text()))
result={'operator':'swi_glu','soc_version':'Ascend910','npu_arch':'dav-2201',
        'total_cases':20,'passed_cases':sum(bool(x.get('passed')) for x in cases),
        'all_passed':len(cases)==20 and all(x.get('passed') for x in cases),'cases':cases}
(root/'results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))
if not result['all_passed']: raise SystemExit(1)
