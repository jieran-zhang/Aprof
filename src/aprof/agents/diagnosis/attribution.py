from __future__ import annotations

from typing import Iterable, List, Optional

from aprof.core.models import (
    AnalysisResult,
    ArchitectureModel,
    Diagnosis,
    Observation,
    ProfilingRequest,
)
from aprof.agents.diagnosis.roofline import (
    aggregate_roofline,
    compute_window_attributions,
    idle_fraction,
    summarize_components,
)
from aprof.profiling.skills import DEFAULT_SKILL_REGISTRY


HIGH_UTILIZATION = 0.8
MEANINGFUL_PHASE = 0.25


def analyze_observation(
    observation: Observation, architecture: ArchitectureModel
) -> AnalysisResult:
    windows = compute_window_attributions(observation, architecture)
    components = summarize_components(observation, architecture, windows)
    idle = idle_fraction(observation)
    aggregate = aggregate_roofline(observation, architecture, windows)
    diagnosis = diagnose(observation, architecture, components, windows, idle, aggregate)

    return AnalysisResult(
        metadata=observation.metadata,
        architecture=architecture.soc_version,
        input_path=observation.input_path,
        windows=windows,
        components=components,
        idle_fraction=idle,
        hotspots=observation.hotspots[:10],
        diagnosis=diagnosis,
        aggregate=aggregate,
    )


