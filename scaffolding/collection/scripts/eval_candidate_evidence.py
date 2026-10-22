"""Read-only replay of qualified routing and independent source review."""
from __future__ import annotations

import json
from pathlib import Path
import sys

from eval_tool_broker import (BUDGET_POLICY, Broker, CONFIG, REVIEW_OBLIGATIONS, REVIEW_SOURCE_POLICY,
                              checked, digest, final_review, inventory, pointer, review_inventory)


def read(path):
    return json.loads(Path(path).read_text())


def runtime(release):
    release = Path(release).resolve()
    repo = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo / "scaffolding/tools"))
    from verify_teacher_wiki import verify_frozen_machine_rules
    verify_frozen_machine_rules(repo, release)
    sys.path.insert(0, str(release / "runtime/src"))
    import aprof_runtime
    if Path(aprof_runtime.__file__).resolve().parent != release / "runtime/src/aprof_runtime":
        raise ValueError("routing must replay in the frozen candidate runtime")


def replay_route(registry_ref, context_id, release):
    """Registry, contexts and evidence are prepared by the trusted baseline qualifier.

    This interface cannot accept caller-provided predicates or alter selection.
    Full qualification is independently replayed by the host/publication gate.
    """
    runtime(release)
    from aprof_runtime.contracts import Context
    from aprof_runtime.graph import load_snapshot, route_graph
    from aprof_runtime.jsonio import content_hash, to_primitive
    from aprof_runtime.planning import validate_planning_context
    registry = read(checked(registry_ref))
    if registry.get("schema_version") != 1 or context_id not in registry["contexts"]:
        raise ValueError("unknown frozen graph context")
    entry = registry["contexts"][context_id]
    qualification = read(checked(entry["baseline_qualification"]))
    if qualification.get("status") != "passed":
        raise ValueError("route context requires a qualified baseline")
    context = Context.from_dict(read(checked(entry["context"])))
    for reference in entry["evidence"]:
        checked(reference)
    if not entry["evidence"]:
        raise ValueError("route context lacks its frozen baseline evidence")
    validate_planning_context(context, execution=context.evidence.get("optimization_stage") == "execution")
    graph_path = Path(release) / "skillgraph/versions/v0002/graph.json"
    if checked(registry["graph"]) != graph_path.resolve():
        raise ValueError("route registry names a different frozen graph")
    graph, _ = load_snapshot(graph_path)
    route = route_graph(graph, context, policy_version="expert-prior", selection_mode="argmax")
    recorded = to_primitive(route)
    selected = next(item for item in recorded["candidates"] if item["edge_id"] == recorded["selected_edge_id"])
    transformation = next(item for item in graph["transformations"] if item["id"] == selected["target_id"])
    return {"schema_version": 1, "registry_ref": registry_ref, "context_id": context_id,
            "context_ref": entry["context"], "baseline_qualification_ref": entry["baseline_qualification"],
            "evidence_refs": entry["evidence"], "graph_hash": content_hash(graph), "route": recorded,
            "parameter_schema": transformation["parameter_schema"]}


