#!/usr/bin/env python3
import json
from pathlib import Path
r=Path(__file__).resolve().parents[1];rows=[]
for i in range(1,21):
 p=r/"results"/f"case_{i}"/"result.json"
 if p.exists():rows.append(json.loads(p.read_text()))
o={"operator":"quant_matmul","level":3,"soc_version":"Ascend910_9362","npu_arch":"dav-2201","execution":"direct_launch_custom_ascendc_cube_and_vector_kernels","correctness_only":True,"profiling":"not_collected_per_user","total_cases":20,"executed_cases":len(rows),"passed_cases":sum(x.get("passed",False) for x in rows),"all_passed":len(rows)==20 and all(x.get("passed",False) for x in rows),"cases":rows};(r/"results.json").write_text(json.dumps(o,indent=2));print(json.dumps({k:v for k,v in o.items() if k!="cases"},indent=2))
