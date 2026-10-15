#!/usr/bin/env python3
import json
from pathlib import Path
r=Path(__file__).resolve().parents[1];cs=[json.loads(p.read_text()) for p in sorted((r/'build/cases').glob('case_*/result.json'))];o={'operator':'cummin','level':2,'soc_version':'Ascend910_9362','npu_arch':'dav-2201','device':4,'total_cases':20,'passed_cases':sum(x['passed'] for x in cs),'all_passed':len(cs)==20 and all(x['passed'] for x in cs),'cases':cs};(r/'results.json').write_text(json.dumps(o,indent=2));print({k:v for k,v in o.items() if k!='cases'});raise SystemExit(0 if o['all_passed'] else 1)
