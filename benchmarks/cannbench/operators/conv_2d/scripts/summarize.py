#!/usr/bin/env python3
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1];rows=[]
for p in sorted((root/'build/cases').glob('case_*/result.json')):rows.append(json.loads(p.read_text()))
out={'operator':'conv_2d','level':3,'soc_version':'Ascend910_9362','npu_arch':'dav-2201','execution':'direct_custom_ascendc_im2col_cube_matmul_postprocess_bf16_sensitive_correction','correctness_only':True,'profiling':'not_collected_per_user','total_cases':20,'passed_cases':sum(bool(x['passed']) for x in rows),'all_passed':len(rows)==20 and all(x['passed'] for x in rows),'cases':rows};(root/'results.json').write_text(json.dumps(out,indent=2,allow_nan=True));print(json.dumps({'collected':len(rows),'passed':out['passed_cases'],'all_passed':out['all_passed']}))
