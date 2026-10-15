"""CPU-only, read-only extraction of bounded lessons from frozen Level1 evidence.

This module returns content, not verdicts or graph-policy training episodes. It
never imports a collector, exporter, gate, or hardware library.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _ev(path: Path | str, selector: str, purpose: str) -> dict:
    return {"path": str(Path(path).resolve()), "selector": selector, "purpose": purpose}


def _base(identifier: str, kind: str, title: str, operator: str | None = None) -> dict:
    return dict(id=identifier, kind=kind, operator=operator, split="train", title=title,
                diagnosis={"symptoms": []}, intervention={}, effective_conditions=[],
                ineffective_conditions=[], counterexamples=[], claims=[], limitations=[],
                next_questions=[], graph_links=[], source_attempt_ids=[], evidence=[])


def _fact(statement: str, basis: str, evidence: list, **attributes: Any) -> dict:
    return dict(statement=statement, basis=basis, evidence=evidence, **attributes)


def _cases(source: list, observed: list, candidate: str, path: Path, addendum: Path,
           line: int) -> list:
    measurements = {c["case_id"]: (i, c) for i, c in enumerate(observed)}
    result = []
    for i, c in enumerate(source):
        mi, m = measurements[c["case_id"]]
        item = {k: deepcopy(c[k]) for k in (
            "case_id", "dtype", "scalar", "mode", "shapes", "lengths", "list_length",
            "complete_operator_launches", "runtime_cores_assumption")}
        item.update(deepcopy(m))
        item["p"] = item.pop("scalar")
        if candidate == "001":
            item["geometry"] = [{
                "length": g["length"], "tiling_unchanged": g["tiling_unchanged"],
                **{role: {k: v for k, v in g[role].items() if k in (
                    "block_num", "block_length", "critical_tile_iterations", "sum_tile_iterations", "tail_blocks")}
                   for role in ("baseline", "candidate_001")},
            } for g in c["candidate_001_tensor_geometry"]]
        else:
            item["intervention_applies"] = c[
                "candidate_002_specialized" if candidate == "002" else "candidate_003_accumulator_rewrite"]
        item["basis"] = "measured"
        item["statement"] = f"case {c['case_id']}: p={item['p']}, {item['dtype']}, speedup={m['speedup']}, regression={m['regression']}"
        item["evidence"] = [
            _ev(path, f"/cases/{i}", "Source-derived dtype, exponent, member sizes and decomposition"),
            _ev(addendum, f"line {line} /cases/{mi}", "Frozen paired per-case speedup, regression and CV"),
        ]
        result.append(item)
    return result


def _norm_lessons(parent: Path, serial: Path) -> list:
    analysis = serial / "tasks/foreach_norm/serial_analysis"
    condition_path = analysis / "case_conditions.json"
    conditions = _read(condition_path)["cases"]
    addendum = serial / "conditional_analysis/train/conditional_lessons.jsonl"
    records = {d["candidate_id"]: (line, d) for line, text in enumerate(
        addendum.read_text(encoding="utf-8").splitlines(), 1) if text.strip()
        for d in [json.loads(text)]}
    output = []
    for candidate in ("001", "002", "003"):
        directory = parent / "tasks/foreach_norm/candidates" / candidate
        plan_path = directory / "candidate_plan.json"
        plan = _read(plan_path)
        claim_path = analysis / f"final_claims_{candidate}.json"
        document = _read(claim_path)
        line, record = records[plan["candidate_id"]]
        lesson = _base(f"lesson.foreach_norm.{candidate}", "operator_optimization",
                       plan["intent"], "foreach_norm")
        lesson["source_attempt_ids"] = [plan["candidate_id"]]
        lesson["diagnosis"]["symptoms"] = [_fact(
            plan["rationale"], "historical_profile",
            [_ev(plan_path, "/rationale", "Original diagnosis with historical profile observations")],
            limitations=plan["contradicting_evidence"])]
        lesson["intervention"] = _fact(plan["intent"], "source", [
            _ev(plan_path, "/parameters", "Concrete predeclared intervention parameters"),
            _ev(directory / "patch.diff", "lines 1-end", "Actual independent patch against baseline")],
            parameters=plan["parameters"], handler_parameters=plan.get("handler_parameters", {}),
            code= (directory / "patch.diff").read_text(encoding="utf-8"),
            invariants=plan["semantic_invariants"], independent_from_baseline=True)
        if candidate == "003":
            original_invariant = next(
                value for value in plan["semantic_invariants"] if "零阶和无穷阶" in value)
            corrected_invariant = (
                "保留原mode选择和Power数学计算语义；GENERAL/ZERO的逐tile累加与同步路径已改写。"
                "INF保留scalar max/GetValue循环，但新增runningBuf分配、初始化和循环外屏障仍执行。")
            lesson["intervention"]["invariants"] = [
                corrected_invariant if value == original_invariant else value
                for value in plan["semantic_invariants"]]
            lesson["intervention"]["retrospective_corrections"] = [_fact(
                corrected_invariant, "source", [
                    _ev(plan_path, "/semantic_invariants", "Preserved original broad invariant wording"),
                    _ev(claim_path, "/claims/1", "Actual GENERAL/ZERO accumulator and synchronization intervention"),
                    _ev(claim_path, "/claims/3", "INF retains scalar loop but executes new allocation and initialization")],
                source_original_statement=original_invariant,
                correction_kind="retrospective_narrowing_of_execution_path_invariant")]
        lesson["limitations"] = document["limitations"] + [
            "This lesson is a retrospective extraction; original claims retain their measured/source/historical_profile/inferred basis.",
            plan["coverage_gap"]]
        lesson["next_questions"] = [
            "Do the condition-specific results hold for unequal TensorList member lengths and additional shapes?",
            "Can isolated interventions distinguish the proposed mechanism from compiler and scheduling effects?",
            "Would independently combining the candidates preserve correctness and their separate benefits?"]
        cases = _cases(conditions, record["cases"], candidate, condition_path, addendum, line)
        lesson["intervention"]["workload_cases"] = cases
        compact_cases = [{k: c[k] for k in (
            "case_id", "p", "dtype", "lengths", "list_length", "speedup", "regression")}
            for c in cases]
        claims = []
        for i, original in enumerate(document["claims"]):
            claim = deepcopy(original)
            claim["id"] = f"{lesson['id']}.claim.{i:02d}"
            # Status evaluates a proposition, not the true observation that
            # refutes it. Keep the original factual account separately.
            refuted_predictions = {
                0: "该候选在当前20case上的总体speedup 95%LCB达到至少1.03。",
                4: "该改写使旧case1和14的scalar time降低。",
            }
            if candidate == "003" and i in refuted_predictions:
                claim["observation"] = original["statement"]
                claim["source_original_statement"] = original["statement"]
                claim["statement"] = refuted_predictions[i]
            # The final_claims object is the exact locator for reviewed semantics.
            # Original source refs are retained with a root-document locator.
            claim["evidence"] = [_ev(claim_path, f"/claims/{i}", "Reviewed condition, status and evidence basis")] + [
                _ev(e["path"], "" if Path(e["path"]).suffix == ".json" else "lines 1-end", e["purpose"])
                for e in original["evidence"]]
            claims.append(claim)
        lesson["claims"] = claims
        selections = {"001": ([1, 3], [2]), "002": ([1], [2, 3]), "003": ([2], [0, 3])}
        effective, ineffective = selections[candidate]
        for target, indices in (("effective_conditions", effective), ("ineffective_conditions", ineffective)):
            for index in indices:
                claim = claims[index]
                lesson[target].append(_fact(
                    claim["condition"] + ": " + claim.get("observation", claim["statement"]), claim["basis"], claim["evidence"][:1],
                    claim_ids=[claim["id"]], case_ids=claim["case_ids"],
                    cases=[c for c in compact_cases if c["case_id"] in claim["case_ids"]],
                    limitations=claim["limitations"]))
        counter_indices = {"001": [2, 3], "002": [2, 3], "003": [0, 3, 4, 5]}[candidate]
        targets = {"001": "More partial blocks produce the same large benefit on every workload.",
                   "002": "Common-order specialization accelerates every exponent.",
                   "003": "Vector-resident accumulation achieves the predeclared benefit and all scalar/wait predictions."}
        # Explicit broad claim under challenge avoids interpreting positive
        # observations on INF as support for an intervention it never executes.
        for index in counter_indices:
            claim = claims[index]
            lesson["counterexamples"].append(_fact(
                claim.get("observation", claim["statement"]), claim["basis"], claim["evidence"][:1],
                target_claim=claim["statement"] if "observation" in claim else targets[candidate],
                claim_ids=[claim["id"]], case_ids=claim["case_ids"],
                cases=[c for c in compact_cases if c["case_id"] in claim["case_ids"]],
                limitations=claim["limitations"]))
        if candidate == "001":
            lesson["graph_links"] = ["mechanism.underused_task_parallelism"]
        lesson["evidence"] = [_ev(claim_path, "", "All final reviewed claims"),
                               _ev(plan_path, "", "Original diagnosis and intervention"),
                               _ev(addendum, f"line {line}", "Measured conditional addendum")]
        output.append(lesson)
    return output


def _method_lessons(serial: Path) -> list:
    path = serial / "setup/measurement_method_analysis.json"
    method = _read(path)
    lesson = _base("lesson.method.aa_lifecycle", "measurement_method",
                   "Qualify measurement lifecycle with same-binary role and session controls")
    evidence = [_ev(path, "/studies", "Historical same-binary method comparisons")]
    study_facts = []
    for si, study in enumerate(method["studies"]):
        for ci, cell in enumerate(study["cells"]):
            study_facts.append(_fact(
                f"{study['id']} / {cell['cell']}: same-binary A/A observations", "measured",
                [_ev(path, f"/studies/{si}/cells/{ci}", "Case-specific role/order bias and process context")],
                method=study["id"], context_lifecycle=cell["context_lifecycle"],
                precondition_samples=cell["precondition_samples"], repeat=cell["repeat"],
                reverse_startup=cell["reverse_startup"],
                cases=[{k: v for k, v in c.items() if k in (
                    "case_id", "pair_count", "role_bias_signed_fraction", "baseline_cv", "candidate_cv",
                    "order_strata", "order_gap_percentage_points")}
                       for c in cell["case_statistics"]]))
    lesson["diagnosis"]["symptoms"] = study_facts
    lesson["intervention"] = _fact(
        "Use the frozen before/startup-reversed/after control protocol, with one preconditioning sample and 30 pairs.",
        "source", [_ev(path, "/final_collection_protocol", "Frozen controls and thresholds")],
        protocol=method["final_collection_protocol"], definitions=method["definitions"])
    lesson["effective_conditions"] = [_fact(
        "Single-context probe has narrowly scoped cross-session observations for exp case 8.", "measured",
        [_ev(path, "/cross_session_comparisons", "Preserve all comparisons, including counterexamples")],
        comparisons=[c for c in method["cross_session_comparisons"] if c["method"] == "single"])]
    lesson["ineffective_conditions"] = [_fact(
        "Persistent/capture method controls expose role or session changes; do not pool their times.", "measured",
        evidence, comparisons=[c for c in method["cross_session_comparisons"] if c["method"] != "single"])]
    lesson["counterexamples"] = [_fact(
        "Same-binary ratios diagnose measurement error and cannot demonstrate candidate speedup.", "source",
        [_ev(path, "/missing_evidence", "Explicit limits of A/A studies")],
        target_claim="A favorable A/A ratio is an operator optimization gain.")]
    lesson["claims"] = [dict(id=lesson["id"] + ".claim.00", status="supported", **_fact(
        "The studies require separating role bias, cross-session drift, and candidate benefit.", "measured",
        evidence, limitations=method["missing_evidence"]))]
    lesson["limitations"] = method["missing_evidence"]
    lesson["next_questions"] = ["Would randomized repeated method studies isolate context lifetime from startup and temporal state?"]
    lesson["evidence"] = evidence

    scope = _base("lesson.method.timing_output_scope", "measurement_method",
                  "Separate full-operator event timing, process cost and retained-output verification")
    observation_path = serial / "tasks/foreach_norm/serial_analysis/measurement_observations_001.json"
    observations = _read(observation_path)
    costs = [{k: v for k, v in c.items() if k != "process_detail"} for c in method["single_context_costs"]]
    refs = [_ev(path, "/single_context_costs", "Recorded lifecycle cost versus native event time"),
            _ev(observation_path, "/definitions", "Full TensorList event and uncertainty definitions"),
            _ev(observation_path, "/summary", "Recorded process/sample/output counts")]
    scope["diagnosis"]["symptoms"] = [_fact(
        "Process lifecycle cost and device event intervals describe different scopes.", "measured", refs,
        lifecycle_costs=costs, observation_summary=observations["summary"])]
    scope["intervention"] = _fact(
        "Retain separate time scopes and explicitly count outputs actually preserved and verified.", "source", refs,
        definitions=observations["definitions"])
    scope["effective_conditions"] = [_fact(
        "Complete TensorList callback timing includes all members and both partial/finalize launches.",
        "source", refs, event_scope=observations["definitions"]["event_scope"])]
    scope["counterexamples"] = [_fact(
        "1200 context sessions do not imply 1200 preserved outputs: this candidate records 40 final outputs.",
        "measured", refs, target_claim="Every intermediate process output was retained and verified.",
        context_sessions=observations["summary"]["context_sessions"],
        verified_final_outputs=observations["summary"]["verified_final_outputs"])]
    scope["claims"] = [dict(id=scope["id"] + ".claim.00", status="supported", **_fact(
        "Full-operator paired time cannot be replaced by historical partial-kernel profile duration or lifecycle wall time.",
        "source", refs, limitations=[observations["definitions"]["uncertainty_scope"]]))]
    scope["source_attempt_ids"] = [observations["candidate_id"]]
    scope["limitations"] = ["The observation artifact was pending_post_batch when written; no admission is inferred from it.",
                            "Log mtime is a parent-reader flush proxy, not a timestamp of a native subphase."]
    scope["next_questions"] = ["Which initialization and cleanup phases account for lifecycle cost? No subphase timestamps exist here."]
    scope["evidence"] = refs
    return [lesson, scope]


def _infrastructure_lesson(serial: Path) -> dict:
    path = serial / "tasks/foreach_norm/serial_analysis/artifact_preflight/integration_report.json"
    report = _read(path)
    lesson = _base("lesson.infrastructure.artifact_preflight", "infrastructure",
                   "Check evidence integration and output coverage before interpreting measurements")
    evidence = [_ev(path, "", "Read-only historical integration preflight, not candidate performance evidence")]
    counts = {k: report[k] for k in (
        "case_count", "pair_count", "context_session_count", "bound_context_log_count", "bound_output_count",
        "bound_verification_log_count", "correctness_passed_count", "unique_cas_objects_verified")}
    lesson["diagnosis"]["symptoms"] = [_fact(
        "Raw timing, source identity and retained-output coverage require distinct bindings.", "source", evidence,
        coverage=counts)]
    lesson["intervention"] = _fact(
        "Use read-only source snapshot and artifact binding checks with explicit unadmitted observation state.",
        "source", evidence, source_bindings=report["source_bindings"],
        no_gate_or_finalization_invoked=report["no_gate_or_finalization_invoked"],
        formal_run_written=report["formal_run_written"])
    lesson["effective_conditions"] = [_fact(
        "Source binding validity and archive/report agreement are directly checkable without hardware.", "source", evidence,
        observed_matches_archived_report=report["observed_matches_archived_report"], coverage=counts)]
    lesson["ineffective_conditions"] = [_fact(
        "Pending calibration and operator health leave observations unadmitted at this preflight checkpoint.",
        "source", evidence, admission_reasons=report["admission_reasons"])]
    lesson["counterexamples"] = [_fact(
        "Successful integration preflight is not measurement admission or operator gain.", "source", evidence,
        target_claim="An artifact preflight pass establishes optimization success.",
        observed_stable=report["observed_stable"], admitted_stable=report["admitted_stable"],
        admitted_speedup=report["admitted_speedup"])]
    lesson["claims"] = [dict(id=lesson["id"] + ".claim.00", status="supported", **_fact(
        "Historical preflight verified evidence bindings while preserving pending admission.", "source", evidence,
        limitations=["This is the preflight checkpoint, not the later finalization state."]))]
    lesson["limitations"] = ["Infrastructure evidence cannot be relabeled as an operator optimization mechanism."]
    lesson["next_questions"] = ["Can later evidence delivery retain every intermediate output without changing timing scope?"]
    lesson["source_attempt_ids"] = [report["candidate_id"]]
    lesson["evidence"] = evidence
    return lesson


def build_lessons(parent_run: Path, serial_run: Path) -> list[dict]:
    """Read frozen artifacts and return six content-only, evidence-located lessons."""
    parent, serial = Path(parent_run).resolve(), Path(serial_run).resolve()
    return _norm_lessons(parent, serial) + _method_lessons(serial) + [_infrastructure_lesson(serial)]
