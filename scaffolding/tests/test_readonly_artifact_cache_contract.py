"""Read-only replay cache regressions; never hardware or publication proof.

Only unchanged regular-file hashes may be reused within one reader. Every
lookup still checks the index, and callers retain transaction ownership.
"""
import contextlib
import hashlib
import importlib.util
import os
from pathlib import Path
import sqlite3

import pytest

from aprof_runtime import __version__

if __version__ != "0.2.2":
    pytest.skip("select graph-base/0.5.1", allow_module_level=True)

from aprof_runtime import store as runtime_store
from aprof_runtime.errors import StoreError
from aprof_runtime.jsonio import canonical_json
from aprof_runtime.task_measurement_admission import replay_task_measurement_admission
from test_shared_measurement_admission import archive, draft
from test_task_measurement_admission import task_archive

PUBLISHER_PATH = Path(__file__).resolve().parents[1] / "tools/verify_measurement_publication.py"
spec = importlib.util.spec_from_file_location("aprof_cache_contract_publisher", PUBLISHER_PATH)
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


@pytest.fixture(params=("runtime", "publisher"))
def cas(request, tmp_path, monkeypatch):
    database = tmp_path / "evidence.sqlite"
    content = b"original immutable evidence"
    reference = "sha256:" + hashlib.sha256(content).hexdigest()
    objects = runtime_store.default_object_directory(database)
    path = runtime_store._object_path(objects, reference)
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    with sqlite3.connect(database) as writer:
        writer.execute("CREATE TABLE artifacts(content_hash TEXT PRIMARY KEY)")
        writer.execute("INSERT INTO artifacts VALUES (?)", (reference,))
    if request.param == "runtime":
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        reader = runtime_store._ReadOnlyArtifacts(connection, objects)
        module, hash_name, error = runtime_store, "file_hash", StoreError
    else:
        reader = publisher.ReadonlyCAS(database)
        connection = reader.connection
        module, hash_name, error = publisher, "digest", ValueError
    # A future publisher may own an explicit snapshot at construction. These
    # tests deliberately end it to exercise uncached SQL visibility as well.
    if connection.in_transaction:
        connection.rollback()
    original_hash = getattr(module, hash_name)
    hashed, selected = [], []

    def counted_hash(value):
        hashed.append(Path(value))
        return original_hash(value)

    def trace(sql):
        if sql.lstrip().upper().startswith("SELECT") and "FROM ARTIFACTS" in sql.upper():
            selected.append(sql)

    monkeypatch.setattr(module, hash_name, counted_hash)
    connection.set_trace_callback(trace)
    yield dict(reader=reader, connection=connection, database=database, objects=objects,
               path=path, reference=reference, content=content, module=module,
               hash_name=hash_name, original_hash=original_hash, hashes=hashed,
               queries=selected, error=error, kind=request.param)
    connection.close()


def change_index(cas, sql):
    with sqlite3.connect(cas["database"]) as writer:
        writer.execute(sql, (cas["reference"],))


def test_repeated_object_hash_cached_but_autocommit_index_checked_each_time(cas):
    reader, connection = cas["reader"], cas["connection"]
    assert not connection.in_transaction
    assert reader.verify_artifact(cas["reference"]) == cas["path"]
    assert reader.verify_artifact(cas["reference"]) == cas["path"]
    assert len(cas["hashes"]) == 1
    assert len(cas["queries"]) == 2
    assert not connection.in_transaction, "resolver must not begin a caller transaction"


def test_same_length_mutation_with_restored_mtime_is_rejected(cas):
    cas["reader"].verify_artifact(cas["reference"])
    before = cas["path"].stat()
    cas["path"].write_bytes(b"x" * len(cas["content"]))
    os.utime(cas["path"], ns=(before.st_atime_ns, before.st_mtime_ns))
    assert cas["path"].stat().st_size == before.st_size
    assert cas["path"].stat().st_mtime_ns == before.st_mtime_ns
    with pytest.raises(cas["error"]):
        cas["reader"].verify_artifact(cas["reference"])


