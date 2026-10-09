from pathlib import Path
import yaml
P=Path(__file__).resolve().parents[5]/'third_party/cann-bench/tasks/level4/gru/cases.yaml'
CASES=yaml.safe_load(P.read_text())['cases']
def get_case(i):
 c=next(x for x in CASES if x['case_id']==i)
 return c
