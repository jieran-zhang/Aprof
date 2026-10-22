"""Buffered evidence must preserve failures without adding sampling-path I/O."""
from pathlib import Path

import pytest

from test_device_paired_timing_v050 import config, history, raw, stopped, timing

pytestmark = pytest.mark.skipif(timing.RELEASE.name != "0.5.1", reason="select graph-base/0.5.1")


def test_sampling_has_no_log_or_raw_file_writes(config, tmp_path, monkeypatch):
    sample, save = timing.TimingChild.sample, timing.save
    calls = []

    def checked_sample(child, *args):
        assert child.path.stat().st_size == 0
        result = sample(child, *args)
        assert child.path.stat().st_size == 0
        calls.append("sample")
        return result

    def checked_save(path, value):
        if Path(path).name == "raw_measurements.json":
            assert len(calls) == 12
            assert len([row for row in history(config) if row["kind"] == "quit"]) == 2
        return save(path, value)

    monkeypatch.setattr(timing.TimingChild, "sample", checked_sample)
    monkeypatch.setattr(timing, "save", checked_save)
    timing.collect(config, tmp_path / "evidence")
    data = raw(tmp_path)
    assert data["checkpoint_policy"] == "after_case_and_finally"
    previous = 0
    for row in data["records"]:
        for role in row["order"]:
            receipt = row["sample_receipts"][role]
            assert previous < receipt["request_monotonic_ns"] < receipt["response_monotonic_ns"]
            previous = receipt["response_monotonic_ns"]
    for role in timing.ROLES:
        text = (tmp_path / f"evidence/case-01-{role}.log").read_text()
        assert text.count(timing.PREFIX) == 6
    stopped(config)


def test_invalid_sample_keeps_buffered_logs_and_partial_record(config, tmp_path):
    config["cases"][0]["candidate"]["command"][2] = "bad_unit"
    with pytest.raises(ValueError, match="identity/unit/index/protocol"):
        timing.collect(config, tmp_path / "evidence")
    assert not raw(tmp_path)["complete"]
    assert raw(tmp_path)["records"][0]["baseline"] is not None
    assert timing.PREFIX in (tmp_path / "evidence/case-01-candidate.log").read_text()
    stopped(config)


def test_log_limit_fails_closed_and_preserves_prefix(config, tmp_path, monkeypatch):
    monkeypatch.setattr(timing, "MAX_CHILD_LOG_BYTES", 64)
    with pytest.raises(RuntimeError, match="buffered log limit"):
        timing.collect(config, tmp_path / "evidence")
    assert not raw(tmp_path)["complete"]
    assert "APROF_TIMING_READY" in (tmp_path / "evidence/case-01-baseline.log").read_text()
    stopped(config)
