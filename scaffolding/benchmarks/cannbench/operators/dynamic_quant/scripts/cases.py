#!/usr/bin/env python3

# Exact matrix from third_party/cann-bench/tasks/level2/dynamic_quant/cases.csv.
CASES = [
    (1, [1024, 1024], "float16", [-1, 1]),
    (2, [2048, 2048], "bfloat16", [-2, 2]),
    (3, [4096, 4096], "bfloat16", [-3, 3]),
    (4, [8192, 8192], "float16", [-10, 10]),
    (5, [8192, 8192], "bfloat16", [-100, 100]),
    (6, [8192, 16384], "bfloat16", [-1000, 1000]),
    (7, [1023, 1023], "float16", [-0.1, 0.1]),
    (8, [1009, 1021], "bfloat16", [-1, 2]),
    (9, [1537, 769], "bfloat16", [-5, 10]),
    (10, [363, 367, 373], "float16", [-50, 100]),
    (11, [2049, 513], "bfloat16", [-65504, 65504]),
    (12, [3, 7, 13, 4001], "bfloat16", [-88, 88]),
    (13, [2, 7, 256, 251], "float16", [-0.01, 0.01]),
    (14, [11, 13, 17, 67, 67], "bfloat16", [-1000, 1000]),
    (15, [256, 4099], "bfloat16", [-float("inf"), float("inf")]),
    (16, [3, 7, 11, 13, 1013], "float16", [float("nan"), float("nan")]),
    (17, [512, 2049], "bfloat16", [0, 0]),
    (18, [255, 8193], "bfloat16", [-0.5, 0.5]),
    (19, [4097, 511], "float16", [-1, 3]),
    (20, [2, 511, 2049], "bfloat16", [-3, 6]),
]


def get_case(case_id):
    for row in CASES:
        if row[0] == case_id:
            return dict(zip(("case_id", "shape", "dtype", "value_range"), row))
    raise ValueError(f"unknown case {case_id}")
