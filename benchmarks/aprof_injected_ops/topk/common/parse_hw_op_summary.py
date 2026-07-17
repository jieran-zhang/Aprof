#!/usr/bin/env python3
"""Parse Task Duration(us) from msprof op hardware CSV (OpBasicInfo or op_summary)."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path


def find_hw_csv(root: Path) -> Path | None:
    patterns = ("OpBasicInfo.csv", "op_summary_*.csv")
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(root.rglob(pattern))
    if not matches:
        return None
    return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def parse_task_duration_us(csv_path: Path, kernel_name: str = "fast_gelu_kernel") -> float | None:
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            op = (row.get("Op Name") or row.get("op_name") or "").strip()
            if kernel_name not in op and op:
                continue
            raw = row.get("Task Duration(us)") or row.get("Task Duration")
            if not raw:
                continue
            return float(str(raw).strip().replace(",", ""))
    return None


def parse_task_duration_from_text(text: str) -> float | None:
    match = re.search(r"Task Duration\(us\):\s*([\d.]+)", text)
    if not match:
        return None
    return float(match.group(1))


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: parse_hw_op_summary.py <msprof_hw_output_dir> [kernel_name]", file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    kernel = sys.argv[2] if len(sys.argv) > 2 else "fast_gelu_kernel"
    summary = find_hw_csv(root)
    if summary is None:
        print("null")
        return 1
    duration = parse_task_duration_us(summary, kernel)
    if duration is None:
        print("null")
        return 1
    print(f"{duration}")
    print(summary, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
