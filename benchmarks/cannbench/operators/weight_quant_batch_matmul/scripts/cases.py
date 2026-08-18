#!/usr/bin/env python3
from pathlib import Path
import yaml
TASK=Path(__file__).resolve().parents[5]/"third_party/cann-bench/tasks/level3/weight_quant_batch_matmul/cases.yaml"
CASES=yaml.safe_load(TASK.read_text())["cases"]
def get_case(case_id):
    for c in CASES:
        if int(c["case_id"])==case_id:return c
    raise ValueError(case_id)
