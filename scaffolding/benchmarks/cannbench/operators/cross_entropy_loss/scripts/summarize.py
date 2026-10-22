#!/usr/bin/env python3
import json
from pathlib import Path
r=Path(__file__).resolve().parents[1];c=[json.loads(p.read_text()) for p in sorted((r/'build/cases').glob('case_*/result.json'))];o={'operator':'cross_entropy_loss','soc_version':'Ascend910','npu_arch':'dav-2201','total_cases':20,'passed_cases':sum(x['passed'] for x in c),'all_passed':len(c)==20 and all(x['passed'] for x in c),'cases':c};(r/'results.json').write_text(json.dumps(o,indent=2));print(o['passed_cases'],o['all_passed']);raise SystemExit(0 if o['all_passed'] else 1)
