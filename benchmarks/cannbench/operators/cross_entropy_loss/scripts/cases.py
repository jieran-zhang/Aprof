#!/usr/bin/env python3
from pathlib import Path
import yaml
SOURCE=Path(__file__).resolve().parents[5]/'third_party/cann-bench/tasks/level2/cross_entropy_loss/cases.yaml'
CASES=yaml.safe_load(SOURCE.read_text())['cases']
def get_case(i):
 for c in CASES:
  if c['case_id']==i:return c
 raise ValueError(i)
