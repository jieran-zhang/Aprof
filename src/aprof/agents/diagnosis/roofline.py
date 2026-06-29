from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from aprof.core.models import (
    ArchitectureModel,
    ComponentSummary,
    Observation,
    TimeWindow,
    WindowAttribution,
)


def compute_window_attributions(
    observation: Observation, architecture: ArchitectureModel
) -> List[WindowAttribution]:
    attributions: List[WindowAttribution] = []

    for window in observation.windows:
        component = architecture.components.get(window.component)
        if component is None or window.duration_us <= 0:
            attributions.append(
                WindowAttribution(
                    index=window.index,
                    component=window.component,
                    name=window.name,
                    start_us=window.start_us,
                    end_us=window.end_us,
                    duration_us=window.duration_us,
                    observed=0.0,
                    attainable=0.0,
                    utilization=None,
                    unit="unknown",
                    evidence="missing component limit",
                )
            )
            continue

        demand = _window_demand(window, component.kind)
        observed = demand / window.duration_us if window.duration_us else 0.0
        attainable = component.limit_per_us
        utilization = observed / attainable if attainable > 0 else None

        attributions.append(
            WindowAttribution(
                index=window.index,
                component=window.component,
                name=window.name,
                start_us=window.start_us,
                end_us=window.end_us,
                duration_us=window.duration_us,
                observed=observed,
                attainable=attainable,
                utilization=utilization,
                unit=component.unit,
                evidence=_evidence_label(component.kind, demand),
                local_bottleneck=bool(utilization is not None and utilization >= 0.8),
            )
        )

    return attributions


def summarize_components(
    observation: Observation,
    architecture: ArchitectureModel,
    windows: List[WindowAttribution],
) -> List[ComponentSummary]:
    total_duration = _total_duration(observation)
    by_component: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"time": 0.0, "demand": 0.0}
    )

    raw_windows = {window.index: window for window in observation.windows}
    for attribution in windows:
        component = architecture.components.get(attribution.component)
        if component is None:
            continue
        raw_window = raw_windows[attribution.index]
        by_component[attribution.component]["time"] += attribution.duration_us
        by_component[attribution.component]["demand"] += _window_demand(
            raw_window, component.kind
        )

    summaries: List[ComponentSummary] = []
    for name, values in sorted(
        by_component.items(), key=lambda item: item[1]["time"], reverse=True
    ):
        component = architecture.components[name]
        active_time = values["time"]
        observed = values["demand"] / active_time if active_time > 0 else 0.0
        attainable = component.limit_per_us
        utilization: Optional[float] = (
            observed / attainable if attainable > 0 else None
        )
        summaries.append(
            ComponentSummary(
                component=name,
                kind=component.kind,
                active_time_us=active_time,
                time_fraction=active_time / total_duration if total_duration else 0.0,
                observed=observed,
                attainable=attainable,
                utilization=utilization,
                unit=component.unit,
                source=component.source,
                confidence=component.confidence,
            )
        )
    return summaries


def idle_fraction(observation: Observation) -> float:
    total_duration = _total_duration(observation)
    if total_duration <= 0:
        return 0.0
    active = sum(window.duration_us for window in observation.windows)
    return max(0.0, (total_duration - active) / total_duration)


def aggregate_roofline(
    observation: Observation,
    architecture: ArchitectureModel,
    windows: List[WindowAttribution],
) -> Dict[str, Any]:
    """Build a coarse baseline that intentionally drops time-axis locality."""

    total_duration = _total_duration(observation)
    raw_windows = {window.index: window for window in observation.windows}
    components: List[Dict[str, Any]] = []

    for component_name, component in architecture.components.items():
        component_windows = [
            window for window in windows if window.component == component_name
        ]
        if not component_windows or total_duration <= 0:
            continue
        demand = sum(
            _window_demand(raw_windows[window.index], component.kind)
            for window in component_windows
        )
        observed_elapsed = demand / total_duration
        utilization_elapsed = (
            observed_elapsed / component.limit_per_us
            if component.limit_per_us > 0
            else None
        )
        max_window_utilization = max(
            (
                window.utilization or 0.0
                for window in component_windows
                if window.utilization is not None
            ),
            default=0.0,
        )
        components.append(
            {
                "component": component_name,
                "kind": component.kind,
                "observed_elapsed": observed_elapsed,
                "attainable": component.limit_per_us,
                "elapsed_utilization": utilization_elapsed,
                "max_window_utilization": max_window_utilization,
                "active_time_us": sum(window.duration_us for window in component_windows),
                "time_fraction": sum(window.duration_us for window in component_windows)
                / total_duration,
                "unit": component.unit,
            }
        )

    hidden_local_bottlenecks = [
        item["component"]
        for item in components
        if (item["elapsed_utilization"] or 0.0) < 0.8
        and item["max_window_utilization"] >= 0.8
        and item["time_fraction"] >= 0.1
    ]

    return {
        "total_duration_us": total_duration,
        "components": sorted(
            components,
            key=lambda item: item["max_window_utilization"],
            reverse=True,
        ),
        "hidden_local_bottlenecks": hidden_local_bottlenecks,
        "interpretation": (
            "aggregate roofline hides phase-local saturation"
            if hidden_local_bottlenecks
            else "aggregate roofline and time-axis roofline agree at this threshold"
        ),
    }


def _window_demand(window: TimeWindow, component_kind: str) -> float:
    if component_kind in {"data_movement", "memory"}:
        return window.bytes_moved
    if component_kind in {"compute", "control"}:
        return window.ops
    return max(window.ops, window.bytes_moved, window.cycles)


def _evidence_label(component_kind: str, demand: float) -> str:
    if component_kind in {"data_movement", "memory"}:
        return f"{demand:.0f} bytes moved in window"
    if component_kind in {"compute", "control"}:
        return f"{demand:.0f} operations in window"
    return f"{demand:.0f} demand units in window"


def _total_duration(observation: Observation) -> float:
    if observation.metadata.total_duration_us > 0:
        return observation.metadata.total_duration_us
    if not observation.windows:
        return 0.0
    return max(window.end_us for window in observation.windows)
