#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import asdict

from aprof.benchmarks.closed_loop import run_swiglu_alignment


def main() -> int:
    rows = run_swiglu_alignment()
    print(json.dumps([asdict(row) for row in rows], indent=2, ensure_ascii=False))
    return 0 if all(row.match for row in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
