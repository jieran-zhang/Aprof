"""Entry-budget accounting only; no build, model, oracle or hardware execution."""
import sys
from types import SimpleNamespace

import pytest

import validation_host_evaluator as host


def invoke(entry, tmp_path, seconds):
    if entry == "qualification":
        return host.qualification(tmp_path / "plan.json", tmp_path / "qualification", seconds)
    return host.evaluate(tmp_path / "plan.json", {}, tmp_path / "workspace",
                         tmp_path / "result.json", "cpu-deadline", seconds)


@pytest.mark.parametrize("entry", ["qualification", "evaluate"])
@pytest.mark.parametrize("seconds", [float("nan"), float("inf"), float("-inf"), -1, 0, 3600.001, True, "60"])
def test_bad_budget_rejected_before_inputs_or_outputs(tmp_path, monkeypatch, entry, seconds):
    def no_read(_):
        pytest.fail("invalid budget must reject before reading task inputs")
    monkeypatch.setattr(host, "read", no_read)
    with pytest.raises(ValueError, match="finite.*3600"):
        invoke(entry, tmp_path, seconds)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("entry", ["qualification", "evaluate"])
@pytest.mark.parametrize("seconds, preparation_seconds", [(3600, 37), (60, 37), (60, 61)])
def test_preparation_elapsed_uses_original_remaining_budget(tmp_path, monkeypatch, entry,
                                                          seconds, preparation_seconds):
    clock = [100.0]
    monkeypatch.setattr(host.time, "monotonic", lambda: clock[0])
    monkeypatch.setitem(sys.modules, "controller_admission", SimpleNamespace(AdmissionRecorder=object))
    monkeypatch.setitem(sys.modules, "evaluate_skill_release", SimpleNamespace(tree_sha=object))
    plan = {"release": str(tmp_path), "operator": "exp", "profile": {}}
    monkeypatch.setattr(host, "read", lambda _: plan)
    monkeypatch.setattr(host, "imports", lambda _: {"profiler": SimpleNamespace(source_inventory=lambda _: {})})
    def prepare(*_):
        clock[0] += preparation_seconds
        return tmp_path / "source", tmp_path / "inputs"
    monkeypatch.setattr(host, "validate_plan", prepare)
    monkeypatch.setattr(host, "verify_qualification", lambda *_: tmp_path / "baseline")
    monkeypatch.setattr(host, "mechanism_choice", lambda *_: {})
    observed = []
    original = host.Commands
    class StoppedAfterRemaining(Exception):
        pass
    class CheckedCommands(original):
        def remaining(self):
            observed.append(self.deadline)
            remaining = super().remaining()
            assert remaining == seconds - preparation_seconds
            raise StoppedAfterRemaining
    monkeypatch.setattr(host, "Commands", CheckedCommands)
    expected = TimeoutError if preparation_seconds >= seconds else StoppedAfterRemaining
    with pytest.raises(expected):
        invoke(entry, tmp_path, seconds)
    assert observed == [100.0 + seconds]  # No reset to current time or increase to 3600.
