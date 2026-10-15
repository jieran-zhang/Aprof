from pathlib import Path
import yaml
P=Path(__file__).resolve().parents[5]/'third_party/cann-bench/tasks/level4/gqa/cases.yaml'
CASES=yaml.safe_load(P.read_text())['cases']
def get_case(i):
 c=next(x for x in CASES if x['case_id']==i)
 return {'case_id':i,'query_shape':c['input_shape'][0],'key_shape':c['input_shape'][1],
  'value_shape':c['input_shape'][2],'dtype':c['dtype'][0],**c['attrs'],'value_range':c['value_range'],'note':c['note']}
