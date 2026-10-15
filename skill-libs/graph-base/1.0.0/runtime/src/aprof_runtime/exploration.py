"""Machine gates for graph coverage gaps, without manufacturing graph routes."""
from __future__ import annotations

import json
import math
import statistics
import csv
from dataclasses import replace
from pathlib import PurePosixPath
from typing import Any

from .contracts import GateConfig, GateEvidence
from .errors import ContractError, StoreError
from .gates import evaluate_candidate_evidence
from .jsonio import canonical_json, content_hash, to_primitive
from .store import EpisodeStore
from .traces import _check_event, _verify_refs, register_json_artifact, utcnow, validate_trace_contract


def freeze_exploration_manifest(store: EpisodeStore, *, run_id: str, task_id: str,
                                split: str, candidates: list[dict], frozen_at=None) -> str:
    manifest = {"schema_version": "1.0.0", "run_id": run_id, "task_id": task_id,
                "split": split, "frozen_at": frozen_at or utcnow(), "candidates": candidates}
    validate_trace_contract("exploration-manifest", manifest)
    _verify_refs(manifest, store)
    return register_json_artifact(store, manifest)


def _load(store: EpisodeStore, digest: str) -> dict:
    try:
        from .profile_evidence import _json
        return _json(store.verify_artifact(digest).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise StoreError(f"artifact {digest} is not JSON: {exc}") from exc


def _check_attempt(store: EpisodeStore, candidate: dict, manifest: dict) -> None:
    fragment = _load(store, candidate["attempt_evidence_hash"])
    if not isinstance(fragment, dict) or set(fragment) != {"schema_version", "identity", "attempt_id", "events"}:
        raise ContractError("attempt evidence is not a sealed TraceWriter fragment")
    identity = fragment["identity"]
    if identity != {"run_id": manifest["run_id"], "task_id": manifest["task_id"], "session_id": candidate["session_id"]}:
        raise ContractError("attempt evidence identity differs from frozen manifest")
    proposals = []
    previous = None
    for event in fragment["events"]:
        _check_event(event, store)
        if any(event.get(key) != value for key, value in identity.items()):
            raise ContractError("sealed evidence contains a different task/session")
        if event["attempt_id"] != fragment["attempt_id"] or event["candidate_id"] != candidate["candidate_id"]:
            raise ContractError("sealed evidence contains a different attempt/candidate")
        if previous and event["sequence"] <= previous["sequence"]:
            raise ContractError("sealed evidence is not in sequence order")
        previous = event
        if event["event_type"] == "candidate_proposed":
            proposals.append(event["payload"])
    if len(proposals) != 1:
        raise ContractError("sealed attempt must contain exactly one candidate_proposed event")
    proposal = proposals[0]
    expected = {"mode": "exploration", "source_parent_hash": candidate["source_hashes"]["baseline"],
                "patch_hash": candidate["patch_artifact_hash"], "handler_id": candidate["handler_id"],
                "handler_version": candidate["handler_version"], "parameters": candidate["parameters"],
                "coverage_gap": candidate["coverage_gap"]}
    if any(proposal[key] != value for key, value in expected.items()):
        raise ContractError("frozen candidate handler/parameters/patch differ from attempt proposal")


def _check_measurement(store: EpisodeStore, evidence: GateEvidence, config: GateConfig) -> None:
    digest = evidence.artifacts.get("measurement_report")
    if digest is None:
        return  # The shared gate reports artifacts_incomplete after hard stages.
    report = _load(store, digest)
    if report.get("unit") != "ns" or report.get("aggregation") != "equal_case_geometric_mean_per_round":
        raise ContractError("exploration measurement_report must use the multicase ns adapter")
    projected = report.get("gate_projection")
    supplied = {key: list(getattr(evidence, key)) for key in
                ("baseline_samples_ns", "candidate_samples_ns", "heldout_regressions")}
    if projected != supplied:
        raise ContractError("GateEvidence measurements differ from the bound report projection")
    if not evidence.baseline_samples_ns and not evidence.candidate_samples_ns:
        return  # Raw failures remain available, but have no admitted measurements.
    cases = report.get("per_case", [])
    if report.get("case_ids") != list(range(1, 21)) or [case.get("case_id") for case in cases] != list(range(1, 21)):
        raise ContractError("final exploration measurements require all 20 cases in order")
    if report.get("stable") is not True:
        raise ContractError("unstable measurements cannot expose gate timing arrays")
    count = len(evidence.baseline_samples_ns)
    regressions = []
    for case in cases:
        for key in ("baseline_samples_ns", "candidate_samples_ns"):
            samples = case.get(key)
            if not isinstance(samples, list) or len(samples) != count or count < config.min_pairs:
                raise ContractError("per-case sample count differs from the suite projection")
            if any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0 for value in samples):
                raise ContractError("invalid per-case ns sample")
            cv = statistics.stdev(samples) / statistics.fmean(samples)
            if cv > config.max_cv:
                raise ContractError("per-case instability was hidden by suite aggregation")
        regressions.append(math.exp(statistics.fmean(math.log(after / before) for before, after in
            zip(case["baseline_samples_ns"], case["candidate_samples_ns"], strict=True))) - 1)
    recomputed = {key: [math.exp(statistics.fmean(math.log(case[key][i]) for case in cases))
                       for i in range(count)] for key in ("baseline_samples_ns", "candidate_samples_ns")}
    recomputed["heldout_regressions"] = regressions
    if any(len(projected[key]) != len(values) or any(not math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
           for a, b in zip(projected[key], values)) for key, values in recomputed.items()):
        raise ContractError("measurement projection does not reproduce equal-case geometric aggregation")


