"""A collection-local inventory proof must preserve full source and file identity."""
import os
from pathlib import Path
import sys

import pytest


SCRIPTS = Path(__file__).resolve().parents[2] / "skill-libs/graph-base/0.5.1/skills/ascendc-aprof-profiling/scripts"
sys.path.insert(0, str(SCRIPTS))
import device_task_window_timing as collector
import aprof_runtime.task_window_measurement_admission as admission


@pytest.fixture
def fixed(tmp_path, monkeypatch):
    def file(name, text):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return str(path)

    baseline = Path(file("source/kernel.cpp", "kernel")).parent
    build = Path(file("built/op_host/host.cpp", "host")).parents[1]
    binary = file("binary", "binary")
    receipt = file("build-receipt.json", "{}")
    python = file("python", "interpreter")
    verifier = file("oracle.py", "oracle")
    dependency = file("input.bin", "input")
    profiler = file("profiler", "profiler")
    release = Path(file("release/producer.py", "producer")).parent
    monkeypatch.setattr(collector, "RELEASE", release)
    monkeypatch.setattr(collector, "PRODUCER_FILES", ("producer.py",))
    monkeypatch.setattr(collector.shared, "RELEASE", release)
    monkeypatch.setattr(collector.shared, "PRODUCERS", ("producer.py",))
    monkeypatch.setattr(admission, "PROFILE_DEPENDENCY_PATHS", (profiler, dependency))
    case = {"case_id": 1, "prepared_files": [dependency], "verify_commands": {
        role: [python, verifier, "--output", "{cycle_dir}/" + role + ".bin"]
        for role in collector.ROLES}}
    config = {"roles": {role: {"source_dir": str(baseline)} for role in collector.ROLES},
        "build": {"source_dir": str(build), "binary": binary, "receipt_files": [receipt]},
        "cases": [case], "task_profile": {"profiler": profiler}}
    return config


def test_same_outputs_complete_roster_and_qualified_proof_reuse(fixed, monkeypatch):
    clock = 0
    monkeypatch.setattr(collector.time, "monotonic_ns", lambda: clock)
    expected = collector.shared.inventory(fixed)
    expected["files"].update({path: collector.file_hash(path) for path in admission.PROFILE_DEPENDENCY_PATHS})
    original = collector.file_hash
    calls = []

    def counted(path):
        calls.append(Path(path))
        return original(path)

    monkeypatch.setattr(collector, "file_hash", counted)
    proof = collector._InventoryProof()
    assert collector.inventory(fixed, _proof=proof) == expected
    clock += 2 * collector._INVENTORY_PROOF_INTERVAL_NS
    assert collector.inventory(fixed, _proof=proof) == expected
    count = len(calls)
    assert collector.inventory(fixed, fixed["cases"][0], _proof=proof) == expected
    assert collector.profile_dependencies(_proof=proof) == {
        path: expected["files"][path] for path in admission.PROFILE_DEPENDENCY_PATHS}
    assert len(calls) == count
    # A new collection cannot inherit any earlier file proof.
    assert collector.inventory(fixed, _proof=collector._InventoryProof()) == expected
    assert len(calls) > count


@pytest.mark.parametrize("mutation", ("same_size_restored_mtime", "replace_inode", "chmod", "symlink"))
def test_stable_path_is_not_enough(fixed, mutation):
    proof = collector._InventoryProof()
    collector.inventory(fixed, _proof=proof)
    path = Path(fixed["cases"][0]["prepared_files"][0])
    before = path.stat()
    if mutation == "same_size_restored_mtime":
        path.write_text("other")
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    elif mutation == "replace_inode":
        replacement = path.with_name("replacement")
        replacement.write_bytes(path.read_bytes())
        os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
        replacement.replace(path)
    elif mutation == "chmod":
        path.chmod(before.st_mode ^ 0o100)
    else:
        target = path.with_name("target")
        path.rename(target)
        path.symlink_to(target)
    with pytest.raises(ValueError):
        collector.inventory(fixed, _proof=proof)


