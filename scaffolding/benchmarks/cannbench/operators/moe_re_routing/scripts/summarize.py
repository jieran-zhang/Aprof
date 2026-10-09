#!/usr/bin/env python3
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cases = [json.loads(p.read_text()) for p in sorted((root / "build/cases").glob("case_*/result.json"))]
result = {
    "operator": "moe_re_routing", "soc_version": "Ascend910_9362", "npu_arch": "dav-2201",
    "total_cases": 20, "passed_cases": sum(x["passed"] for x in cases),
    "all_passed": len(cases) == 20 and all(x["passed"] for x in cases),
    "performance_status": "not_collected_per_user", "cases": cases
}
(root / "results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
print(json.dumps({k: v for k, v in result.items() if k != "cases"}, ensure_ascii=False))
raise SystemExit(0 if result["all_passed"] else 1)