@pytest.mark.parametrize("change", ("replace_inode", "symlink", "missing", "directory"))
def test_cached_identity_does_not_hide_replacement_or_nonregular_object(cas, change):
    reader, path = cas["reader"], cas["path"]
    reader.verify_artifact(cas["reference"])
    previous = path.with_name("preserved-original")
    path.rename(previous)
    if change == "replace_inode":
        path.write_bytes(b"x" * len(cas["content"]))
        before = previous.stat()
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    elif change == "symlink":
        path.symlink_to(previous)
    elif change == "directory":
        path.mkdir()
    with pytest.raises(cas["error"]):
        reader.verify_artifact(cas["reference"])


def test_hash_completion_requires_unchanged_file_identity(cas, monkeypatch):
    def mutate_after_hash(path):
        digest = cas["original_hash"](path)
        before = Path(path).stat()
        Path(path).write_bytes(b"x" * len(cas["content"]))
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        return digest

    monkeypatch.setattr(cas["module"], cas["hash_name"], mutate_after_hash)
    with pytest.raises(cas["error"]):
        cas["reader"].verify_artifact(cas["reference"])


def test_cached_bytes_still_require_current_index_without_transaction(cas):
    cas["reader"].verify_artifact(cas["reference"])
    change_index(cas, "DELETE FROM artifacts WHERE content_hash=?")
    with pytest.raises(cas["error"]):
        cas["reader"].verify_artifact(cas["reference"])


def test_failed_index_lookup_is_not_cached_as_success(cas):
    change_index(cas, "DELETE FROM artifacts WHERE content_hash=?")
    with pytest.raises(cas["error"]):
        cas["reader"].verify_artifact(cas["reference"])
    change_index(cas, "INSERT INTO artifacts VALUES (?)")
    assert cas["reader"].verify_artifact(cas["reference"]) == cas["path"]


def test_index_visibility_survives_transaction_boundary(cas):
    connection, reader = cas["connection"], cas["reader"]
    connection.execute("BEGIN")
    reader.verify_artifact(cas["reference"])
    connection.commit()
    change_index(cas, "DELETE FROM artifacts WHERE content_hash=?")
    connection.execute("BEGIN")
    with pytest.raises(cas["error"]):
        reader.verify_artifact(cas["reference"])
    assert connection.in_transaction, "resolver must not end a caller transaction"
    connection.rollback()


def test_readonly_adapter_inside_writable_transaction_does_not_trust_in_transaction(cas):
    if cas["kind"] != "runtime":
        pytest.skip("publisher creates its own read-only connection")
    with sqlite3.connect(cas["database"]) as writer:
        reader = runtime_store._ReadOnlyArtifacts(writer, cas["objects"])
        writer.execute("BEGIN IMMEDIATE")
        reader.verify_artifact(cas["reference"])
        writer.execute("DELETE FROM artifacts WHERE content_hash=?", (cas["reference"],))
        with pytest.raises(StoreError):
            reader.verify_artifact(cas["reference"])
        assert writer.in_transaction
        writer.rollback()


def test_cache_does_not_cross_reader_instances(cas):
    cas["reader"].verify_artifact(cas["reference"])
    if cas["kind"] == "runtime":
        other = runtime_store._ReadOnlyArtifacts(cas["connection"], cas["objects"])
        other.verify_artifact(cas["reference"])
    else:
        other = publisher.ReadonlyCAS(cas["database"])
        try:
            other.verify_artifact(cas["reference"])
        finally:
            other.close()
    assert len(cas["hashes"]) == 2


def test_full_task_replay_output_bytes_match_uncached_reader(task_archive):
    store, raw, config, registration, worker, seal, expected, *_ = task_archive
    reference = seal()
    # EpisodeStore deliberately retains uncached current-byte verification.
    before = replay_task_measurement_admission(store, reference, expected=expected)
    with contextlib.closing(sqlite3.connect(store.path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        reader = runtime_store._ReadOnlyArtifacts(connection, store.objects_path)
        after = replay_task_measurement_admission(reader, reference, expected=expected)
    assert canonical_json(after) == canonical_json(before)
