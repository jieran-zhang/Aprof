from pathlib import Path
import yaml

TASK = Path(__file__).resolve().parents[5] / "third_party/cann-bench/tasks/level3/quant_matmul/cases.yaml"
CASES = yaml.safe_load(TASK.read_text())["cases"]

def get_case(case_id):
    for case in CASES:
        if int(case["case_id"]) == int(case_id):
            return case
    raise KeyError(case_id)
