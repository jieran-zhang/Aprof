"""从未过滤的原始 Task 表重建同一流上的 20 次清 L2 完整调用。"""

import csv
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median


def _rows(path, label):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"Op Name", "OP Type", "Task Duration(us)"}
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or not required <= set(reader.fieldnames):
            raise ValueError(f"{label}: missing or duplicate Task CSV columns")
        if not {"Stream ID", "Stream Id"} & set(reader.fieldnames):
            raise ValueError(f"{label}: missing Stream ID column")
        rows = []
        for line, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{label}: malformed Task CSV row {line}")
            name, kind, raw = (row[key].strip() for key in ("Op Name", "OP Type", "Task Duration(us)"))
            if not name or not kind:
                raise ValueError(f"{label}: missing kernel identity at row {line}")
            try:
                duration = Decimal(raw)
            except InvalidOperation as exc:
                raise ValueError(f"{label}: invalid Task duration at row {line}") from exc
            if not duration.is_finite() or duration <= 0:
                raise ValueError(f"{label}: nonpositive Task duration at row {line}")
            stream_id = (row.get("Stream ID") or row.get("Stream Id") or "").strip()
            if not stream_id:
                raise ValueError(f"{label}: missing Stream ID at row {line}")
            rows.append((name, kind, duration, stream_id))
    if not rows:
        raise ValueError(f"{label}: empty Task CSV")
    return rows


def complete_calls(kernel_details, op_summary, expected_names, *, eviction_type="CannBenchCacheClean"):
    """优先读取 kernel_details；只有文件不存在时才读取 op_summary。"""
    primary = Path(kernel_details) if kernel_details is not None else None
    fallback = Path(op_summary) if op_summary is not None else None
    if primary is not None and primary.is_file():
        label, path = "kernel_details", primary
    elif fallback is not None and fallback.is_file():
        label, path = "op_summary", fallback
    else:
        raise ValueError("neither kernel_details nor op_summary Task CSV exists")
    if not isinstance(expected_names, (list, tuple)) or not expected_names or any(not isinstance(name, str) or not name for name in expected_names):
        raise ValueError("complete-call kernel sequence is required")

    groups = []
    current = None
    marker_streams = []
    for name, kind, duration, stream_id in _rows(path, label):
        if eviction_type in kind and eviction_type in name:
            if current is not None:
                groups.append(current)
            current = []
            marker_streams.append(stream_id)
        elif current is None:
            raise ValueError("Task appeared before first L2 eviction marker")
        else:
            current.append((name, duration, stream_id))
    if current is not None:
        groups.append(current)
    if len(groups) != 20:
        raise ValueError(f"expected 20 complete calls, found {len(groups)}")
    if len(set(marker_streams)) != 1:
        raise ValueError("complete calls used multiple streams")

    values = []
    for index, group in enumerate(groups):
        if [row[0] for row in group] != list(expected_names):
            raise ValueError(f"call {index}: missing, extra, or reordered kernel")
        if len({stream for stream in (marker_streams[index], *(row[2] for row in group)) if stream}) > 1:
            raise ValueError(f"call {index}: eviction and target used multiple streams")
        total = float(sum((row[1] for row in group), Decimal(0)))
        if not math.isfinite(total) or total <= 0:
            raise ValueError(f"call {index}: complete-call duration exceeds numeric range")
        values.append(total)
    return {"table": label, "values_us": values, "median_us": median(values)}
