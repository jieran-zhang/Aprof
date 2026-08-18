#!/usr/bin/env python3
"""Audit whether an AProf graph contains substantive trainable decisions."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
from typing import Any


KNOWN_CONTEXT_ROOTS = {
    "operator",
    "hardware_fingerprint",
    "workload",
    "budget",
    "evidence",
}
RECOVERY_EDGE_TYPES = {"failure_transition", "recovery_transition"}


def _load_graph(path: Path) -> dict[str, Any]:
    location = path / "graph.json" if path.is_dir() else path
    try:
        value = json.loads(location.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read graph {location}: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("edges"), list):
        raise ValueError("graph must be an object with an edges array")
    return value


def audit(graph: dict[str, Any]) -> dict[str, Any]:
    edges = graph["edges"]
    supports = [edge for edge in edges if edge.get("edge_type") == "supports"]
    priors = [
        edge for edge in edges if edge.get("edge_type") == "problem_to_skill_prior"
    ]
    support_targets: dict[str, list[str]] = defaultdict(list)
    action_targets: dict[str, list[str]] = defaultdict(list)
    for edge in supports:
        support_targets[str(edge["source"])].append(str(edge["target"]))
    for edge in priors:
        action_targets[str(edge["source"])].append(str(edge["target"]))

    positive_actions = {
        mechanism: sorted(
            target for target in targets if target != "transformation.noop"
        )
        for mechanism, targets in action_targets.items()
    }
    symptom_branch_histogram = Counter(len(set(items)) for items in support_targets.values())
    positive_action_histogram = Counter(len(set(items)) for items in positive_actions.values())
    context_edges: list[str] = []
    unsupported_context_edges: list[str] = []
    predicate_only_edges: list[str] = []
    for edge in priors:
        conditions = edge.get("hard_preconditions", [])
        path_conditions = [
            item for item in conditions
            if isinstance(item, dict) and {"path", "op", "value"} <= item.keys()
        ]
        if path_conditions:
            if all(
                str(item["path"]).split(".", 1)[0] in KNOWN_CONTEXT_ROOTS
                for item in path_conditions
            ):
                context_edges.append(str(edge["id"]))
            else:
                unsupported_context_edges.append(str(edge["id"]))
        elif conditions:
            predicate_only_edges.append(str(edge["id"]))

    transformations = graph.get("transformations", [])
    parameterized_handlers: list[dict[str, Any]] = []
    for item in transformations:
        if item.get("id") == "transformation.noop":
            continue
        schema = item.get("parameter_schema", {})
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        enum_fields = {
            name: value.get("enum")
            for name, value in properties.items()
            if isinstance(value, dict) and isinstance(value.get("enum"), list)
        }
        parameterized_handlers.append(
            {
                "transformation_id": item.get("id"),
                "parameter_fields": sorted(properties),
                "enumerated_fields": enum_fields,
                "handler_nodes": 0,
                "handler_policy": "absent",
            }
        )

    extractor_states = Counter(
        str(item.get("evaluation", {}).get("implementation_status", "missing"))
        for item in graph.get("predicates", [])
    )
    multiple_problem_predicates = sorted(
        source for source, targets in support_targets.items() if len(set(targets)) > 1
    )
    multiple_positive_action_problems = sorted(
        source for source, targets in positive_actions.items() if len(set(targets)) > 1
    )
    all_edge_types = {str(edge.get("edge_type")) for edge in edges}
    recovery_edge_types = sorted(all_edge_types & RECOVERY_EDGE_TYPES)
    handler_nodes = graph.get("handlers", [])
    handler_branch_sources = Counter(
        str(item.get("transformation_id")) for item in handler_nodes
        if isinstance(item, dict) and item.get("transformation_id")
    )
    multiple_handler_transformations = sorted(
        source for source, count in handler_branch_sources.items() if count > 1
    )
    topological_dimensions_complete = bool(
        multiple_problem_predicates
        and multiple_positive_action_problems
        and context_edges
        and multiple_handler_transformations
        and recovery_edge_types
    )
    return {
        "schema_version": "1.0.0",
        "graph_version": graph.get("graph_version"),
        "counts": {
            "predicates": len(graph.get("predicates", [])),
            "mechanisms": len(graph.get("mechanisms", [])),
            "transformations": len(transformations),
            "edges": len(edges),
            "supports_edges": len(supports),
            "trainable_prior_edges": len(priors),
        },
        "formal_predicate_to_problem": {
            "out_degree_histogram": dict(sorted(symptom_branch_histogram.items())),
            "multiple_problem_predicates": multiple_problem_predicates,
            "is_trainable": False,
            "input_unit": "formal_predicate_not_raw_profiler_symptom",
            "raw_symptom_ambiguity_audited": False,
        },
        "problem_to_action": {
            "positive_action_degree_histogram": dict(sorted(positive_action_histogram.items())),
            "multiple_positive_action_problems": multiple_positive_action_problems,
            "noop_is_counted_as_positive_action": False,
        },
        "context_conditioning": {
            "direct_context_conditioned_edge_ids": sorted(context_edges),
            "unsupported_context_path_edge_ids": sorted(unsupported_context_edges),
            "predicate_only_conditioned_edge_ids": sorted(predicate_only_edges),
            "learned_context_residuals": False,
            "joint_action_coactivation_audited": False,
        },
        "handlers": {
            "parameterized_transformations": parameterized_handlers,
            "handler_nodes": len(handler_nodes),
            "multiple_handler_transformations": multiple_handler_transformations,
            "handler_propensity_recorded": False,
            "handler_parameters_learned": False,
        },
        "failure_recovery": {
            "recovery_edge_types": recovery_edge_types,
            "route_reads_previous_verdict": False,
            "parent_attempt_transition_validated": False,
        },
        "predicate_extractors": dict(sorted(extractor_states.items())),
        "topological_branch_dimensions_complete": topological_dimensions_complete,
        "empirical_trace_support_audited": False,
        "substantive_decision_graph": False,
        "recommended_experiment_scope": (
            "topological_candidate_requires_coactivation_and_trace_support"
            if topological_dimensions_complete
            else "fixed_graph_edge_ranking_with_handler_parameter_trace_collection"
        ),
        "limitations": [
            "raw profiler symptoms and their ambiguity sets are outside this graph-only audit",
            "NOOP alternatives do not constitute multiple positive handlers",
            "topological out-degree does not prove jointly legal or empirically supported actions",
            "global edge biases are not shape- or hardware-conditioned",
            "typed gate failures are outcomes, not learned recovery transitions",
            "free-form transformation parameters collapse distinct handlers into one edge reward",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = audit(_load_graph(args.graph))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
