from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Protocol

from aprof.core.models import Observation, ProfilingRequest, ProfilingSkillResult


@dataclass(frozen=True)
class SkillSpec:
    name: str
    backend: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    preconditions: List[str]
    description: str = ""


class ProfilingSkill(Protocol):
    spec: SkillSpec

    def detect_artifacts(self, observation: Observation) -> ProfilingSkillResult:
        ...


@dataclass(frozen=True)
class ArtifactProfilingSkill:
    spec: SkillSpec
    artifact_keys: List[str]

    def detect_artifacts(self, observation: Observation) -> ProfilingSkillResult:
        artifacts = {
            key: observation.artifacts.get(key)
            for key in self.artifact_keys
            if key in observation.artifacts
        }
        missing = [key for key in self.artifact_keys if not observation.artifacts.get(key)]
        return ProfilingSkillResult(
            skill_name=self.spec.name,
            status="missing" if missing else "available",
            outputs={
                "available_artifacts": sorted(artifacts),
                "missing_artifacts": missing,
            },
            artifacts=artifacts,
        )


class SkillRegistry:
    def __init__(self, skills: Iterable[ProfilingSkill] | None = None) -> None:
        self._skills: Dict[str, ProfilingSkill] = {}
        for skill in skills or []:
            self.register(skill)

    def register(self, skill: ProfilingSkill) -> None:
        name = skill.spec.name
        if name in self._skills:
            raise ValueError(f"profiling skill is already registered: {name}")
        self._skills[name] = skill

    def get(self, name: str) -> ProfilingSkill:
        try:
            return self._skills[name]
        except KeyError as exc:
            raise KeyError(f"unknown profiling skill: {name}") from exc

    def list_specs(self) -> List[SkillSpec]:
        return [skill.spec for skill in self._skills.values()]

    def validate_request(self, request: ProfilingRequest) -> None:
        if request.skill_name not in self._skills:
            raise ValueError(
                f"profiling request references unknown skill: {request.skill_name}"
            )

    def validate_requests(self, requests: Iterable[ProfilingRequest]) -> None:
        for request in requests:
            self.validate_request(request)


def default_skill_registry() -> SkillRegistry:
    return SkillRegistry(
        [
            ArtifactProfilingSkill(
                spec=SkillSpec(
                    name="collect_operator_timeline",
                    backend="msprof",
                    description="Collect operator execution windows from msprof simulator trace output.",
                    inputs={
                        "operator_name": "string",
                        "shape": "string",
                        "kernel_version": "string",
                        "profile_output": "path",
                    },
                    outputs={
                        "trace_json": "path",
                        "execution_windows": "list[TimeWindow]",
                        "time_axis_metrics": "list[WindowAttribution]",
                    },
                    preconditions=[
                        "workload is compiled",
                        "input shape is fixed",
                        "Ascend runtime environment is available",
                    ],
                ),
                artifact_keys=["has_trace", "trace_json"],
            ),
            ArtifactProfilingSkill(
                spec=SkillSpec(
                    name="collect_code_hotspots",
                    backend="msprof",
                    description="Collect source-level code hotspot CSVs from a debug-enabled msprof run.",
                    inputs={
                        "operator_name": "string",
                        "kernel_version": "string",
                        "source_root": "path",
                        "profile_output": "path",
                    },
                    outputs={
                        "code_hotspot_csvs": "list[path]",
                        "code_hotspots": "list[CodeHotspot]",
                    },
                    preconditions=[
                        "workload is compiled with source/debug information",
                        "source root is available when source mapping is required",
                        "Ascend runtime environment is available",
                    ],
                ),
                artifact_keys=["has_code_hotspots", "code_hotspot_csvs"],
            ),
            ArtifactProfilingSkill(
                spec=SkillSpec(
                    name="extract_time_window_metrics",
                    backend="aprof",
                    description="Normalize timeline and counter artifacts into per-window roofline inputs.",
                    inputs={
                        "trace_json": "path",
                        "code_hotspot_csvs": "list[path]",
                        "architecture": "ArchitectureModel",
                    },
                    outputs={
                        "windows": "list[TimeWindow]",
                        "component_summary": "list[ComponentSummary]",
                        "aggregate_roofline": "object",
                    },
                    preconditions=[
                        "timeline or hotspot artifacts are present",
                        "architecture model is loaded",
                    ],
                ),
                artifact_keys=["has_trace", "has_code_hotspots"],
            ),
            ArtifactProfilingSkill(
                spec=SkillSpec(
                    name="collect_memory_behavior",
                    backend="msprof",
                    description="Collect or infer memory/data-movement behavior from trace and CSV artifacts.",
                    inputs={
                        "operator_name": "string",
                        "kernel_version": "string",
                        "profile_output": "path",
                    },
                    outputs={
                        "data_movement_windows": "list[TimeWindow]",
                        "memory_artifacts": "object",
                        "bandwidth_proxy": "object",
                    },
                    preconditions=[
                        "timeline or instruction artifacts are available",
                        "workload uses a fixed input shape",
                    ],
                ),
                artifact_keys=["has_trace", "has_instruction_csv", "has_visualize_data"],
            ),
            ArtifactProfilingSkill(
                spec=SkillSpec(
                    name="collect_compute_utilization",
                    backend="msprof",
                    description="Collect or infer compute-path utilization from trace and CSV artifacts.",
                    inputs={
                        "operator_name": "string",
                        "kernel_version": "string",
                        "component": "string",
                        "profile_output": "path",
                    },
                    outputs={
                        "compute_windows": "list[TimeWindow]",
                        "component_utilization": "object",
                        "instruction_mix_proxy": "object",
                    },
                    preconditions=[
                        "timeline or code hotspot artifacts are available",
                        "architecture limit for the target component is known or being calibrated",
                    ],
                ),
                artifact_keys=["has_trace", "has_code_hotspots", "has_instruction_csv"],
            ),
        ]
    )


DEFAULT_SKILL_REGISTRY = default_skill_registry()


def skill_specs_to_dicts(registry: SkillRegistry = DEFAULT_SKILL_REGISTRY) -> List[Dict[str, Any]]:
    return [asdict(spec) for spec in registry.list_specs()]
