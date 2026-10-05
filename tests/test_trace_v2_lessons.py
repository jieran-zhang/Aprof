"""Read-only regression tests against the preserved Level1 evidence corpus."""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from trace_v2_lessons import build_lessons

PARENT = ROOT / ".aprof/runs/level1-20260907T152600Z"
SERIAL = ROOT / ".aprof/runs/level1-serial-final-20260908T011500Z"


@pytest.fixture(scope="module")
def lessons():
    if not (SERIAL / "tasks/foreach_norm/serial_analysis/final_claims_001.json").exists():
        pytest.skip("Frozen Level1 corpus is not available in this checkout")
    return {lesson["id"]: lesson for lesson in build_lessons(PARENT, SERIAL)}


def test_all_seven_subthreshold_regressions_remain_counterexamples(lessons):
    lesson = lessons["lesson.foreach_norm.002"]
    regression = lesson["counterexamples"][0]
    assert regression["case_ids"] == [5, 6, 7, 13, 17, 19, 20]
    assert len(regression["cases"]) == 7
    assert {c["p"] for c in regression["cases"]} == {3, 1.5, 5, -1, 2.5}
    for case in regression["cases"]:
        assert 0 < case["regression"] < 0.03
        assert case["speedup"] < 1
        full = next(c for c in lesson["intervention"]["workload_cases"] if c["case_id"] == case["case_id"])
        assert full["intervention_applies"] is False
    assert max(c["regression"] for c in regression["cases"]) == pytest.approx(0.01337774172587336)
    assert regression["target_claim"]


def test_flat48_controls_have_unchanged_geometry_and_measured_values(lessons):
    lesson = lessons["lesson.foreach_norm.001"]
    controls = lesson["ineffective_conditions"][0]
    assert controls["case_ids"] == [3, 9]
    assert [c["speedup"] for c in controls["cases"]] == pytest.approx([0.999994377, 1.000372786])
    for c in controls["cases"]:
        full = next(case for case in lesson["intervention"]["workload_cases"] if case["case_id"] == c["case_id"])
        for geometry in full["geometry"]:
            assert geometry["tiling_unchanged"]
            assert geometry["baseline"]["block_num"] == 48
            assert geometry["candidate_001"]["block_num"] == 48
    assert lesson["intervention"]["parameters"]["minimum_tiles_per_task"] == 16
    assert "runtime_vector_cores" in lesson["intervention"]["handler_parameters"]["dynamic_formula"]


def test_mixed_scalar_and_stall_evidence_keeps_historical_basis(lessons):
    lesson = lessons["lesson.foreach_norm.003"]
    scalar, mixed = lesson["claims"][4:6]
    assert scalar["status"] == "refuted"
    assert mixed["status"] == "inconclusive"
    assert scalar["basis"] == mixed["basis"] == "historical_profile"
    assert "50.52054→54.756758" in scalar["observation"]
    assert "48.9086475→52.958378" in scalar["observation"]
    assert "stall下降" in scalar["observation"]
    assert "case20" in mixed["statement"] and "重叠" in mixed["statement"]
    assert lesson["claims"][0]["status"] == "refuted"
    assert lesson["claims"][6]["basis"] == "inferred"
    assert lesson["claims"][6]["status"] == "inconclusive"
    assert lesson["intervention"]["parameters"]["running_accumulator_bytes"] == 32


def test_original_claim_semantics_are_preserved_without_gate_reclassification(lessons):
    for candidate in ("001", "002", "003"):
        original = json.loads((SERIAL / f"tasks/foreach_norm/serial_analysis/final_claims_{candidate}.json").read_text())
        claims = lessons[f"lesson.foreach_norm.{candidate}"]["claims"]
        assert len(claims) == len(original["claims"])
        for actual, expected in zip(claims, original["claims"]):
            for key in ("status", "basis", "condition", "case_ids", "limitations"):
                assert actual[key] == expected[key]
            assert actual.get("source_original_statement", actual["statement"]) == expected["statement"]


