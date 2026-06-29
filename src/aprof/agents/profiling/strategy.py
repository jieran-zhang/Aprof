from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import subprocess
from typing import Optional

from aprof.profiling.case_io import load_case_metadata
from aprof.core.models import ProfilingPlan


class ProfilingStrategyAgent:
    """Choose a targeted single-core msprof simulator command for one case."""

    def plan(self, case_dir: str | Path, hypothesis: str = "") -> ProfilingPlan:
        case = Path(case_dir).resolve()
        metadata = load_case_metadata(case)
        op = metadata.get("op_name", case.parents[1].name if len(case.parents) > 1 else "unknown")
        variant = metadata.get("variant", case.name)
        command = ["bash", str(case / "run.sh"), "sim", "--blockdim", "1"]
        if variant == "inject_tilelen_small":
            command += ["--output-elements", "256", "--tile-length", "16"]
        elif variant == "inject_tail":
            command += ["--output-elements", "257", "--tile-length", "256"]
        else:
            command += ["--output-elements", "256", "--tile-length", str(metadata.get("tile_length", 256))]
        return ProfilingPlan(
            case_dir=str(case),
            command=command,
            reason=hypothesis or f"single-core targeted capture for {op}/{variant}",
            expected_artifacts=["trace.json", "visualize_data.bin", "*_instr_exe_*.csv", "*_code_exe_*.csv"],
        )

    def run(self, case_dir: str | Path, hypothesis: str = "", timeout: Optional[int] = None) -> dict:
        plan = self.plan(case_dir, hypothesis)
        proc = subprocess.run(plan.command, cwd=plan.case_dir, text=True, capture_output=True, timeout=timeout)
        result = {"plan": asdict(plan), "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
        Path(plan.case_dir, "profiling_plan.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return result
