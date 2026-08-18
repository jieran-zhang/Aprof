#!/usr/bin/env python3
from pathlib import Path
import yaml
SPEC=Path(__file__).resolve().parents[5]/'third_party/cann-bench/tasks/level3/depthwise_conv_2d/cases.yaml'
CASES=yaml.safe_load(SPEC.read_text())['cases']
def get_case(case_id):
 for c in CASES:
  if c['case_id']==case_id:
   return {'case_id':case_id,'shape':c['input_shape'][0],'weight_shape':c['input_shape'][1],'bias_shape':c['input_shape'][2],
    'dtype':c['dtype'][0],'attrs':c['attrs'],'value_range':c['value_range'],'note':c.get('note','')}
 raise ValueError(case_id)
