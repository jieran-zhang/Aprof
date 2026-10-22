#!/usr/bin/env python3
import csv, json
from pathlib import Path

CSV = Path(__file__).resolve().parents[5] / 'third_party/cann-bench/tasks/level3/conv_3d_backprop_filter/cases.csv'
def _range(v):
    def cv(x):
        if isinstance(x, (int, float)): return x
        return {'inf': float('inf'), '-inf': float('-inf'), 'nan': float('nan')}[x]
    return [[cv(x) for x in pair] for pair in v]
def all_cases():
    out = []
    with CSV.open(newline='') as f:
        for row in csv.DictReader(f):
            shapes = json.loads(row['input_shape']); dtypes = json.loads(row['dtype'])
            out.append({'case_id': int(row['case_id']), 'x_shape': shapes[0], 'grad_shape': shapes[1], 'dtype': dtypes[0],
                        'attrs': json.loads(row['attrs']), 'value_range': _range(json.loads(row['value_range'])), 'note': row['note']})
    return out
def get_case(case_id):
    for case in all_cases():
        if case['case_id'] == case_id: return case
    raise KeyError(case_id)