def test_refuted_claims_evaluate_predictions_not_true_observations(lessons):
    lesson = lessons["lesson.foreach_norm.003"]
    gain, scalar = lesson["claims"][0], lesson["claims"][4]
    assert gain["statement"] == "该候选在当前20case上的总体speedup 95%LCB达到至少1.03。"
    assert scalar["statement"] == "该改写使旧case1和14的scalar time降低。"
    for claim in (gain, scalar):
        assert claim["status"] == "refuted"
        counter = next(c for c in lesson["counterexamples"] if claim["id"] in c["claim_ids"])
        assert counter["target_claim"] == claim["statement"]
        assert counter["statement"] == claim["observation"]
        assert counter["statement"] != claim["statement"]
    assert gain["observation"] in lesson["ineffective_conditions"][0]["statement"]
    for counter in lessons["lesson.foreach_norm.001"]["counterexamples"]:
        for case in counter["cases"]:
            assert "geometry" not in case
            assert {"case_id", "speedup", "p", "dtype"} <= case.keys()


def test_accumulator_invariant_distinguishes_math_from_changed_execution(lessons):
    intervention = lessons["lesson.foreach_norm.003"]["intervention"]
    correction = intervention["retrospective_corrections"][0]
    assert correction["source_original_statement"] not in intervention["invariants"]
    assert correction["statement"] in intervention["invariants"]
    assert "GENERAL/ZERO的逐tile累加与同步路径已改写" in correction["statement"]
    assert "runningBuf" in correction["statement"]
    assert correction["correction_kind"] == "retrospective_narrowing_of_execution_path_invariant"


def test_full_case_table_is_unique_and_groups_preserve_inline_values(lessons):
    for candidate in ("001", "002", "003"):
        lesson = lessons[f"lesson.foreach_norm.{candidate}"]
        full_cases = lesson["intervention"]["workload_cases"]
        assert len(full_cases) == 20
        full_by_id = {case["case_id"]: case for case in full_cases}
        assert len(full_by_id) == 20
        for group in ("effective_conditions", "ineffective_conditions", "counterexamples"):
            for condition in lesson[group]:
                for case in condition["cases"]:
                    assert set(case) == {"case_id", "p", "dtype", "lengths", "list_length", "speedup", "regression"}
                    assert all(full_by_id[case["case_id"]][k] == v for k, v in case.items())
        assert all("evidence" in case and "shapes" in case and "baseline_cv" in case for case in full_cases)


def test_method_and_infrastructure_are_separate_and_json_compatible(lessons):
    assert len(lessons) == 6
    assert lessons["lesson.method.aa_lifecycle"]["kind"] == "measurement_method"
    infra = lessons["lesson.infrastructure.artifact_preflight"]
    assert infra["kind"] == "infrastructure"
    assert infra["counterexamples"][0]["admitted_speedup"] is None
    assert infra["intervention"]["formal_run_written"] is False
    scope = lessons["lesson.method.timing_output_scope"]["counterexamples"][0]
    assert (scope["context_sessions"], scope["verified_final_outputs"]) == (1200, 40)
    json.dumps(list(lessons.values()), allow_nan=False)


def test_every_evidence_path_and_json_pointer_resolves(lessons):
    checked = set()
    def visit(value):
        if isinstance(value, dict):
            if {"path", "selector", "purpose"} <= value.keys():
                path, selector = Path(value["path"]), value["selector"]
                assert path.is_absolute() and path.is_file()
                if (str(path), selector) not in checked and path.suffix == ".json":
                    doc = json.loads(path.read_text())
                    if selector:
                        assert selector.startswith("/")
                        for part in selector[1:].split("/"):
                            part = part.replace("~1", "/").replace("~0", "~")
                            doc = doc[int(part)] if isinstance(doc, list) else doc[part]
                    checked.add((str(path), selector))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(list(lessons.values()))
    assert len(checked) > 50