def _profile_metric(store: EpisodeStore, profile_hash: str, name: str) -> tuple[dict, dict]:
    profile = _load(store, profile_hash)
    validate_trace_contract("normalized-profile", profile)
    if name not in profile["metrics"]:
        raise ContractError(f"normalized profile is missing metric {name!r}")
    metric = profile["metrics"][name]
    if profile["schema_version"] == "1.1.0":
        from .profile_evidence import replay_profile_metric
        replay_profile_metric(store, profile, name)
        return profile, metric
    source = store.verify_artifact(metric["source_artifact_hash"])
    original_rows = {}
    try:
        with source.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if metric["field"] not in (reader.fieldnames or []):
                raise ContractError("profile metric field is absent from bound CSV")
            samples = []
            for row in reader:
                if profile["kernel"] != "*" and profile["kernel"] not in row.values():
                    continue
                raw = row.get(metric["field"], "")
                if raw in (None, "", "N/A", "NA", "--"):
                    continue
                # Combined tables retain a deterministic pointer to every
                # original raw cell; a derived CSV is not a new trust root.
                provenance = {"aprof_source_hash", "aprof_source_row", "aprof_source_path", "aprof_kernel"}
                if provenance.intersection(row):
                    if not provenance.issubset(row):
                        raise ContractError("combined profile CSV has incomplete raw-row provenance")
                    digest = row["aprof_source_hash"]
                    if digest not in original_rows:
                        with store.verify_artifact(digest).open(encoding="utf-8-sig", newline="") as original:
                            original_rows[digest] = list(csv.DictReader(original))
                    index = int(row["aprof_source_row"]) - 1
                    if not 0 <= index < len(original_rows[digest]):
                        raise ContractError("combined profile row points outside its raw CSV")
                    original = original_rows[digest][index]
                    if original.get(metric["field"], "") != raw:
                        raise ContractError("combined profile value differs from its bound original CSV cell")
                    original_kernel = original.get("Op Name") or original.get("OP Name")
                    if original_kernel and original_kernel != row["aprof_kernel"]:
                        raise ContractError("combined profile kernel disagrees with original CSV")
                    if not original_kernel and row["aprof_kernel"] not in PurePosixPath(row["aprof_source_path"]).parts:
                        raise ContractError("combined profile kernel lacks source-directory provenance")
                samples.append(float(raw))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ContractError(f"profile metric source is not a numeric CSV column: {exc}") from exc
    if samples != metric["samples"] or not samples or any(not math.isfinite(value) for value in samples):
        raise ContractError("normalized profile samples differ from bound raw CSV/kernel selection")
    reducer = {"mean": statistics.fmean, "median": statistics.median,
               "sum": sum, "min": min, "max": max}[metric["aggregation"]]
    if not math.isclose(float(reducer(samples)), metric["value"], rel_tol=1e-12, abs_tol=1e-12):
        raise ContractError("normalized profile metric does not reproduce its samples/aggregation")
    return profile, metric


def mechanism_alignment_from_artifacts(evidence: GateEvidence | dict, store: EpisodeStore, *,
                                      source_hashes=None, require_v11=False) -> bool | None:
    """Recompute measured directional support; absence of profiling stays unknown.

    Collectors may use this for graph evidence without changing v1 serialization.
    A supported direction is evidence for the stated hypothesis, not proof that
    no other mechanism caused a speedup. hypothesis_basis preserves that limit.
    """
    if isinstance(evidence, dict):
        evidence = GateEvidence.from_dict(evidence)
    digest = evidence.artifacts.get("mechanism_report")
    if not digest:
        return None
    report = _load(store, digest)
    if isinstance(report, dict) and report.get("kind") == "full_call_pmu_mechanism":
        from .full_call_pmu import replay_full_call_mechanism
        return replay_full_call_mechanism(store, report, evidence=evidence,
                                         source_hashes=source_hashes)["alignment"]
    validate_trace_contract("mechanism-report", report)
    if report["candidate_id"] != evidence.candidate_id:
        raise ContractError("mechanism report candidate identity mismatch")
    supported = []
    unavailable = False
    for metric in report["metrics"]:
        baseline_profile, baseline = _profile_metric(store, metric["baseline_profile_hash"], metric["name"])
        candidate_profile, candidate = _profile_metric(store, metric["candidate_profile_hash"], metric["name"])
        versions = (baseline_profile["schema_version"], candidate_profile["schema_version"])
        if versions != ("1.1.0", "1.1.0"):
            if require_v11:
                unavailable = True
                continue
            if versions != ("1.0.0", "1.0.0"):
                raise ContractError("mixed normalized profile versions cannot be compared")
        else:
            from .profile_evidence import compare_profiles
            if not compare_profiles(store, baseline_profile, candidate_profile, metric["name"], source_hashes=source_hashes):
                unavailable = True
                continue
        if baseline_profile["case_id"] != candidate_profile["case_id"]:
            raise ContractError("mechanism profiles must describe the same workload case")
        if (baseline["unit"] != metric["unit"] or candidate["unit"] != metric["unit"] or
                baseline["value"] != metric["baseline"] or candidate["value"] != metric["candidate"]):
            raise ContractError("mechanism metric values/units disagree with normalized profiles")
        supported.append(candidate["value"] > baseline["value"] if metric["expected_direction"] == "increase"
                         else candidate["value"] < baseline["value"])
    return True if any(supported) else (None if unavailable else False)


