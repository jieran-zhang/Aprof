import hashlib
import json
from pathlib import Path

import pytest

import level2_partial_control_output_dedup as storage
from level2_partial_control_output_dedup import deduplicate


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def fixture(tmp_path):
    stage = tmp_path / "train/tasks/cummin/stages/aa-test"
    names = [f"aa-test-p{i:02d}" for i in range(1, 7)]
    write(stage / "stage-plan.json", {
        "control_type": "aa", "group": stage.name,
        "case_ids": list(range(1, 21)), "protocol": "msprof_task_time_exploration_v2",
        "cohort": {"schedule": [{"name": name} for name in names]},
    })
    write(stage / "result.json", {"kind": "control", "status": "failed", "ended_at": 1})
    for name in names[:2]:
        session = stage / "cohort" / name
        outputs = []
        for case in range(1, 21):
            for config in ("normal", "swapped"):
                for role in ("A", "B"):
                    stem = f"{case}_{config}_{role}.bin"
                    payload = f"case-{case}-packed".encode()
                    packed = session / "native" / stem
                    packed.parent.mkdir(parents=True, exist_ok=True)
                    packed.write_bytes(payload)
                    parts = []
                    for part in ("values", "indices"):
                        data = f"case-{case}-{part}".encode()
                        path = packed.with_name(stem + "." + part)
                        path.write_bytes(data)
                        parts.append({"name": part, "path": str(path), "bytes": len(data), "sha256": sha(data)})
                    write(packed.with_name(stem + ".outputs.json"),
                          {"version": "level2_output_bundle_v1", "operator": "cummin", "outputs": parts})
                    outputs.append({"case_id": str(case), "buffer_config": config,
                                    "role": role, "passed": True, "output_hash": sha(payload)})
        write(session / "completion.json", {"status": "passed", "error": None})
        write(session / "validation.json", {"outputs": outputs})
    return stage, names


def test_failed_control_preserves_bytes_and_paths(tmp_path):
    stage, names = fixture(tmp_path)
    before = stage / "cohort" / names[0] / "native/5_normal_A.bin.indices"
    after = stage / "cohort" / names[1] / "native/5_swapped_B.bin.indices"
    assert before.stat().st_ino != after.stat().st_ino
    dry = deduplicate(stage, names[1], writers_closed=True)
    assert dry["status"] == "verified_dry_run"
    assert dry["logical_files"] == 480 and dry["unique_payloads"] == 60
    result = deduplicate(stage, names[1], writers_closed=True, apply=True)
    assert result["status"] == "complete" and result["logical_paths_preserved"] is True
    assert before.read_bytes() == after.read_bytes() == b"case-5-indices"
    assert before.stat().st_ino == after.stat().st_ino
    assert deduplicate(stage, names[1], writers_closed=True, apply=True)["receipt"] == result["receipt"]


def test_tampered_output_and_incomplete_session_fail_closed(tmp_path):
    stage, names = fixture(tmp_path)
    target = stage / "cohort" / names[1] / "native/1_normal_A.bin.values"
    target.write_bytes(b"X" * len(b"case-1-values"))
    with pytest.raises(ValueError, match="hash differs"):
        deduplicate(stage, names[1], writers_closed=True, apply=True)
    assert not (stage / "partial-output-dedup").exists()
    target.write_bytes(b"case-1-values")
    (stage / "cohort" / names[1] / "completion.json").unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        deduplicate(stage, names[1], writers_closed=True, apply=True)


def test_only_completed_session_is_selected_during_paused_coordinator(tmp_path, monkeypatch):
    stage, names = fixture(tmp_path)
    (stage / "result.json").unlink()
    monkeypatch.setattr(storage, "paused", lambda pid, path: {"pid": pid, "cmdline_sha256": sha(b"argv")})
    result = deduplicate(stage, names[0], paused_pid=42, apply=True)
    assert result["logical_files"] == 240
    assert result["unique_payloads"] == 60
    assert not (stage / "partial-output-dedup" / names[1]).exists()
