#!/usr/bin/env python3
import json
from datetime import datetime,timezone
from pathlib import Path
r=[]
for p in sorted(Path('build/cases').glob('case_*/result.json')):r.append(json.loads(p.read_text()))
out={'operator':'dequant_swiglu_quant','level':3,'soc':'Ascend910_9362','npu_arch':'dav-2201','verification':'real_npu','correctness_only':True,'performance':'not_collected_per_user','total_cases':20,'passed_cases':sum(x['passed'] for x in r),'all_passed':len(r)==20 and all(x['passed'] for x in r),'cases':r,'generated_at':datetime.now(timezone.utc).isoformat()}
Path('results.json').write_text(json.dumps(out,indent=2));print(json.dumps({'passed':out['passed_cases'],'total':len(r)}))
