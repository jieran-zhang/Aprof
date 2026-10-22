#!/usr/bin/env python3

# Exact shape/dtype/attribute matrix from
# third_party/cann-bench/tasks/level2/arg_max/cases.csv.
CASES = [
    (1, [1048576], "float16", -1, False, [-1, 1]),
    (2, [2048, 2048], "float32", -1, False, [-2, 2]),
    (3, [4096, 4096], "bfloat16", -1, False, [-3, 3]),
    (4, [8192, 8192], "int32", 0, False, [-10000, 10000]),
    (5, [4096, 8192], "int64", -1, False, [-100000, 100000]),
    (6, [8192, 8192], "float32", 0, False, [-1000, 1000]),
    (7, [1023, 1023], "float16", -1, False, [-0.1, 0.1]),
    (8, [1009, 1021], "float32", 0, False, [-1, 2]),
    (9, [1537, 769], "bfloat16", -1, False, [-5, 10]),
    (10, [363, 367, 373], "int32", 1, False, [-50, 100]),
    (11, [2049, 513], "float16", -1, False, [-65504, 65504]),
    (12, [3, 7, 13, 4001], "float32", -1, False, [-88, 88]),
    (13, [2, 7, 256, 251], "bfloat16", 1, False, [-0.01, 0.01]),
    (14, [1048583], "float32", -1, False, [-float("inf"), float("inf")]),
    (15, [11, 13, 17, 67, 67], "float16", 2, False, [float("nan"), float("nan")]),
    (16, [3, 7, 11, 13, 1013], "int64", -1, False, [0, 0]),
    (17, [512, 2049], "float32", -1, False, [-0.5, 0.5]),
    (18, [255, 8193], "bfloat16", 0, False, [-1, 3]),
    (19, [4097, 511], "int32", -1, False, [-1000, 1000]),
    (20, [2, 511, 2049], "float16", 1, False, [-3, 6]),
]


def get_case(case_id):
    for row in CASES:
        if row[0] == case_id:
            return dict(zip(("case_id", "shape", "dtype", "dim", "keepdim", "value_range"), row))
    raise ValueError(f"unknown case {case_id}")