def validate_exploration_request(request: dict, store: EpisodeStore) -> tuple[dict, dict, GateConfig, dict[str, GateEvidence]]:
    validate_trace_contract("exploration-request", request)
    config = GateConfig.from_dict(request["config"])
    candidates = request["candidates"]
    evidence = [GateEvidence.from_dict(item) for item in request["evidence"]]
    candidate_ids = [item["candidate_id"] for item in candidates]
    evidence_ids = [item.candidate_id for item in evidence]
    if len(set(candidate_ids)) != len(candidate_ids) or len(set(evidence_ids)) != len(evidence_ids):
        raise ContractError("exploration candidate/evidence ids must be unique")
    if set(candidate_ids) != set(evidence_ids):
        raise ContractError("exploration requires evidence for the complete frozen candidate batch")
    if len({item["session_id"] for item in candidates}) != 1:
        raise ContractError("exploration candidates must belong to one session")
    manifest = _load(store, request["frozen_manifest_hash"])
    validate_trace_contract("exploration-manifest", manifest)
    if manifest["candidates"] != candidates:
        raise ContractError("exploration candidate batch differs from frozen manifest")
    _verify_refs(manifest, store)
    for candidate in candidates:
        _check_attempt(store, candidate, manifest)
    from .measurement_entry import verify_measurement_admission
    candidate_by_id = {item["candidate_id"]: item for item in candidates}
    for item in evidence:
        for digest in item.artifacts.values():
            store.verify_artifact(digest)
        _check_measurement(store, item, config)
        candidate = candidate_by_id[item.candidate_id]
        verify_measurement_admission(item, store, source_hashes=candidate["source_hashes"],
                                     session_id=candidate["session_id"], run_id=manifest["run_id"])
    source_roles = {item["candidate_id"]: item["source_hashes"] for item in candidates}
    measured_evidence = {item.candidate_id: replace(item, mechanism_alignment=mechanism_alignment_from_artifacts(
        item, store, source_hashes=source_roles[item.candidate_id], require_v11=True)) for item in evidence}
    return request, manifest, config, measured_evidence


class ExplorationGate:
    def evaluate(self, request: dict, *, store: EpisodeStore) -> tuple[dict, ...]:
        """Evaluate a complete frozen batch; only evidence artifacts enter SQLite."""
        request, _, config, evidence = validate_exploration_request(request, store)
        request_hash = register_json_artifact(store, request)
        outcomes = []
        for candidate in request["candidates"]:
            result = to_primitive(evaluate_candidate_evidence(
                candidate["candidate_id"], evidence[candidate["candidate_id"]], config))
            # Do not expose v1 policy eligibility, episode winner, or decision hash.
            for key in ("policy_update_eligible", "selected_as_best", "decision_hash"):
                del result[key]
            result.update({"frozen_manifest_hash": request["frozen_manifest_hash"],
                "request_hash": request_hash, "graph_policy_eligible": False, "episode_ref": None})
            result["outcome_hash"] = content_hash(result)
            validate_trace_contract("exploration-outcome", result)
            outcomes.append(result)
        return tuple(outcomes)


def verify_exploration(request: dict, outcomes: Any, *, store: EpisodeStore) -> dict:
    actual = list(outcomes)
    for outcome in actual:
        validate_trace_contract("exploration-outcome", outcome)
        if outcome["outcome_hash"] != content_hash({key: value for key, value in outcome.items() if key != "outcome_hash"}):
            raise StoreError("exploration outcome hash mismatch")
    expected = list(ExplorationGate().evaluate(request, store=store))
    if canonical_json(actual) != canonical_json(expected):
        raise StoreError("exploration outcomes do not reproduce the machine gate")
    return {"valid": True, "candidate_count": len(expected), "request_hash": content_hash(request),
            "graph_policy_eligible": False, "episode_count_added": 0}
