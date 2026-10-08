import json
from pathlib import Path
import shutil

import pytest

import organize_optimization_traces as collection


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def fixture(tmp_path):
    checkout = tmp_path / "checkout"
    dataset = checkout / ".aprof/runs/level1-msprof-feedback-fixture/dataset/v2"
    evidence = tmp_path / "original-evidence.json"
    evidence.write_bytes(b'{"truth": "original"}\n')
    content = collection.digest(evidence.read_bytes())
    revision = dataset / "revisions/fixture"
    record = {"id": "attempt-1", "record_hash": "sha256:" + "1" * 64,
              "record_kind": "optimization_memory"}
    files = {"evidence_index.json": {"e1": dict(path=str(evidence), sha256=content,
                    size_bytes=evidence.stat().st_size, selector="", split="train")}}
    for name, value in files.items():
        put(revision / name, value)
    for split in ("train", "validation"):
        for name in ("optimization_traces.jsonl", "lessons.jsonl"):
            path = revision / split / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record) + "\n" if split == "train" and name.startswith("optimization") else "")
    manifest = {"files": {str(p.relative_to(revision)): collection.digest(p.read_bytes())
                          for p in revision.rglob("*") if p.is_file()}}
    put(revision / "manifest.json", manifest)
    put(dataset / "current.json", {"revision": "fixture", "manifest_hash": collection.digest((revision / "manifest.json").read_bytes())})
    run = tmp_path / "paused-level2"
    put(run / "campaign-manifest.json", {"source_attempts_planned": 3})
    task = run / "train/tasks/operator"
    feedback = task / "feedback/operator001.json"
    put(feedback, {"candidate_id": "operator001", "status": "build_failed"})
    events = [{"kind": "source_attempt_registered", "value": {"candidate_id": "operator001"}},
              {"kind": "candidate_feedback_closed", "value": {"feedback": {
                  "path": str(feedback), "sha256": collection.digest(feedback.read_bytes())}}}]
    (task / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    (run / "validation/tasks").mkdir(parents=True)
    (task / "output.key_out").write_bytes(b"binary evidence" * 100)
    return checkout, run, evidence, content


def test_preserves_published_bytes_partial_failures_and_local_readability(tmp_path):
    checkout, run, evidence, sha = fixture(tmp_path)
    output = tmp_path / "central"
    index = collection.organize(output, [checkout], run, threshold=100)
    assert index["level1"]["memory_rows"] == 1
    assert index["level2"]["closed_attempts"] == 1
    assert index["level2"]["published_optimization_memories"] == 0
    assert index["level2"]["hardlinked_payload_files"] == 1
    assert collection.verify(output, deep=True)["status"] == "passed"
    record = json.loads((output / "level2/paused-level2/source_attempts.jsonl").read_text())
    assert record["feedback"]["status"] == "build_failed"
    evidence.unlink()
    linked = next((output / "level2/paused-level2/payloads").rglob("*"))
    if linked.is_dir():
        linked = next(linked.iterdir())
    (run / "train/tasks/operator/output.key_out").unlink()
    assert linked.read_bytes() == b"binary evidence" * 100
    entry = collection.read_json(output / "level1/evidence-index.json")[sha]
    assert b"".join(collection.entry_bytes(output, entry)) == b'{"truth": "original"}\n'


def test_packed_tampering_and_metadata_tampering_rejected(tmp_path):
    checkout, run, _, sha = fixture(tmp_path)
    output = tmp_path / "central"
    collection.organize(output, [checkout], run, threshold=100)
    entry = collection.read_json(output / "level1/evidence-index.json")[sha]
    with (output / entry["container"]).open("r+b") as stream:
        stream.seek(entry["offset"])
        stream.write(b"x")
    with pytest.raises(ValueError, match="packed evidence changed"):
        collection.verify(output, deep=True)
    (output / "index.json").write_text('{}')
    with pytest.raises((ValueError, KeyError)):
        collection.verify(output)


def test_symlink_and_changed_signed_evidence_fail_before_publication(tmp_path):
    checkout, run, evidence, _ = fixture(tmp_path)
    evidence.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="signed evidence changed"):
        collection.organize(tmp_path / "bad", [checkout], run, threshold=100)
    assert not (tmp_path / "bad").exists()
    (tmp_path / "symbolic").symlink_to(evidence)
    with pytest.raises(ValueError, match="symlink"):
        collection.safe_path(tmp_path, "symbolic")
    with pytest.raises(ValueError, match="unsafe"):
        collection.safe_path(tmp_path, "../escape")


