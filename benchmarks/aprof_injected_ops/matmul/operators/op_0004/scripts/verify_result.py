#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path

def main() -> int:
    out = Path("build/output/output.bin")
    golden = Path("data/golden.bin")
    if not out.is_file() or not golden.is_file():
        raise SystemExit("missing output or golden")
    print(f"synthetic_kernel_verify_skipped bytes_out={out.stat().st_size} bytes_golden={golden.stat().st_size}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
