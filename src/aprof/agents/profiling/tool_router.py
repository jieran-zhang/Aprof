from __future__ import annotations

from dataclasses import asdict
from typing import Any

from aprof.core.models import ProfilingPlan, ProfilingRequest
from aprof.profiling.skills import DEFAULT_SKILL_REGISTRY, SkillRegistry


class ProfilingToolRouter:
    """Route profiling requests to registered skills and msprof commands."""

    def __init__(self, registry: SkillRegistry | None = None) -> None:
        self.registry = registry or DEFAULT_SKILL_REGISTRY

    def list_skills(self) -> list[dict[str, Any]]:
        return [asdict(spec) for spec in self.registry.list_specs()]

    def validate_requests(self, requests: list[ProfilingRequest]) -> None:
        self.registry.validate_requests(requests)

    def route(self, request: ProfilingRequest) -> dict[str, Any]:
        skill = self.registry.get(request.skill_name)
        return {
            "skill_name": request.skill_name,
            "backend": skill.spec.backend,
            "reason": request.reason,
            "required_evidence": request.required_evidence,
            "preconditions": request.preconditions or skill.spec.preconditions,
            "expected_outputs": request.expected_outputs or list(skill.spec.outputs.keys()),
        }

    def plan_to_command(self, plan: ProfilingPlan) -> list[str]:
        return list(plan.command)
