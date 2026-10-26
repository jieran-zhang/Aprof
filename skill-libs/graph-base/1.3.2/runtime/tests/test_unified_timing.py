from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import jsonschema
import pytest

from aprof_runtime.cli import main
from aprof_runtime.contracts import GateEvidence
from aprof_runtime.errors import ContractError
from aprof_runtime.measurement_entry import verify_measurement_admission
from aprof_runtime.unified_timing import evaluate_request, file_hash, finalize_timing, replay_capture, verify_timing
from test_unified_capture import FakeRunner, capture_config, prepare_correctness
from single_role_task import collect


def ref(root, path):
    return {"path": str(path.relative_to(root)), "sha256": file_hash(path)}


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True))


class CaseRunner(FakeRunner):
    def __call__(self, argv, *, cwd, env, timeout_seconds):
        configured = self.duration
        if isinstance(configured, dict):
            self.duration = configured[int(Path(cwd).name.split("_")[-1])]
        try:
            return super().__call__(argv, cwd=cwd, env=env, timeout_seconds=timeout_seconds)
        finally:
            self.duration = configured


def campaign(root, *, baseline_us=100, candidate_us=80, case_ids=(1,), stability_policy=None, samples=None,
             declaration_overrides=None):
    """纯 CPU 联合集成样例；FakeRunner 不启动 NPU。"""
    config = capture_config(root / "inputs")
    declaration_path = Path(config["declaration"]["path"])
    declaration = json.loads(declaration_path.read_text())
    declaration["case_ids"] = list(case_ids)
    declaration["correctness_case_ids"] = list(case_ids)
    if stability_policy is not None:
        declaration["stability_policy"] = stability_policy
    if declaration_overrides:
        declaration.update(declaration_overrides)
    write(declaration_path, declaration)
    config["declaration"]["sha256"] = file_hash(declaration_path)
    config["cases"] = [{**deepcopy(config["cases"][0]), "case_id": case} for case in case_ids]
    correctness = {}
    captures = {}
    sources = {}
    for role, duration in (("baseline", baseline_us), ("candidate", candidate_us)):
        if role == "candidate":
            Path(config["source_files"][0]).write_text("candidate source")
            Path(config["binary"]).write_text("candidate binary")
        correctness[role] = prepare_correctness(config, root / f"{role}_correctness") if len(case_ids) == 1 else None
        if correctness[role] is None:
            collect(config, root / f"{role}_correctness", runner=FakeRunner(config), correctness_only=True)
            correctness[role] = root / f"{role}_correctness/correctness.json"
            config["correctness"] = {"path": str(correctness[role]), "sha256": file_hash(correctness[role])}
        class SampleRunner(CaseRunner):
            def __call__(self, argv, *, cwd, env, timeout_seconds):
                result = super().__call__(argv, cwd=cwd, env=env, timeout_seconds=timeout_seconds)
                if samples and role in samples and Path(argv[1]).name == "msprof.py":
                    table = Path(cwd) / "profile/PROF_test/kernel_details.csv"
                    rows = table.read_text().splitlines()
                    for call, value in enumerate(samples[role]):
                        for offset, name in ((2, "first"), (3, "second")):
                            rows[call * 3 + offset] = f"{name},Target,{value / 2},7"
                    table.write_text("\n".join(rows) + "\n")
                return result
        collect(config, root / role, runner=SampleRunner(config, duration=duration))
        captures[role] = [root / role / f"case_{case}/capture.json" for case in case_ids]
        sources[role] = json.loads(captures[role][0].read_text())["identity"]["source_sha256"]
    request = {"schema_version": 1, "protocol": config["protocol"], "operator": config["operator"],
        "candidate_id": "candidate-one", "baseline_source_sha256": sources["baseline"],
        "candidate_source_sha256": sources["candidate"], "declaration": ref(root, declaration_path),
        "baseline_captures": [ref(root, p) for p in captures["baseline"]],
        "candidate_captures": [ref(root, p) for p in captures["candidate"]],
        "baseline_correctness": ref(root, correctness["baseline"]),
        "candidate_correctness": ref(root, correctness["candidate"])}
    request_path = root / "comparison.json"
    write(request_path, request)
    return request_path, config


def test_formal_point_estimate_and_cli_replay(tmp_path, capsys):
    request, _ = campaign(tmp_path)
    output = tmp_path / "result.json"
    assert main(["timing", "finalize", "--request", str(request), "--output", str(output)]) == 0
    result = json.loads(output.read_text())
    assert result["verdict"] == "accepted"
    assert result["speedup"] == 1.25
    assert result["authority"] == "performance_engineering_only"
    assert not {"pair_count", "speedup_lcb", "selected_as_best", "policy_update_eligible"} & result.keys()
    assert main(["timing", "verify", "--result", str(output)]) == 0
    assert verify_timing(output)["valid"] is True
    schema_dir = Path(__file__).parents[2] / "schemas"
    for name, value in (("request", json.loads(request.read_text())), ("result", result)):
        jsonschema.validate(value, json.loads((schema_dir / f"unified-timing-{name}.schema.json").read_text()))
    with pytest.raises(FileExistsError):
        finalize_timing(request, output)


def test_rejects_missing_case_and_wrong_source(tmp_path):
    request_path, _ = campaign(tmp_path, case_ids=(1, 2))
    value = json.loads(request_path.read_text())
    value["candidate_captures"].pop()
    write(request_path, value)
    with pytest.raises(ContractError, match="覆盖"):
        evaluate_request(request_path)
    value["candidate_source_sha256"] = "sha256:" + "0" * 64
    write(request_path, value)
    with pytest.raises(ContractError, match="正确性身份"):
        evaluate_request(request_path)


