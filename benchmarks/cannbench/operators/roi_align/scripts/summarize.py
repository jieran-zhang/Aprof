#!/usr/bin/env python3
import json
from pathlib import Path
r=Path(__file__).resolve().parents[1];cases=[json.loads(p.read_text()) for p in sorted((r/'build/cases').glob('case_*/result.json'))];o={'operator':'roi_align','soc_version':'Ascend910','npu_arch':'dav-2201','total_cases':20,'passed_cases':sum(x['passed'] for x in cases),'all_passed':len(cases)==20 and all(x['passed'] for x in cases),'cases':cases};(r/'results.json').write_text(json.dumps(o,indent=2));print(json.dumps({k:v for k,v in o.items() if k!='cases'}));raise SystemExit(0 if o['all_passed'] else 1)
