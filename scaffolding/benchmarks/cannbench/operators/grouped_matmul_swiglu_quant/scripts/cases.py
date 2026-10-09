from pathlib import Path
import yaml
TASK=Path(__file__).resolve().parents[5]/"third_party/cann-bench/tasks/level4/grouped_matmul_swiglu_quant/cases.yaml"
CASES=yaml.safe_load(TASK.read_text())["cases"]
def get_case(i):
 for c in CASES:
  if int(c["case_id"])==int(i): return c
 raise KeyError(i)
