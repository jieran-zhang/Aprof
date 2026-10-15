"""Local profile persistence checks; these tests do not start a profiler or NPU."""
import json
from pathlib import Path
import sys
import time

import pytest

from aprof_runtime import __version__

if __version__ != "0.2.2":
    pytest.skip("select graph-base/0.5.1", allow_module_level=True)

from aprof_runtime.store import EpisodeStore
from aprof_runtime.task_measurement_admission import PRODUCER_FILES, select_mount

SCRIPTS = Path(__file__).resolve().parents[2] / "skill-libs/graph-base/0.5.1/skills/ascendc-aprof-profiling/scripts"
sys.path.insert(0, str(SCRIPTS))
import device_task_timing as collector


def profile(tmp_path):
    source = tmp_path / "local" / "profile"
    (source / "PROF_01" / "empty").mkdir(parents=True)
    (source / "PROF_01" / "raw.prof").write_bytes(b"native bytes\x00\xff")
    (source / "PROF_01" / "op_summary.csv").write_text("Task Duration(us)\n6.2\n")
    destination = tmp_path / "persistent" / "profile"
    destination.parent.mkdir()
    deadline = time.monotonic() + 30
    inventory = collector.profile_inventory(source, deadline=deadline)
    return source, destination, deadline, inventory


def test_complete_tree_is_preserved_and_atomically_published(tmp_path):
    source, destination, deadline, inventory = profile(tmp_path)
    receipt = collector.copy_profile_tree(source, destination, inventory, deadline=deadline)
    assert receipt["source_dir"] == str(source)
    assert receipt["destination_dir"] == str(destination)
    assert receipt["started_at"] <= receipt["finished_at"]
    assert receipt["source_inventory"] == receipt["source_after_inventory"] == receipt["persisted_inventory"] == inventory
    assert collector.profile_inventory(destination, deadline=deadline) == inventory
    assert (destination / "PROF_01" / "empty").is_dir()
    assert not destination.with_name("profile.partial").exists()
    assert (source / "PROF_01/raw.prof").read_bytes() == (destination / "PROF_01/raw.prof").read_bytes()


@pytest.mark.parametrize("existing", ["destination", "partial"])
def test_previous_output_is_never_overwritten(tmp_path, existing):
    source, destination, deadline, inventory = profile(tmp_path)
    previous = destination if existing == "destination" else destination.with_name("profile.partial")
    previous.mkdir()
    (previous / "evidence").write_bytes(b"old failed attempt")
    with pytest.raises(ValueError, match="must be fresh"):
        collector.copy_profile_tree(source, destination, inventory, deadline=deadline)
    assert (previous / "evidence").read_bytes() == b"old failed attempt"


@pytest.mark.parametrize("change", ["missing", "extra", "wrong_bytes"])
def test_registered_inventory_must_cover_every_source_file(tmp_path, change):
    source, destination, deadline, inventory = profile(tmp_path)
    if change == "missing": inventory.pop("PROF_01/raw.prof")
    elif change == "extra": inventory["nonexistent"] = next(iter(inventory.values()))
    else: (source / "PROF_01/raw.prof").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed before persistence"):
        collector.copy_profile_tree(source, destination, inventory, deadline=deadline)
    assert not destination.exists()


def test_source_mutation_during_copy_keeps_partial_and_rejects_receipt(tmp_path, monkeypatch):
    source, destination, deadline, inventory = profile(tmp_path)
    original = collector.shutil.copytree

    def changed_after_copy(src, dst, *args, **kwargs):
        result = original(src, dst, *args, **kwargs)
        if Path(src) == source:
            (source / "PROF_01/raw.prof").write_bytes(b"changed while copy completed")
        return result

    monkeypatch.setattr(collector.shutil, "copytree", changed_after_copy)
    with pytest.raises(ValueError, match="changed during copy"):
        collector.copy_profile_tree(source, destination, inventory, deadline=deadline)
    assert not destination.exists()
    assert destination.with_name("profile.partial").is_dir()


def test_links_and_expired_deadline_do_not_publish_a_tree(tmp_path):
    source, destination, _, inventory = profile(tmp_path)
    with pytest.raises(TimeoutError):
        collector.copy_profile_tree(source, destination, inventory, deadline=time.monotonic() - 1)
    assert not destination.exists()
    (source / "linked").symlink_to(source / "PROF_01/raw.prof")
    with pytest.raises(ValueError, match="symlink"):
        collector.copy_profile_tree(source, destination, inventory, deadline=time.monotonic() + 30)
    assert not destination.exists()


@pytest.mark.parametrize("value", ["relative", "parent_link", "self_link"])
def test_scratch_path_must_be_canonical_absolute(tmp_path, value):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    path = "relative" if value == "relative" else link / "scratch" if value == "parent_link" else link
    with pytest.raises(ValueError, match="canonical absolute"):
        collector.canonical_path(path)


@pytest.mark.parametrize("filesystem", ["nfs", "nfs4", "fuse.juicefs", "cifs"])
def test_remote_scratch_is_rejected_at_registration(tmp_path, monkeypatch, filesystem):
    output = tmp_path / "persistent"
    output.mkdir()
    original = collector.select_mount

    def remote(mountinfo, path):
        value = original(mountinfo, path)
        value["filesystem_type"] = filesystem
        return value

    monkeypatch.setattr(collector, "select_mount", remote)
    with EpisodeStore(tmp_path / "store.db") as store:
        with pytest.raises(ValueError, match="supported local filesystem"):
            collector.create_profile_storage(tmp_path / "scratch", output, store,
                started_at=time.time(), timeout_seconds=120)
    assert not (output / "profile-storage.json").exists()


def test_storage_registration_records_actual_mounts_and_private_mode(tmp_path):
    output, scratch = tmp_path / "persistent", tmp_path / "scratch"
    output.mkdir()
    with EpisodeStore(tmp_path / "store.db") as store:
        reference = collector.create_profile_storage(scratch, output, store,
            started_at=time.time(), timeout_seconds=120)
        storage = json.loads(store.verify_artifact(reference).read_text())
        mountinfo = store.verify_artifact(storage["mountinfo_ref"]).read_text()
        assert storage["scratch_mount"] == select_mount(mountinfo, scratch)
        assert storage["persistent_mount"] == select_mount(mountinfo, output)
        assert storage["directory_mode"] == scratch.stat().st_mode & 0o777 == 0o700
        with pytest.raises(FileExistsError):
            collector.create_profile_storage(scratch, output, store,
                started_at=time.time(), timeout_seconds=120)
    assert collector.PRODUCER_FILES == PRODUCER_FILES
    assert "runtime/src/aprof_runtime/store.py" in PRODUCER_FILES