def test_changed_during_first_hash_is_never_cached(tmp_path, monkeypatch):
    path = tmp_path / "source"
    path.write_text("before")
    original = collector.file_hash

    def changing(value):
        digest = original(value)
        Path(value).write_text("after!")
        return digest

    monkeypatch.setattr(collector, "file_hash", changing)
    proof = collector._InventoryProof()
    try:
        proof.digest(path)
    except ValueError as error:
        assert "during hashing" in str(error)
        assert not proof.files
    else:
        # Equal timestamp tuples do occur on the real local filesystem. The
        # first digest remains provisional and the next read must reject it.
        assert proof.files[path][2] is False
        monkeypatch.setattr(collector, "file_hash", original)
        with pytest.raises(ValueError):
            proof.digest(path)


def test_same_stat_change_cannot_be_promoted_by_elapsed_time(tmp_path, monkeypatch):
    path = tmp_path / "source"
    path.write_bytes(b"before")
    identity = collector._InventoryProof.identity(path)
    proof = collector._InventoryProof()
    monkeypatch.setattr(proof, "identity", lambda value: identity)
    clock = 0
    monkeypatch.setattr(collector.time, "monotonic_ns", lambda: clock)
    proof.digest(path)
    assert proof.files[path][2] is False
    path.write_bytes(b"after!")
    clock += 2 * collector._INVENTORY_PROOF_INTERVAL_NS
    with pytest.raises(ValueError, match="bytes changed without a new identity"):
        proof.digest(path)
    assert proof.files[path][2] is False


def test_fresh_proof_needs_a_later_full_read_using_monotonic_time(tmp_path, monkeypatch):
    path = tmp_path / "source"
    path.write_bytes(b"stable")
    clock = 0
    monkeypatch.setattr(collector.time, "monotonic_ns", lambda: clock)
    # Deliberately untrustworthy wall time must not promote a proof.
    monkeypatch.setattr(collector.time, "time_ns", lambda: 10**30)
    original, calls = collector.file_hash, []

    def counted(value):
        calls.append(value)
        return original(value)

    monkeypatch.setattr(collector, "file_hash", counted)
    proof = collector._InventoryProof()
    first = proof.digest(path)
    assert proof.files[path][2] is False
    assert proof.digest(path) == first
    assert len(calls) == 2
    clock += 2 * collector._INVENTORY_PROOF_INTERVAL_NS
    assert proof.digest(path) == first
    assert proof.files[path][2] is True
    assert len(calls) == 3
    assert proof.digest(path) == first
    assert len(calls) == 3


@pytest.mark.parametrize("mutation", ("add", "remove", "link_directory"))
def test_every_boundary_rescans_source_names(fixed, mutation):
    proof = collector._InventoryProof()
    before = collector.inventory(fixed, _proof=proof)
    root = Path(fixed["roles"]["baseline"]["source_dir"])
    if mutation == "add":
        (root / "added.cpp").write_text("added")
    elif mutation == "remove":
        (root / "kernel.cpp").unlink()
    else:
        (root / "linked").symlink_to(Path(fixed["build"]["source_dir"]), target_is_directory=True)
    if mutation in {"remove", "link_directory"}:
        with pytest.raises(ValueError):
            collector.inventory(fixed, _proof=proof)
    else:
        # run_session's existing exact comparison must see the newly added file.
        assert collector.inventory(fixed, _proof=proof) != before


def test_config_and_registration_share_proof(fixed, tmp_path, monkeypatch):
    header = tmp_path / "header.h"
    header.write_text("header")
    built = Path(fixed["build"]["source_dir"]) / "op_host/device_task_profile.h"
    built.write_bytes(header.read_bytes())
    clock = 0
    monkeypatch.setattr(collector.time, "monotonic_ns", lambda: clock)
    monkeypatch.setattr(collector, "HEADER_ASSET", header)
    monkeypatch.setattr(collector.old, "config_value", lambda value: value)
    monkeypatch.setattr(collector, "SUMMARY_PYTHON", Path(sys.executable).resolve())
    original = collector.file_hash
    calls = []

    def counted(path):
        calls.append(Path(path))
        return original(path)

    monkeypatch.setattr(collector, "file_hash", counted)
    proof = collector._InventoryProof()
    collector.config_value(fixed, _proof=proof)
    collector.inventory(fixed, _proof=proof)
    clock += 2 * collector._INVENTORY_PROOF_INTERVAL_NS
    collector.inventory(fixed, _proof=proof)
    count = len(calls)
    collector.profile_dependencies(_proof=proof)
    assert len(calls) == count
