import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "collection/scripts"))
import level2_parent_control_dedup as storage


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")


def fixture(tmp_path):
    run = tmp_path / "run"
    (run / "storage").mkdir(parents=True)
    control = run / "train/tasks/resize_bilinear/parent-controls/resize_bilinear001-aa-final-local-01"
    cohort = control / "cohort"
    cohort.mkdir(parents=True)
    names = [control.name + f"-p{i:02d}" for i in range(1, 7)]
    schedule = [{"name": name} for name in names]
    sessions = [str(cohort / name) for name in names]
    plan = {"comparison_kind": "aa", "protocol": "msprof_task_time_exploration_v2",
            "case_ids": list(range(1, 21)), "schedule": schedule}
    group = {"protocol": plan["protocol"], "status": "passed", "completed_sessions": sessions}
    report = {"comparison_kind": "aa", "protocol": plan["protocol"],
              "evidence_status": "verified_complete", "metric": "operator_task_sum_us",
              "operator": "resize_bilinear", "sessions": []}
    for name in names:
        session = cohort / name
        native = session / "native"
        native.mkdir(parents=True)
        outputs = []
        for case in range(1, 21):
            for config in ("normal", "swapped"):
                for role in ("A", "B"):
                    output = native / f"{case}_{config}_{role}.bin"
                    output.write_bytes(bytes([case]))
                    outputs.append({"case_id": str(case), "buffer_config": config,
                                    "role": role, "passed": True,
                                    "output_hash": storage.ref(output)["sha256"]})
        validation = session / "validation.json"
        write(validation, {"outputs": outputs})
        report["sessions"].append({"directory": str(session),
                                   "artifacts": {str(validation): storage.ref(validation)["sha256"]}})
    write(cohort / "plan.json", plan)
    write(cohort / "group-completion.json", group)
    write(cohort / "report.json", report)
    write(control / "request.json", {"version": "test"})
    completion = {"version": "level2_candidate_parent_aa_control_v1", "status": "passed",
                  "error": None, "source_attempt_added": False}
    for key, path in (("report", cohort / "report.json"),
                      ("group_completion", cohort / "group-completion.json"),
                      ("request", control / "request.json")):
        completion[key] = storage.ref(path)
    write(control / "completion.json", completion)
    return control


def test_closed_parent_outputs_reenter_without_changing_bytes(tmp_path):
    control = fixture(tmp_path)
    before = storage.inventory(control)[1]
    assert len(before) == 480
    with patch("level2_storage.exclusive_host", return_value=__import__("contextlib").nullcontext()), \
         patch("level2_storage.storage_lock", return_value=__import__("contextlib").nullcontext()):
        preview = storage.run(control, writers_closed=True)
        assert preview["potential_duplicate_bytes"] == 460
        first = storage.run(control, writers_closed=True, apply=True)
        second = storage.run(control, writers_closed=True, apply=True)
    assert first == second
    assert first["linked_duplicate_paths"] == 460
    after = storage.inventory(control)[1]
    assert [(row["path"], row["sha256"]) for row in before] == [
        (row["path"], row["sha256"]) for row in after]
    paths = [Path(row["path"]) for row in after]
    assert len({(p.stat().st_dev, p.stat().st_ino) for p in paths}) == 20


def test_foreign_temporary_link_is_rejected(tmp_path):
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    first.write_bytes(b"same")
    second.write_bytes(b"same")
    temporary = second.with_name(second.name + ".aprof-parent-dedup.tmp")
    temporary.write_bytes(b"foreign")
    rows = [{"path": str(p), "sha256": storage.ref(p)["sha256"], "bytes": 4}
            for p in (first, second)]
    with pytest.raises(ValueError, match="foreign temporary"):
        storage.replace_duplicates(rows)
    assert second.read_bytes() == b"same"


def test_incomplete_validation_is_rejected_before_mutation(tmp_path):
    control = fixture(tmp_path)
    path = control / "cohort" / (control.name + "-p01") / "validation.json"
    value = json.loads(path.read_text())
    value["outputs"][0]["passed"] = False
    write(path, value)
    with pytest.raises(ValueError, match="independent report binding"):
        storage.inventory(control)


def test_unknown_hardlink_alias_is_rejected(tmp_path):
    control = fixture(tmp_path)
    output = next((control / "cohort").rglob("native/*.bin"))
    os.link(output, tmp_path / "outside.bin")
    with pytest.raises(ValueError, match="outside the closed control roster"):
        storage.inventory(control)
