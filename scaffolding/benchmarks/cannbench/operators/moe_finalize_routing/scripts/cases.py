#!/usr/bin/env python3
from pathlib import Path
import yaml
_PATH=Path(__file__).resolve().parents[5]/'third_party/cann-bench/tasks/level3/moe_finalize_routing/cases.yaml'
CASES={int(x['case_id']):x for x in yaml.safe_load(_PATH.read_text())['cases']}
def get_case(case_id):
    if case_id not in CASES: raise ValueError(f'unknown case {case_id}')
    return CASES[case_id]
