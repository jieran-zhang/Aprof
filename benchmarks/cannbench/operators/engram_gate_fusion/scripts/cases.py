#!/usr/bin/env python3
from pathlib import Path
import yaml
SPEC=Path(__file__).resolve().parents[5]/'third_party/cann-bench/tasks/level3/engram_gate_fusion/cases.yaml'
CASES=yaml.safe_load(SPEC.read_text())['cases']
NAMES=['keys','hidden','value','norm1','norm2','conv_norm','conv_weight','state']
def get_case(case_id):
 for c in CASES:
  if c['case_id']==case_id:
   return {'case_id':case_id,'input_shapes':dict(zip(NAMES,c['input_shape'])),'dtypes':dict(zip(NAMES,c['dtype'])),'attrs':c['attrs'],'value_ranges':dict(zip(NAMES,c['value_range'])),'note':c.get('note','')}
 raise ValueError(case_id)
