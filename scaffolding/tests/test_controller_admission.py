"""Failure retention at the controller/collector boundary; no hardware claims."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "collection/scripts"))
import controller_admission as admission


class Files:
    def __init__(self):
        self.values = {}

    def register_artifact(self, path):
        value = Path(path).read_bytes()
        digest = "sha256:" + hashlib.sha256(value).hexdigest()
        self.values[digest] = value
        return digest


def recorder(tmp_path, collect):
    value = admission.AdmissionRecorder.__new__(admission.AdmissionRecorder)
    value.api = {"timing": SimpleNamespace(collect=collect)}
    value.store, value.output = Files(), tmp_path
    value.events, value.collected, value.partial, value.active = [], {}, {}, None
    value.protocol = {"purpose": "evaluation", "phases": {"aa_before": {"config_ref": "unit-config"}}}
    value.configs = {"aa_before": {"unit_fixture": "not hardware evidence"}}
    value.registration = {"stages": ["aa_before"]}
    value.registration_ref = "unit-preregistration"
    return value


def test_partial_collector_failure_retains_original_bytes_and_stops(tmp_path):
    stdout = tmp_path / "device.log"
    stdout.write_text("actual partial fixture log\n")

    def fail(_config, directory):
        directory.mkdir()
        (directory / "raw_measurements.json").write_text(json.dumps({
            "complete": False, "case_executions": [{"epochs": [{"commands": {
                "baseline": {"log_path": str(stdout)}}}]}]}))
        raise RuntimeError("collector stopped")

    value = recorder(tmp_path, fail)
    with pytest.raises(RuntimeError, match="collector stopped") as error:
        value.collect("aa_before")
    value.fail_active(error.value)
    assert stdout.read_bytes() in value.store.values.values()
    assert len(value.events) == 2
    terminal = json.loads(value.store.values[value.events[-1]])
    assert terminal["exit_status"] == 1 and len(terminal["evidence_refs"]) == 2
    assert not value.collected and value.active is None


def test_aa_statistics_cannot_override_formal_quality_failure(tmp_path, monkeypatch):
    def unstable(_config, directory):
        directory.mkdir()
        for name, payload in (("raw_measurements.json", {"case_executions": []}),
                              ("measurement_report.json", {"stable": False})):
            (directory / name).write_text(json.dumps(payload))
        return {"stable": False}

    monkeypatch.setattr(admission, "control_statistics", lambda *_a, **_k: {"passed": True})
    value = recorder(tmp_path, unstable)
    with pytest.raises(RuntimeError, match="measurement control failed"):
        value.collect("aa_before")
    terminal = json.loads(value.store.values[value.events[-1]])
    assert terminal["exit_status"] == 1
    assert json.loads((tmp_path / "aa_before-admission.json").read_text())["passed"] is False