def test_manifest_source_relabel_cannot_change_snapshot(tmp_path):
    request, _ = campaign(tmp_path)
    path = tmp_path / "candidate/case_1/capture.json"
    capture = json.loads(path.read_text())
    capture["identity"]["source_sha256"] = "sha256:" + "0" * 64
    write(path, capture)
    with pytest.raises(ContractError, match="source 身份"):
        replay_capture(path)


def test_candidate_artifact_becomes_new_baseline_without_rewrite(tmp_path):
    request_path, config = campaign(tmp_path)
    old = json.loads(request_path.read_text())
    previous = tmp_path / old["candidate_captures"][0]["path"]
    before = previous.read_bytes()
    Path(config["source_files"][0]).write_text("next source")
    Path(config["binary"]).write_text("next binary")
    correct = prepare_correctness(config, tmp_path / "next_correctness")
    collect(config, tmp_path / "next", runner=FakeRunner(config, duration=60))
    new_capture = tmp_path / "next/case_1/capture.json"
    old.update(candidate_id="next", baseline_source_sha256=old["candidate_source_sha256"],
        candidate_source_sha256=json.loads(new_capture.read_text())["identity"]["source_sha256"],
        baseline_captures=old["candidate_captures"], baseline_correctness=old["candidate_correctness"],
        candidate_captures=[ref(tmp_path, new_capture)], candidate_correctness=ref(tmp_path, correct))
    write(request_path, old)
    assert evaluate_request(request_path)["speedup"] == pytest.approx(4 / 3)
    assert previous.read_bytes() == before


def test_expired_evidence_is_inconclusive(tmp_path):
    request, _ = campaign(tmp_path)
    later = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    result = evaluate_request(request, evaluated_at=later)
    assert result["verdict"] == "inconclusive"
    assert any("复用时限" in reason for reason in result["reasons"])


def test_replay_detects_forged_result_and_raw_file(tmp_path):
    request, _ = campaign(tmp_path)
    output = tmp_path / "result.json"
    result = finalize_timing(request, output)
    result["speedup"] = 2
    write(output, result)
    with pytest.raises(ContractError, match="结果与原始"):
        verify_timing(output)
    path = tmp_path / "candidate/case_1/profile/PROF_test/kernel_details.csv"
    path.write_text(path.read_text().replace("second,Target,40.0", "second,Target,400.0", 1))
    with pytest.raises(ContractError, match="SHA256"):
        evaluate_request(request)


def test_every_case_regression_is_checked(tmp_path):
    request, _ = campaign(tmp_path, baseline_us=100, candidate_us=104)
    result = evaluate_request(request)
    assert result["verdict"] == "rejected"
    assert result["max_case_regression"] == pytest.approx(0.04)
    assert any("回归超过" in reason for reason in result["reasons"])


def test_old_paired_measurement_cannot_enter_current_gate():
    evidence = GateEvidence.from_dict({"candidate_id": "old", "static_review": "passed", "build": "passed",
        "accuracy": "passed", "runtime": "passed", "semantic": "passed", "scope": "passed", "portability": "passed",
        "baseline_samples_ns": [100] * 30, "candidate_samples_ns": [80] * 30, "artifacts": {}})
    with pytest.raises(ContractError, match="timing finalize"):
        verify_measurement_admission(evidence, None, source_hashes={})


def test_geometric_mean_does_not_hide_individual_regression(tmp_path):
    request, _ = campaign(tmp_path, case_ids=(1, 2), candidate_us={1: 50, 2: 104})
    result = evaluate_request(request)
    assert result["speedup"] == pytest.approx((2 * 100 / 104) ** 0.5)
    assert result["verdict"] == "rejected"
    assert result["max_case_regression"] == pytest.approx(0.04)


def test_manifest_timestamp_cannot_refresh_old_execution(tmp_path):
    _, _ = campaign(tmp_path)
    path = tmp_path / "baseline/case_1/capture.json"
    value = json.loads(path.read_text())
    value["captured_at"] = (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat()
    write(path, value)
    with pytest.raises(ContractError, match="采集时间晚于执行"):
        replay_capture(path)


def test_high_within_process_variation_is_inconclusive(tmp_path):
    request, config = campaign(tmp_path)

    class NoisyRunner(FakeRunner):
        def __call__(self, argv, *, cwd, env, timeout_seconds):
            result = super().__call__(argv, cwd=cwd, env=env, timeout_seconds=timeout_seconds)
            if Path(argv[1]).name == "msprof.py":
                table = Path(cwd) / "profile/PROF_test/kernel_details.csv"
                rows = table.read_text().splitlines()
                for call in range(20):
                    duration = 20 if call % 2 else 60
                    for offset, name in ((2, "first"), (3, "second")):
                        rows[call * 3 + offset] = f"{name},Target,{duration},7"
                table.write_text("\n".join(rows) + "\n")
            return result

    collect(config, tmp_path / "noisy", runner=NoisyRunner(config))
    value = json.loads(request.read_text())
    value["candidate_captures"] = [ref(tmp_path, tmp_path / "noisy/case_1/capture.json")]
    write(request, value)
    result = evaluate_request(request)
    assert result["speedup"] == 1.25
    assert result["verdict"] == "inconclusive"
    assert any("轮内 CV" in reason for reason in result["reasons"])