def verify_blind_source_review(workspace, release, *, model=None, retained=None):
    """Verify only the independent reviewer evidence for the selected task.

    ``accepted`` describes the blind source review, never a legal graph route,
    exploration authorization, or machine admission. The caller retains its
    selected release and supplies the frozen model when checking that identity.
    """
    if retained is not None:
        from retained_source_review import _RetainedReview
        if type(retained) is not _RetainedReview:
            raise ValueError("retained review requires a verified archive context")
    workspace = Path(workspace)
    checked_ref = checked if retained is None else retained.checked
    file_pointer = pointer if retained is None else retained.pointer
    review = read(workspace / "candidate_review.json")
    if (review.get("schema_version") != 1 or review.get("review_source_policy") != REVIEW_SOURCE_POLICY
            or review["baseline_inventory"] != inventory(workspace / "baseline")
            or review["candidate_inventory"] != inventory(workspace / "candidate")
            or review["plan_sha256"] != file_pointer(workspace / "candidate_plan.json")["sha256"]):
        raise ValueError("source review is not bound to the actual candidate")
    worker = read(checked_ref(review["worker_receipt_ref"]))
    review_work = checked_ref(review["worker_receipt_ref"]).parent / "root/work"
    if inventory(review_work) != review["input_inventory"]:
        raise ValueError("blind reviewer input changed or contains unrecorded material")
    if {item.name for item in review_work.iterdir()} != {"baseline", "candidate", "contract.json", "checklist.json", "boundaries.json", "diff.txt", "prompt.txt"}:
        raise ValueError("blind reviewer did not receive exactly the anonymous sources and frozen contract")
    for role in ("baseline", "candidate"):
        expected_view = review_inventory(review[role + "_inventory"])
        actual_names = {path.relative_to(review_work / role).as_posix()
                        for path in (review_work / role).rglob("*") if path.is_file()}
        if not expected_view or actual_names != set(expected_view) or inventory(review_work / role) != expected_view:
            raise ValueError("blind reviewer source view differs from the full frozen source inventory")
    from review_packet import build_review_packet
    packet = build_review_packet(review_work, expected_inventory={
        name: reference for name, reference in review["input_inventory"].items() if name != "prompt.txt"})
    if retained is not None:
        packet = retained.restore_packet(packet)
    if (review.get("review_packet_binding") != packet["binding"]
            or (review_work / "prompt.txt").read_text() != packet["prompt"]):
        raise ValueError("blind reviewer first prompt differs from its complete frozen packet")
    events = [json.loads(line) for line in checked_ref(worker["events_ref"]).read_text().splitlines() if line]
    broker = [json.loads(line) for line in checked_ref(worker["broker_ref"]).read_text().splitlines() if line]
    usage = [row["params"]["tokenUsage"]["total"] for row in events if row.get("method") == "thread/tokenUsage/updated"]
    totals = [item.get("totalTokens") for item in usage]
    if (worker["role"] != "reviewer" or worker["status"] != "completed" or not usage
            or any(type(value) is not int or value < 0 for value in totals)
            or totals != sorted(totals) or worker["usage"] != usage[-1]
            or worker.get("budget_policy") != BUDGET_POLICY):
        raise ValueError("review lacks a complete independent model usage receipt")
    if model and (worker["model"] != model["name"] or worker["reasoning_effort"] != model["reasoning_effort"]):
        raise ValueError("source reviewer differs from the frozen evaluation model")
    from qualify_eval_tools import verify_qualification
    verify_qualification(worker["qualification_ref"], model=worker["model"], effort=worker["reasoning_effort"], retained=retained)
    if worker.get("config") != CONFIG or worker.get("worker_builds") != 0:
        raise ValueError("review did not use the qualified read-only broker")
    decision, binding = final_review(events)
    if (worker.get("review_submission") != binding or worker["submission"] != decision
            or review["decision"] != decision):
        raise ValueError("review decision differs from its final model answer and usage binding")
    if any(row["tool"] not in {"list_files", "read_file", "search_text"} for row in broker):
        raise ValueError("review used a non-blind or obsolete submission tool")
    decision = review["decision"]
    if set(decision["obligations"]) != set(REVIEW_OBLIGATIONS):
        raise ValueError("review omitted a critical obligation")
    # Reuse the exact broker validation without writing another broker receipt.
    validator = Broker(review_work, Path("unused-read-only-validation"), review=True)
    validator.validate_review(decision["obligations"])
    accepted = all(item["status"] == "pass" and item["reason"].strip() and item["anchors"] for item in decision["obligations"].values())
    if decision["accepted"] is not accepted:
        raise ValueError("review acceptance differs from critical obligations")
    for key in ("contract_ref", "checklist_ref", "boundaries_ref", "prompt_ref"):
        checked_ref(review[key])
        name = {"contract_ref": "contract.json", "checklist_ref": "checklist.json", "boundaries_ref": "boundaries.json", "prompt_ref": "prompt.txt"}[key]
        if file_pointer(review_work / name)["sha256"] != review[key]["sha256"]:
            raise ValueError("reviewed input differs from its frozen attachment")
    return {"accepted": accepted, "source_review": review,
            "source_review_ref": file_pointer(workspace / "candidate_review.json")}