def diagnose(observation, architecture, components, windows, idle, aggregate) -> Diagnosis:
    missing_evidence: List[str] = []
    next_requests: List[ProfilingRequest] = []
    if not observation.artifacts.get("has_trace", bool(observation.windows)):
        missing_evidence.append("trace windows are unavailable")
        next_requests.append(
            _profiling_request(
                "collect_operator_timeline",
                reason="AProf needs timeline trace events to build operator execution windows.",
                required_evidence=["trace windows"],
            )
        )
    if not observation.artifacts.get("has_code_hotspots", bool(observation.hotspots)):
        missing_evidence.append("code hotspot CSV is unavailable")
        next_requests.append(
            _profiling_request(
                "collect_code_hotspots",
                reason="AProf needs source hotspot CSVs to map time back to kernel code.",
                required_evidence=["code hotspots"],
            )
        )
    if any(window.utilization is None for window in windows):
        missing_evidence.append("one or more components have no architecture limit")
        unknown_components = sorted(
            {window.component for window in windows if window.utilization is None}
        )
        next_requests.append(
            _profiling_request(
                "collect_compute_utilization",
                reason=(
                    "AProf needs component-local utilization evidence for "
                    f"{', '.join(unknown_components) or 'unknown components'}."
                ),
                required_evidence=[
                    "component utilization",
                    "architecture limit source",
                ],
                preconditions=[
                    "target component can be isolated in the profile",
                    "architecture limit can be documented, measured, or calibrated",
                ],
            )
        )

    high_windows = [
        window
        for window in windows
        if window.utilization is not None and window.utilization >= HIGH_UTILIZATION
    ]
    high_components = [
        component
        for component in components
        if component.utilization is not None
        and component.utilization >= HIGH_UTILIZATION
        and component.time_fraction >= MEANINGFUL_PHASE
    ]

    scalar = _component(components, "scalar")
    vector = _component(components, "vector")
    data_movers = [
        component for component in components if component.component in {"mte2", "mte3", "gm"}
    ]
    data_movement_fraction = sum(component.time_fraction for component in data_movers)
    high_data_movers = [
        component
        for component in data_movers
        if component.utilization is not None and component.utilization >= HIGH_UTILIZATION
    ]
    hidden_local = aggregate.get("hidden_local_bottlenecks", [])

    if idle >= 0.2:
        return Diagnosis(
            bottleneck_class="idle_or_synchronization",
            responsible_components=["idle"],
            responsible_windows=[],
            confidence="medium",
            missing_evidence=missing_evidence,
            recommendation="continue: reduce launch gaps, synchronization, or non-kernel overhead before tuning compute paths",
            rationale=[
                f"idle fraction is {idle:.1%}, so aggregate roofline points hide non-active time"
            ],
            agent_actions=[
                "collect a shorter timeline around launch/synchronization boundaries",
                "check harness invariants before tuning compute or memory code",
            ],
            next_profiling_requests=_merge_requests(
                next_requests,
                [
                    _profiling_request(
                        "collect_operator_timeline",
                        reason="Idle or synchronization gaps require a tighter operator timeline.",
                        required_evidence=["launch gaps", "synchronization boundaries"],
                    )
                ],
            ),
        )

    if scalar and scalar.time_fraction >= 0.35:
        hotspot_codes = [hotspot.code for hotspot in observation.hotspots[:3]]
        return Diagnosis(
            bottleneck_class="scalar_control_overhead",
            responsible_components=["scalar"],
            responsible_windows=_window_ids(windows, "scalar"),
            confidence="high" if observation.hotspots else "medium",
            missing_evidence=missing_evidence,
            recommendation="continue: move invariant scalar work to host/tiling or remove debug/control work in the kernel",
            rationale=[
                f"scalar/control windows consume {scalar.time_fraction:.1%} of task time",
                f"top hotspot lines: {', '.join(hotspot_codes)}"
                if hotspot_codes
                else "no source hotspot lines were available",
            ],
            agent_actions=[
                "inspect scalar hotspot lines and move invariant work out of the kernel",
                _next_experiment(architecture, "scalar"),
            ],
            next_profiling_requests=_merge_requests(
                next_requests,
                [
                    _profiling_request(
                        "collect_code_hotspots",
                        reason="Scalar control overhead should be tied to source hotspot lines.",
                        required_evidence=["scalar source hotspots"],
                    )
                ],
            ),
        )

    mixed_candidates = [component.component for component in high_components] or hidden_local
    mixed_kinds = {
        architecture.components[component].kind
        for component in mixed_candidates
        if component in architecture.components
    }
    is_mixed_phase = (
        len(mixed_candidates) >= 2
        and len(mixed_kinds - {"control", "idle"}) >= 2
        and data_movement_fraction < 0.5
    )

    if is_mixed_phase:
        responsible = mixed_candidates
        return Diagnosis(
            bottleneck_class="mixed_phase_bottleneck",
            responsible_components=responsible,
            responsible_windows=[window.index for window in high_windows],
            confidence="high" if hidden_local else "medium",
            missing_evidence=missing_evidence,
            recommendation="stop or change algorithm: multiple phase-local windows are close to attainable limits",
            rationale=[
                "per-window attribution finds multiple locally saturated components",
                _format_component_utils(high_components)
                if high_components
                else f"aggregate baseline hides local bottlenecks in {', '.join(hidden_local)}",
                f"aggregate baseline: {aggregate.get('interpretation', 'unknown')}",
            ],
            agent_actions=[
                "do not optimize only the global average; inspect responsible windows first",
                *[
                    _next_experiment(architecture, component)
                    for component in responsible[:3]
                ],
            ],
            next_profiling_requests=_merge_requests(
                next_requests,
                [
                    _profiling_request(
                        "extract_time_window_metrics",
                        reason="Mixed bottlenecks require per-window metrics before choosing a code change.",
                        required_evidence=["per-window component utilization"],
                    )
                ],
            ),
        )

    if data_movement_fraction >= 0.5:
        responsible = [component.component for component in high_data_movers] or [
            component.component for component in data_movers
        ]
        near_limit = bool(high_data_movers)
        return Diagnosis(
            bottleneck_class="memory_data_movement",
            responsible_components=responsible,
            responsible_windows=[
                window.index
                for window in high_windows
                if window.component in {"mte2", "mte3", "gm"}
            ],
            confidence="high" if near_limit else "medium",
            missing_evidence=missing_evidence,
            recommendation=(
                "stop: dominant data-movement windows are already near the software-aware attainable limit"
                if near_limit
                else "continue: memory/data-movement time dominates but bandwidth utilization is below the attainable limit"
            ),
            rationale=[
                f"data movement accounts for {data_movement_fraction:.1%} of active task time",
                _format_component_utils(data_movers),
            ],
            agent_actions=[
                "check tiling, double buffering, and GM-to-AICORE traffic for the responsible MTE windows",
                *[
                    _next_experiment(architecture, component)
                    for component in responsible[:2]
                ],
            ],
            next_profiling_requests=_merge_requests(
                next_requests,
                [
                    _profiling_request(
                        "collect_memory_behavior",
                        reason="Data-movement bottlenecks need memory and MTE behavior evidence.",
                        required_evidence=["data movement windows", "bandwidth proxy"],
                    )
                ],
            ),
        )

    if vector and vector.time_fraction >= 0.5:
        near_limit = vector.utilization is not None and vector.utilization >= HIGH_UTILIZATION
        return Diagnosis(
            bottleneck_class="vector_compute",
            responsible_components=["vector"],
            responsible_windows=_window_ids(windows, "vector"),
            confidence="high" if near_limit else "medium",
            missing_evidence=missing_evidence,
            recommendation=(
                "stop: vector compute is the dominant phase and is close to its attainable limit"
                if near_limit
                else "continue: vector compute dominates but utilization is below its attainable limit"
            ),
            rationale=[
                f"vector windows consume {vector.time_fraction:.1%} of active task time",
                f"vector utilization is {_fmt_util(vector.utilization)}",
            ],
            agent_actions=[
                "inspect vector instruction mix and data type path before generating more variants",
                _next_experiment(architecture, "vector"),
            ],
            next_profiling_requests=_merge_requests(
                next_requests,
                [
                    _profiling_request(
                        "collect_compute_utilization",
                        reason="Vector bottlenecks need compute-path utilization or instruction-mix evidence.",
                        required_evidence=["vector utilization", "instruction mix proxy"],
                    )
                ],
            ),
        )

    if components:
        dominant = components[0]
        return Diagnosis(
            bottleneck_class="underutilized",
            responsible_components=[dominant.component],
            responsible_windows=_window_ids(windows, dominant.component),
            confidence="medium",
            missing_evidence=missing_evidence,
            recommendation="continue: no dominant component is close to its attainable limit",
            rationale=[
                f"dominant component is {dominant.component} with utilization {_fmt_util(dominant.utilization)}"
            ],
            agent_actions=[
                "request additional profiling evidence before changing the algorithm",
                _next_experiment(architecture, dominant.component),
            ],
            next_profiling_requests=_merge_requests(
                next_requests,
                [
                    _profiling_request(
                        "collect_compute_utilization",
                        reason=(
                            "The dominant component is below its attainable limit and needs "
                            "component-local evidence."
                        ),
                        required_evidence=[f"{dominant.component} utilization"],
                    )
                ],
            ),
        )

    return Diagnosis(
        bottleneck_class="insufficient_evidence",
        responsible_components=[],
        responsible_windows=[],
        confidence="low",
        missing_evidence=missing_evidence or ["no trace windows were parsed"],
        recommendation="request additional profiling evidence",
        rationale=["AProf could not build a complete observation from the input"],
        agent_actions=[
            "collect simulator trace.json and code hotspot CSV with a -g build"
        ],
        next_profiling_requests=next_requests,
    )


