from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from aprof.metrics.architecture import load_architecture
from aprof.agents.diagnosis.attribution import analyze_observation
from aprof.agents.profiling.model_client import LocalHeuristicModelClient, ModelClient, ProblemReport, write_problem_report
from aprof.core.models import AnalysisResult, ProfilingRequest
from aprof.profiling.msprof import (
    MsprofRunRequest,
    MsprofRunResult,
    parse_msprof_simulator,
    probe_msprof_environment,
    run_msprof_simulator,
)
from aprof.reports.analysis import write_analysis_report, write_environment_report


@dataclass(frozen=True)
class HarnessRequest:
    arch: str
    out_dir: str
    executable: Optional[str] = None
    source_root: Optional[str] = None
    input_path: Optional[str] = None
    run: bool = False
    profile_output: Optional[str] = None
    soc_version: str = "Ascend910B1"
    operator_name: str = "AscendC_Sample"
    kernel_version: str = "sample_v0"
    shape: str = "unknown"
    data_type: str = "unknown"
    kernel_name: Optional[str] = None
    config: Optional[str] = None
    core_id: Optional[int] = 0
    aic_metrics: Optional[str] = "PipeUtilization,ResourceConflictRatio"
    launch_count: Optional[int] = 1
    env_script: Optional[str] = None
    cwd: Optional[str] = None
    timeout_seconds: Optional[float] = None


@dataclass(frozen=True)
class HarnessResult:
    request: HarnessRequest
    profile_input: str
    analysis: AnalysisResult
    next_profiling_requests: List[ProfilingRequest]
    problems: ProblemReport
    environment: Dict[str, Any]
    run_result: Optional[MsprofRunResult]
    harness_path: str


def run_harness(
    request: HarnessRequest, model_client: Optional[ModelClient] = None
) -> HarnessResult:
    return run_harness_once(request, model_client=model_client)


def run_harness_once(
    request: HarnessRequest, model_client: Optional[ModelClient] = None
) -> HarnessResult:
    out_dir = Path(request.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    profile_input = _profile_input_path(request, out_dir)
    run_result: Optional[MsprofRunResult] = None

    if request.run:
        if not request.executable:
            raise ValueError("--executable is required when --run is set")
        _write_metadata(request, profile_input)
        run_result = run_msprof_simulator(
            MsprofRunRequest(
                executable=request.executable,
                output=str(profile_input),
                soc_version=request.soc_version,
                core_id=request.core_id,
                kernel_name=request.kernel_name,
                config=request.config,
                aic_metrics=request.aic_metrics,
                launch_count=request.launch_count,
                env_script=request.env_script,
                cwd=request.cwd,
                timeout_seconds=request.timeout_seconds,
            )
        )
        if run_result.returncode not in (0, None) or run_result.timed_out:
            _write_harness_record(request, profile_input, out_dir, run_result, None, None)
            raise RuntimeError(run_result.error or "msprof simulator failed")

    environment = (
        run_result.environment
        if run_result is not None
        else probe_msprof_environment(request.soc_version)
    )
    write_environment_report(environment, out_dir / "environment")

    observation = parse_msprof_simulator(profile_input)
    architecture = load_architecture(request.arch)
    analysis = analyze_observation(observation, architecture)
    write_analysis_report(analysis, out_dir)

    context = _harness_context(request, profile_input, observation_artifacts=observation.artifacts)
    client = model_client or LocalHeuristicModelClient()
    problems = client.assess(analysis, context)
    write_problem_report(problems, out_dir)

    harness_path = _write_harness_record(
        request, profile_input, out_dir, run_result, analysis, problems
    )
    return HarnessResult(
        request=request,
        profile_input=str(profile_input),
        analysis=analysis,
        next_profiling_requests=analysis.diagnosis.next_profiling_requests,
        problems=problems,
        environment=environment,
        run_result=run_result,
        harness_path=str(harness_path),
    )


def run_harness_loop(
    request: HarnessRequest,
    model_client: Optional[ModelClient] = None,
    max_iterations: int = 1,
) -> List[HarnessResult]:
    if max_iterations != 1:
        raise NotImplementedError(
            "automatic profiling loops are not enabled yet; run one harness iteration"
        )
    return [run_harness_once(request, model_client=model_client)]


def _profile_input_path(request: HarnessRequest, out_dir: Path) -> Path:
    if request.run:
        return Path(request.profile_output) if request.profile_output else out_dir / "raw"
    if request.input_path:
        return Path(request.input_path)
    if request.profile_output:
        return Path(request.profile_output)
    return out_dir / "raw"


def _write_metadata(request: HarnessRequest, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    metadata = {
        "operator_name": request.operator_name,
        "kernel_version": request.kernel_version,
        "shape": request.shape,
        "data_type": request.data_type,
        "soc_version": request.soc_version,
        "total_duration_us": 0.0,
        "notes": "Generated by AProf harness for real msprof simulator collection.",
    }
    (output / "aprof_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _write_harness_record(
    request: HarnessRequest,
    profile_input: Path,
    out_dir: Path,
    run_result: Optional[MsprofRunResult],
    analysis: Optional[AnalysisResult],
    problems: Optional[ProblemReport],
) -> Path:
    next_requests = (
        [asdict(item) for item in analysis.diagnosis.next_profiling_requests]
        if analysis
        else []
    )
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "request": asdict(request),
        "profile_input": str(profile_input),
        "source_summary": _summarize_source_root(request.source_root),
        "run_result": run_result.to_dict() if run_result else None,
        "analysis": {
            "bottleneck_class": analysis.diagnosis.bottleneck_class,
            "confidence": analysis.diagnosis.confidence,
            "parsed_windows": len(analysis.windows),
            "parsed_hotspots": len(analysis.hotspots),
            "next_profiling_requests": next_requests,
        }
        if analysis
        else None,
        "problems": problems.to_dict() if problems else None,
    }
    path = out_dir / "harness.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    collection = {
        "created_at": payload["created_at"],
        "harness": str(path),
        "profile_input": str(profile_input),
        "executed": run_result.executed if run_result else False,
        "returncode": run_result.returncode if run_result else None,
        "parsed_windows": len(analysis.windows) if analysis else 0,
        "parsed_hotspots": len(analysis.hotspots) if analysis else 0,
        "next_profiling_requests": next_requests,
        "problems": problems.to_dict() if problems else None,
    }
    (out_dir / "collection.json").write_text(
        json.dumps(collection, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path


def _harness_context(
    request: HarnessRequest, profile_input: Path, observation_artifacts: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "executable": request.executable,
        "source_root": request.source_root,
        "profile_input": str(profile_input),
        "soc_version": request.soc_version,
        "operator_name": request.operator_name,
        "kernel_version": request.kernel_version,
        "shape": request.shape,
        "data_type": request.data_type,
        "artifacts": observation_artifacts,
        "source_summary": _summarize_source_root(request.source_root),
    }


def _summarize_source_root(source_root: Optional[str]) -> Dict[str, Any]:
    if not source_root:
        return {"provided": False}
    root = Path(source_root)
    if not root.exists():
        return {"provided": True, "path": str(root), "exists": False}

    suffix_counts: Dict[str, int] = {}
    file_count = 0
    sample_files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        file_count += 1
        suffix = path.suffix or "<none>"
        suffix_counts[suffix] = suffix_counts.get(suffix, 0) + 1
        if len(sample_files) < 10:
            sample_files.append(str(path.relative_to(root)))

    return {
        "provided": True,
        "path": str(root),
        "exists": True,
        "file_count": file_count,
        "suffix_counts": suffix_counts,
        "sample_files": sample_files,
    }
