#!/usr/bin/env python3
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1];rows=[]
for i in range(1,21):
 p=root/"results"/f"case_{i}"/"result.json"
 if p.exists():rows.append(json.loads(p.read_text()))
out={"operator":"grouped_matmul","level":3,"soc_version":"Ascend910_9362","npu_arch":"dav-2201",
     "execution":"direct_launch_custom_ascendc_cube_kernel","correctness_only":True,"profiling":"not_collected_per_user",
     "total_cases":20,"executed_cases":len(rows),"passed_cases":sum(bool(x.get("passed")) for x in rows),
     "all_passed":len(rows)==20 and all(x.get("passed") for x in rows),"cases":rows}
(root/"results.json").write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!="cases"},indent=2))
