#!/usr/bin/env python3
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1];files=sorted((root/'build/cases').glob('case_*/result.json'))
cases=[json.loads(p.read_text()) for p in files]
out={'operator':'grid_sampler_3d','soc_version':'Ascend910','npu_arch':'dav-2201','total_cases':20,
     'passed_cases':sum(x['passed'] for x in cases),'all_passed':len(cases)==20 and all(x['passed'] for x in cases),'cases':cases}
(root/'results.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='cases'}));raise SystemExit(0 if out['all_passed'] else 1)
