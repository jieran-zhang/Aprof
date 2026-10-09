#!/usr/bin/env python3
from pathlib import Path
import yaml
SPEC=Path(__file__).resolve().parents[5]/'third_party/cann-bench/tasks/level3/unique/cases.yaml'
CASES=yaml.safe_load(SPEC.read_text())['cases']
def get_case(case_id):
 for c in CASES:
  if c['case_id']==case_id:return {'case_id':case_id,'shape':c['input_shape'][0],'dtype':c['dtype'][0],'return_inverse':c['attrs']['return_inverse'],'value_range':c['value_range']}
 raise ValueError(case_id)