def verify_candidate_evidence(workspace, release, *, model=None, baseline_qualification=None):
    workspace = Path(workspace)
    plan = read(workspace / "candidate_plan.json")
    route_path = checked(plan["route_receipt_ref"])
    route = read(route_path)
    if read(workspace / "route_receipt.json") != route:
        raise ValueError("controller route copy differs from broker receipt")
    expected_route = replay_route(route["registry_ref"], route["context_id"], release)
    if route != expected_route:
        raise ValueError("frozen graph route does not replay")
    if baseline_qualification is not None and route["baseline_qualification_ref"] != baseline_qualification:
        raise ValueError("route context belongs to a different qualified baseline")
    from aprof_runtime.attestation import attest_route
    from aprof_runtime.contracts import Context, RouteDecision
    from aprof_runtime.graph import load_snapshot
    from aprof_runtime.planning import _validate
    graph, _ = load_snapshot(Path(release) / "skillgraph/versions/v0002/graph.json")
    attest_route(context=Context.from_dict(read(checked(route["context_ref"]))), recorded=RouteDecision.from_dict(route["route"]),
        graph_snapshot=graph, graph_hash=route["graph_hash"], behavior_policy_checkpoint=None, policy_checkpoint_hash=None)
    selected = next(item for item in route["route"]["candidates"] if item["edge_id"] == route["route"]["selected_edge_id"])
    if not selected["allowed"] or plan.get("transformation_id") != selected["target_id"]:
        raise ValueError("candidate did not follow the selected legal graph edge")
    transformation = next(item for item in graph["transformations"] if item["id"] == selected["target_id"])
    _validate(transformation["parameter_schema"], plan.get("parameters"), "candidate_plan.parameters")
    blind_review = verify_blind_source_review(workspace, release, model=model)
    review = blind_review["source_review"]
    if selected["target_id"] == "transformation.noop" and review["baseline_inventory"] != review["candidate_inventory"]:
        raise ValueError("NOOP route cannot authorize a source change")
    return {"accepted": blind_review["accepted"], "source_review": review, "route_receipt": route,
            "source_review_ref": blind_review["source_review_ref"], "route_receipt_ref": pointer(route_path)}


def register_candidate_evidence(store, workspace, release, *, model=None, baseline_qualification=None):
    result = verify_candidate_evidence(workspace, release, model=model, baseline_qualification=baseline_qualification)
    if not result["accepted"]:
        raise ValueError("independent source review failed or remained unknown")
    review, route = result["source_review"], result["route_receipt"]
    worker = read(checked(review["worker_receipt_ref"]))
    attachments = [review[key] for key in ("worker_receipt_ref", "contract_ref", "checklist_ref", "boundaries_ref", "prompt_ref")]
    attachments += [worker[key] for key in ("events_ref", "broker_ref", "qualification_ref")]
    qualification = read(checked(worker["qualification_ref"]))
    attachments += [qualification["model_catalog"], qualification["installed_model_metadata"], *qualification["producers"]]
    attachments += [probe[key] for probe in qualification["probes"] for key in ("request_ref", "events_ref")]
    attachments += [route[key] for key in ("registry_ref", "context_ref", "baseline_qualification_ref")] + route["evidence_refs"]
    for reference in attachments:
        store.register_artifact(checked(reference))
    return {"source_review": store.register_artifact(checked(result["source_review_ref"])),
            "route_receipt": store.register_artifact(checked(result["route_receipt_ref"]))}