def test_same_id_different_revisions_survive_and_exact_duplicates_are_indexed(tmp_path):
    checkout, run, _, _ = fixture(tmp_path)
    source = checkout / ".aprof/runs/level1-msprof-feedback-fixture"
    for name, change in (("level1-second", True), ("level1-third", False)):
        target = source.with_name(name)
        shutil.copytree(source, target)
        if change:
            revision = target / "dataset/v2/revisions/fixture"
            record_path = revision / "train/optimization_traces.jsonl"
            record = json.loads(record_path.read_text())
            record["record_hash"] = "sha256:" + "2" * 64
            record_path.write_text(json.dumps(record) + "\n")
            manifest = collection.read_json(revision / "manifest.json")
            manifest["files"]["train/optimization_traces.jsonl"] = collection.digest(record_path.read_bytes())
            put(revision / "manifest.json", manifest)
            put(target / "dataset/v2/current.json", {"revision": "fixture",
                "manifest_hash": collection.digest((revision / "manifest.json").read_bytes())})
    output = tmp_path / "central"
    index = collection.organize(output, [checkout], run, threshold=100)
    assert index["level1"]["memory_rows"] == 3
    assert index["level1"]["unique_memory_revisions"] == 2
    rows = collection.read_json(output / "level1/memory-catalog.json")
    assert sorted(len(r["occurrences"]) for r in rows) == [1, 2]
    assert index["level1"]["current_evidence_objects"] == 1


def test_raw_budget_keeps_explicit_external_inventory_without_read_fallback(tmp_path):
    checkout, run, _, _ = fixture(tmp_path)
    output = tmp_path / "central"
    index = collection.organize(output, [checkout], run, threshold=100, raw_budget=0)
    assert index["level2"]["external_raw_files"] == 1
    assert index["level2"]["all_run_regular_files_included"] is False
    assert collection.verify(output)["all_raw_payloads_local"] is False
    entries = collection.read_json(output / "level2/paused-level2/external-raw-inventory.json")
    entry = next(iter(entries.values()))
    with pytest.raises(ValueError, match="explicitly external"):
        b"".join(collection.entry_bytes(output, entry))


def test_known_native_outputs_share_one_payload_name(tmp_path):
    checkout, run, _, _ = fixture(tmp_path)
    task = run / "train/tasks/operator"
    session = task / "session"
    (session / "native").mkdir(parents=True)
    blob = b"same output" * 200
    rows, outputs = [], []
    for role in ("A", "B"):
        path = session / f"native/1_normal_{role}.bin"
        path.write_bytes(blob)
        rows.append(dict(type="output", case_id="1", buffer_config="normal", role=role, path=str(path)))
        outputs.append(dict(case_id="1", buffer_config="normal", role=role, output_hash=collection.digest(blob)))
    (session / "native/journal.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    put(session / "validation.json", {"outputs": outputs})
    output = tmp_path / "central"
    index = collection.organize(output, [checkout], run, threshold=100)
    assert index["level2"]["hardlinked_payload_files"] == 2  # one unrelated fixture + one shared output
    file_index = collection.read_json(output / "level2/paused-level2/file-index.json")
    assert file_index["train/tasks/operator/session/native/1_normal_A.bin"]["path"] == \
        file_index["train/tasks/operator/session/native/1_normal_B.bin"]["path"]


def test_resume_reuses_completed_level1_without_reading_original_payloads(tmp_path):
    checkout, run, evidence, _ = fixture(tmp_path)
    output = tmp_path / "central"
    with pytest.raises(ValueError, match="packed-byte budget"):
        collection.organize(output, [checkout], run, threshold=100, packed_budget=0)
    staging = next(tmp_path.glob("central.staging-*"))
    evidence.unlink()
    index = collection.organize(output, [checkout], run, threshold=100, resume_staging=staging)
    assert index["level1"]["memory_rows"] == 1
    assert collection.verify(output, deep=True)["status"] == "passed"


def test_method_validation_preserves_failed_observations_without_adding_attempts(tmp_path):
    checkout, run, _, _ = fixture(tmp_path)
    method = tmp_path / "method"
    put(method / "method-validation-summary.json", {"status": "passed", "new_source_attempts": 0})
    put(method / "failed-observation/completion.json", {"status": "failed"})
    put(method / "successful-observation/completion.json", {"status": "passed"})
    output = tmp_path / "central"
    index = collection.organize(output, [checkout], run, threshold=100, method_validation=method)
    assert index["method_validation"]["new_source_attempts"] == 0
    assert index["level2"]["registered_attempts"] == 1
    assert index["method_validation"]["files"] == 3
    assert collection.verify(output, deep=True)["status"] == "passed"


def test_reclassified_historical_source_failure_counts_as_closed_not_success(tmp_path):
    checkout, run, _, _ = fixture(tmp_path)
    task = run / "train/tasks/operator"
    events = [json.loads(row) for row in (task / "events.jsonl").read_text().splitlines()]
    events[1]["kind"] = "candidate_feedback_blocked"
    feedback = task / "feedback/operator001-reclassification.json"
    put(feedback, {"candidate_id": "operator001", "status": "source_attempt_failed",
                  "reclassification": {"source_attempt_added": False, "native_reexecuted": False}})
    events.append({"kind": "candidate_feedback_reclassified", "value": {"feedback": {
        "path": str(feedback), "sha256": collection.digest(feedback.read_bytes())}}})
    (task / "events.jsonl").write_text("\n".join(json.dumps(row) for row in events) + "\n")
    output = tmp_path / "central"
    index = collection.organize(output, [checkout], run, threshold=100)
    assert index["level2"]["closed_attempts"] == 1
    assert index["level2"]["registered_attempts"] == 1
    attempt = json.loads((output / "level2/paused-level2/source_attempts.jsonl").read_text())
    assert attempt["feedback"]["status"] == "source_attempt_failed"
    assert attempt["closed_event"]["kind"] == "candidate_feedback_reclassified"
