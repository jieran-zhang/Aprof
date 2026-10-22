import json
import os

import pytest

from aprof_runtime.cli import _parser, _evidence_reader, _local_result
from aprof_runtime.errors import StoreError
from aprof_runtime.jsonio import content_hash
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.profile_evidence import _load
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import register_json_artifact


class DelegatingLocal:
    def __init__(self, local):
        self.local = local

    def register_json(self, value):
        return self.local.register_json(value)

    def verify_artifact(self, reference):
        return self.local.verify_artifact(reference)

    def object_path(self, *args):
        pytest.fail("local result registration entered CAS storage")

    def register_artifact(self, *args, **kwargs):
        pytest.fail("local JSON must not be copied into persistent storage")


def test_delegating_local_and_real_cas_registration(tmp_path):
    local = LocalEvidence(tmp_path / "records")
    wrapper = DelegatingLocal(local)
    value = {"new_gate_request": {"status": "unmeasured"}}
    ref = register_json_artifact(wrapper, value)
    assert ref == content_hash(value)
    assert register_json_artifact(wrapper, value) == ref
    assert len(list(local.directory.iterdir())) == 1
    index = local.write_index(tmp_path / "index.json")
    assert _load(LocalEvidence.from_index(index), ref) == value
    with EpisodeStore(tmp_path / "archive.sqlite") as store:
        archived = register_json_artifact(store, value)
        assert archived == ref
        assert json.loads(store.verify_artifact(archived).read_text()) == value


def test_local_replay_hash_and_parse_cache_detects_mutation(tmp_path, monkeypatch):
    import aprof_runtime.local_evidence as module
    import aprof_runtime.profile_evidence as profile
    local = LocalEvidence(tmp_path / "records")
    source = tmp_path / "source.json"
    source.write_text('{"a":[1]}')
    ref = local.register_artifact(source)
    hashes, parses = [], []
    original_hash, original_parse = module.file_hash, profile._json
    monkeypatch.setattr(module, "file_hash", lambda path: (hashes.append(path), original_hash(path))[1])
    monkeypatch.setattr(profile, "_json", lambda text: (parses.append(text), original_parse(text))[1])
    first = _load(local, ref)
    first["a"].append(2)
    assert _load(local, ref) == {"a": [1]}
    assert len(hashes) >= 2 and len(parses) == 1
    before = source.stat()
    source.write_text('{"a":[9]}')
    os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
    with pytest.raises(StoreError, match="changed"):
        _load(local, ref)


def test_fresh_reader_never_inherits_verified_cache(tmp_path):
    local = LocalEvidence(tmp_path / "records")
    ref = local.register_json({"a": 1})
    index = local.write_index(tmp_path / "index.json")
    path = local.verify_artifact(ref)
    path.write_text('{"a":2}')
    with pytest.raises(StoreError, match="changed"):
        LocalEvidence.from_index(index).verify_artifact(ref)


def test_registered_log_snapshot_survives_export_append(tmp_path):
    local = LocalEvidence(tmp_path / "records")
    log = tmp_path / "profile.log"
    log.write_text("capture complete\n")
    original = local.register_artifact(log)
    snapshot = local.snapshot_file(log)
    assert snapshot == original
    assert local.verify_artifact(snapshot).parent == local.directory
    with log.open("a") as stream:
        stream.write("export complete\n")
    assert local.verify_artifact(snapshot).read_text() == "capture complete\n"


def test_local_cli_handoff_keeps_new_records_without_overwriting(tmp_path):
    local = LocalEvidence(tmp_path / "records")
    local.register_json({"before": True})
    original = local.write_index(tmp_path / "input.json")
    original_bytes = original.read_bytes()
    args = _parser().parse_args(["candidate", "gate", "--request", "request.json",
                                "--local-index", str(original)])
    with _evidence_reader(args) as reader:
        new_ref = register_json_artifact(DelegatingLocal(reader), {"after": True})
        result = _local_result(args, reader, {"outcomes": []})
    assert original.read_bytes() == original_bytes
    assert not result["archive_performed"]
    assert LocalEvidence.from_index(result["local_index"]).verify_artifact(new_ref).exists()
    assert not list(tmp_path.glob("*.sqlite"))


@pytest.mark.parametrize("command", [["candidate", "gate"], ["exploration", "gate"], ["exploration", "verify"]])
def test_cli_storage_choices_are_exclusive(command):
    with pytest.raises(SystemExit):
        _parser().parse_args(command + ["--request", "r", "--local-index", "l", "--store", "s"])


def test_occupied_output_rejected_before_gate(tmp_path):
    from aprof_runtime.errors import ContractError
    local = LocalEvidence(tmp_path / "records")
    index = local.write_index(tmp_path / "index.json")
    args = _parser().parse_args(["candidate", "gate", "--request", "r", "--local-index", str(index),
                                "--output-index", str(index)])
    with pytest.raises(ContractError, match="new file"):
        _evidence_reader(args)


def test_child_handoff_indexes_raw_files_without_copying(tmp_path):
    parent = LocalEvidence(tmp_path / "parent-records")
    stage = tmp_path / "stage"
    stage.mkdir()
    child = LocalEvidence(stage / "records")
    raw = stage / "op_summary.csv"
    raw.write_text("Task Duration(us)\n3.2\n")
    raw_ref = child.register_artifact(raw)
    index = child.write_index(stage / "local-evidence-index.json")
    index_ref = parent.merge_index(index)
    assert parent.verify_artifact(raw_ref) == raw
    assert parent.verify_artifact(index_ref) == index
    assert not list(parent.directory.iterdir())
    terminal_index = parent.write_index(tmp_path / "terminal-index.json")
    assert LocalEvidence.from_index(terminal_index).verify_artifact(raw_ref) == raw
    raw.write_text("Task Duration(us)\n1.0\n")
    with pytest.raises(StoreError, match="changed"):
        parent.verify_artifact(raw_ref)


def test_other_workspace_child_handoff_is_rejected(tmp_path):
    root = tmp_path / "parent"
    root.mkdir()
    parent = LocalEvidence(root / "records")
    other = LocalEvidence(tmp_path / "other-records")
    index = other.write_index(tmp_path / "other-index.json")
    with pytest.raises(StoreError, match="escaped"):
        parent.merge_index(index)
