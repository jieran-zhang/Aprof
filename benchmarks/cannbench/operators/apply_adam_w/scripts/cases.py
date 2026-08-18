import csv
import json
from pathlib import Path


TASK_CSV = Path(__file__).resolve().parents[5] / "third_party/cann-bench/tasks/level2/apply_adam_w/cases.csv"


def load_cases():
    result = []
    with TASK_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            attrs = json.loads(row["attrs"])
            attrs.setdefault("epsilon", 1e-8)
            attrs.setdefault("step", 1)
            attrs.setdefault("maximize", False)
            result.append({
                "case_id": int(row["case_id"]),
                "shape": json.loads(row["input_shape"])[0],
                "dtype": json.loads(row["dtype"])[0],
                "attrs": attrs,
                "ranges": json.loads(row["value_range"]),
                "note": row["note"],
            })
    return result


def get_case(case_id):
    return next(c for c in load_cases() if c["case_id"] == int(case_id))
