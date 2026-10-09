#!/usr/bin/env python3

# Exact case matrix from third_party/cann-bench/tasks/level1/mish/cases.csv.
CASES = [
    (1, [1024, 1024], "float16", [-1.0, 1.0]),
    (2, [2048, 2048], "float32", [-2.0, 2.0]),
    (3, [4096, 4096], "bfloat16", [-3.0, 3.0]),
    (4, [8192, 8192], "float16", [-10.0, 10.0]),
    (5, [8192, 8192], "float32", [-100.0, 100.0]),
    (6, [1023, 1023], "bfloat16", [-0.1, 0.1]),
    (7, [1009, 1021], "float16", [-1.0, 2.0]),
    (8, [1537, 769], "float32", [-5.0, 10.0]),
    (9, [363, 367, 373], "bfloat16", [-50.0, 100.0]),
    (10, [2049, 513], "float16", [-65504.0, 65504.0]),
    (11, [3, 7, 13, 4001], "float32", [-88.0, 88.0]),
    (12, [1000003], "bfloat16", [-float("inf"), float("inf")]),
    (13, [11, 13, 17, 67, 67], "float32", [float("nan"), float("nan")]),
    (14, [3, 7, 11, 13, 1009], "float16", [0.0, 0.0]),
    (15, [512, 2049], "float32", [-0.5, 0.5]),
    (16, [255, 8193], "bfloat16", [-1.0, 3.0]),
    (17, [4097, 511], "float16", [-1000.0, 1000.0]),
    (18, [2, 511, 2049], "float32", [-0.2, 0.2]),
    (19, [4, 255, 2049], "bfloat16", [-3.0, 6.0]),
    (20, [2, 3, 17, 1024, 101], "float32", [-20.0, 40.0]),
]


def get_case(case_id):
    for row in CASES:
        if row[0] == case_id:
            return dict(zip(("case_id", "shape", "dtype", "value_range"), row))
    raise ValueError(f"unknown case {case_id}")
