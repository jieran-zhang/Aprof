"""Reconstruct complete-call kernel times from CANN-style profiler CSVs.

The caller must supply one expected kernel sequence for every formal call. A
dedicated cache-eviction kernel separates calls; its duration is never scored.
This parser is exploratory and does not change a frozen APROF gate.
"""

from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median


def _rows(path: Path, source: str):
    columns = ("Name", "Type", "Duration(us)") if source == "kernel_details" else (
        "Op Name", "OP Type", "Task Duration(us)")
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not set(columns).issubset(reader.fieldnames):
            raise ValueError(f"{source}: missing required CSV columns")
        rows = []
        for index, row in enumerate(reader, 2):
            name, kind, duration = ((row.get(key) or "").strip() for key in columns)
            if not name or not kind:
                raise ValueError(f"{source}: missing kernel identity at row {index}")
            try:
                value = Decimal(duration)
            except InvalidOperation as exc:
                raise ValueError(f"{source}: invalid duration at row {index}") from exc
            if not value.is_finite() or value <= 0:
                raise ValueError(f"{source}: nonpositive duration at row {index}")
            stream_id = (row.get("Stream ID") or row.get("Stream Id") or "").strip()
            rows.append((name, kind, value, stream_id))
    if not rows:
        raise ValueError(f"{source}: empty kernel table")
    return rows


def parse_complete_calls(kernel_details, op_summary, expected_steps,
                         *, eviction_type="CannBenchCacheClean"):
    """Return one summed kernel duration per complete call, in expected order.

    ``expected_steps`` is a sequence of ``(role, kernel_names)`` pairs from the
    native runner's immutable journal. The CSV must contain one eviction marker
    before every call. Only *absent* kernel_details.csv permits op_summary
    fallback; an incomplete primary table is an error.
    """
    primary = Path(kernel_details) if kernel_details is not None else None
    fallback = Path(op_summary) if op_summary is not None else None
    if primary is not None and primary.is_file():
        source, path = "kernel_details", primary
    elif fallback is not None and fallback.is_file():
        source, path = "op_summary", fallback
    else:
        raise ValueError("neither kernel_details.csv nor op_summary CSV is present")
    if not expected_steps or not isinstance(eviction_type, str) or not eviction_type:
        raise ValueError("expected calls and eviction kernel type are required")
    steps = []
    for role, names in expected_steps:
        if not isinstance(role, str) or not role or not names or any(
                not isinstance(name, str) or not name for name in names):
            raise ValueError("invalid expected complete-call kernel sequence")
        steps.append((role, tuple(names)))

    calls = []
    current = None
    for name, kind, duration, stream_id in _rows(path, source):
        if eviction_type in kind:
            if current is not None:
                calls.append(current)
            current = []
            continue
        if current is None:
            raise ValueError("target kernel appeared before first L2 eviction marker")
        current.append((name, duration, stream_id))
    if current is not None:
        calls.append(current)
    if len(calls) != len(steps):
        raise ValueError(f"expected {len(steps)} complete calls, found {len(calls)}")

    samples = []
    for index, ((role, names), kernels) in enumerate(zip(steps, calls)):
        if tuple(row[0] for row in kernels) != names:
            raise ValueError(f"complete call {index} has missing, extra, or reordered kernels")
        streams = {row[2] for row in kernels if row[2]}
        if len(streams) > 1:
            raise ValueError(f"complete call {index} used multiple streams")
        samples.append(dict(index=index, role=role, kernel_names=list(names),
                            kernel_us=[float(row[1]) for row in kernels],
                            complete_call_us=float(sum((row[1] for row in kernels), Decimal(0))),
                            stream_id=next(iter(streams), None)))
    roles = dict.fromkeys(role for role, _ in steps)
    return dict(source=source, eviction_type=eviction_type, eviction_count=len(calls),
                samples=samples, median_complete_call_us={
                    role: median(sample["complete_call_us"] for sample in samples
                                 if sample["role"] == role) for role in roles})
