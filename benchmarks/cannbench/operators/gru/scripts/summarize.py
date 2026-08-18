#!/usr/bin/env python3
import json
from pathlib import Path
r=Path(__file__).resolve().parents[1];c=[json.loads(p.read_text()) for p in sorted((r/'results').glob('case_*/result.json'))];o={'operator':'gru','soc_version':'Ascend910_9362','npu_arch':'dav-2201','validation':'real_npu','profiling':'not_collected_per_user','total_cases':20,'passed_cases':sum(x['passed'] for x in c),'all_passed':len(c)==20 and all(x['passed'] for x in c),'cases':c};(r/'results.json').write_text(json.dumps(o,indent=2));print(json.dumps({k:v for k,v in o.items()if k!='cases'}));raise SystemExit(0 if o['all_passed'] else 1)
