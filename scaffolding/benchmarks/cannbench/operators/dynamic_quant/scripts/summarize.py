#!/usr/bin/env python3
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = sorted((root / "build/cases").glob("case_*/result.json"))
cases = [json.loads(path.read_text()) for path in files]
out = {
    "operator": "dynamic_quant",
    "soc_version": "Ascend910",
    "npu_arch": "dav-2201",
    "total_cases": 20,
    "passed_cases": sum(item["passed"] for item in cases),
    "all_passed": len(cases) == 20 and all(item["passed"] for item in cases),
    "cases": cases,
}
(root / "results.json").write_text(json.dumps(out, indent=2))
print(json.dumps({key: value for key, value in out.items() if key != "cases"}))
if not out["all_passed"]:
    raise SystemExit(1)