def _component(components, name):
    for component in components:
        if component.component == name:
            return component
    return None


def _window_ids(windows, component: str) -> List[int]:
    return [window.index for window in windows if window.component == component]


def _format_component_utils(components: Iterable) -> str:
    return ", ".join(
        f"{component.component}={_fmt_util(component.utilization)}"
        for component in components
    )


def _fmt_util(value) -> str:
    return "unknown" if value is None else f"{value:.1%}"


def _profiling_request(
    skill_name: str,
    reason: str,
    required_evidence: List[str],
    preconditions: Optional[List[str]] = None,
    expected_outputs: Optional[List[str]] = None,
) -> ProfilingRequest:
    spec = DEFAULT_SKILL_REGISTRY.get(skill_name).spec
    return ProfilingRequest(
        skill_name=skill_name,
        reason=reason,
        required_evidence=required_evidence,
        preconditions=preconditions or spec.preconditions,
        expected_outputs=expected_outputs or list(spec.outputs.keys()),
    )


def _merge_requests(
    base: List[ProfilingRequest], extra: Iterable[ProfilingRequest]
) -> List[ProfilingRequest]:
    merged: List[ProfilingRequest] = []
    seen = set()
    for request in [*base, *extra]:
        if request.skill_name in seen:
            continue
        seen.add(request.skill_name)
        merged.append(request)
    return merged


def _next_experiment(architecture, component: str) -> str:
    limit = architecture.components.get(component)
    if limit and limit.next_experiment:
        return limit.next_experiment
    if limit and limit.required_evidence:
        return f"collect evidence for {component}: {', '.join(limit.required_evidence)}"
    return f"collect more component-local evidence for {component}"
