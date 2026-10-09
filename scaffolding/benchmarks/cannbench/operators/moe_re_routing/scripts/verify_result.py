#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import numpy as np

RAW = {"float16": np.float16, "bfloat16": np.uint16, "int8": np.int8,
       "int32": np.int32, "int64": np.int64, "float32": np.float32}

parser = argparse.ArgumentParser()
parser.add_argument("--metadata", required=True)
args = parser.parse_args()
metadata_path = Path(args.metadata)
m = json.loads(metadata_path.read_text())
a, h, n, e = m["tokens"], m["hidden"], m["ranks"], m["experts"]
token_dtype, count_dtype = m["dtype"][0], m["dtype"][1]
counts = np.memmap(m["files"]["counts"], dtype=RAW[count_dtype], mode="r", shape=(n, e))
src_start = np.concatenate(([0], np.cumsum(np.asarray(counts).reshape(-1), dtype=np.int64)[:-1]))
expected_index = np.empty(a, dtype=np.int32)
dst = 0
for expert in range(e):
    for rank in range(n):
        cell = rank * e + expert
        count = int(counts[rank, expert])
        expected_index[dst:dst + count] = np.arange(src_start[cell], src_start[cell] + count, dtype=np.int32)
        dst += count
expected_count = np.asarray(counts).sum(axis=0, dtype=RAW[count_dtype])
actual_index = np.memmap(m["outputs"]["output_index"], dtype=np.int32, mode="r", shape=(a,))
actual_count = np.memmap(m["outputs"]["output_count"], dtype=RAW[count_dtype], mode="r", shape=(e,))
input_tokens = np.memmap(m["files"]["tokens"], dtype=RAW[token_dtype], mode="r", shape=(a, h))
actual_tokens = np.memmap(m["outputs"]["output_tokens"], dtype=RAW[token_dtype], mode="r", shape=(a, h))
actual_scales = np.memmap(m["outputs"]["output_scales"], dtype=np.float32, mode="r", shape=(a,))
input_scales = (np.memmap(m["files"]["scales"], dtype=np.float32, mode="r", shape=(a,))
                if "scales" in m["files"] else None)
index_mismatch = int(np.count_nonzero(np.asarray(actual_index) != expected_index))
count_mismatch = int(np.count_nonzero(np.asarray(actual_count) != expected_count))
token_mismatch = 0
scale_mismatch = 0
for off in range(0, a, 256):
    end = min(a, off + 256)
    expected_tokens = np.asarray(input_tokens[expected_index[off:end]])
    token_mismatch += int(np.count_nonzero(np.asarray(actual_tokens[off:end]) != expected_tokens))
    expected_scales = (np.asarray(input_scales[expected_index[off:end]])
                       if input_scales is not None else np.zeros(end - off, np.float32))
    scale_mismatch += int(np.count_nonzero(np.asarray(actual_scales[off:end]) != expected_scales))
passed = index_mismatch == count_mismatch == token_mismatch == scale_mismatch == 0
result = {
    "case_id": m["case_id"], "input_shape": m["input_shape"],
    "output_shapes": [[a, h], [a], [a], [e]], "dtype": m["dtype"],
    "token_mismatch_count": token_mismatch, "scale_mismatch_count": scale_mismatch,
    "index_mismatch_count": index_mismatch, "count_mismatch_count": count_mismatch,
    "comparison": "bitwise_exact", "passed": passed, "note": m["note"]
}
(metadata_path.parent / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
print(json.dumps(result, ensure_ascii=False))
raise SystemExit(0 if passed else 1)
