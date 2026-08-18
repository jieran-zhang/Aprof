#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cases = []
for case_id in range(1, 21):
    path = ROOT / "build/cases" / f"case_{case_id:02d}" / "precision.json"
    if not path.exists():
        raise SystemExit(f"missing {path}")
    cases.append(json.loads(path.read_text()))
out = ROOT / "docs/precision"
out.mkdir(parents=True, exist_ok=True)
(out / "cases.json").write_text(json.dumps(cases, indent=2, ensure_ascii=False))
passed = sum(bool(case["precision_pass"]) for case in cases)
summary = [f"apply_adam_w real-NPU precision: {passed}/20 passed", "device=0, npu_arch=dav-2201, CANN=9.0.0"]
for case in cases:
    summary.append(f"case {case['case_id']:02d}: {'PASS' if case['precision_pass'] else 'FAIL'} "
                   f"dtype={case['dtype']} MERE={case['MERE']:.9g} MARE={case['MARE']:.9g}")
(out / "summary.txt").write_text("\n".join(summary) + "\n")
print(summary[0])
raise SystemExit(0 if passed == 20 else 1)
