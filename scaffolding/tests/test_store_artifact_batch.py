"""Small-file CAS batch invariants for the Task profile importer."""

import pytest

from aprof_runtime import __version__

if __version__ != "0.2.2":
    pytest.skip("select graph-base/0.5.1", allow_module_level=True)

from aprof_runtime.errors import StoreError
from aprof_runtime.jsonio import file_hash
from aprof_runtime.store import EpisodeStore


def test_batch_preserves_complete_bytes_and_single_file_api(tmp_path):
    paths = [tmp_path / name for name in ("one.bin", "two.bin", "empty.bin")]
    for path, data in zip(paths, (b"first", b"second" * 11, b""), strict=True):
        path.write_bytes(data)
    with EpisodeStore(tmp_path / "store.sqlite") as store:
        refs = store.register_artifacts([*paths, paths[0]])
        assert refs == tuple(file_hash(path) for path in [*paths, paths[0]])
        assert store.connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 3
        assert all(store.verify_artifact(ref).read_bytes() == path.read_bytes()
                   for path, ref in zip(paths, refs[:3], strict=True))
        assert store.register_artifact(paths[0]) == refs[0]
        paths[0].write_bytes(b"changed source")
        assert store.verify_artifact(refs[0]).read_bytes() == b"first"
        assert store.register_artifact(paths[0]) == file_hash(paths[0])


def test_batch_rejects_corrupt_existing_object_before_indexing(tmp_path):
    first, second = tmp_path / "first.bin", tmp_path / "second.bin"
    first.write_bytes(b"fresh"); second.write_bytes(b"already indexed")
    with EpisodeStore(tmp_path / "store.sqlite") as store:
        old_ref = store.register_artifact(second)
        store.object_path(old_ref).write_bytes(b"corrupt")
        before = store.connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
        with pytest.raises(StoreError, match="existing CAS object is corrupt"):
            store.register_artifacts([first, second])
        assert store.connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == before
        assert store.connection.execute("SELECT 1 FROM artifacts WHERE content_hash=?", (file_hash(first),)).fetchone() is None


def test_batch_rolls_back_all_index_rows_on_late_sql_failure(tmp_path):
    first, second = tmp_path / "one.bin", tmp_path / "two.bin"
    first.write_bytes(b"one"); second.write_bytes(b"two")
    with EpisodeStore(tmp_path / "store.sqlite") as store:
        store.connection.execute("""CREATE TRIGGER fail_second_location BEFORE INSERT ON artifact_locations
            WHEN NEW.uri LIKE '%two.bin' BEGIN SELECT RAISE(ABORT, 'injected failure'); END""")
        with pytest.raises(StoreError, match="could not register artifact batch"):
            store.register_artifacts([first, second])
        assert store.connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0
        assert store.connection.execute("SELECT COUNT(*) FROM artifact_locations").fetchone()[0] == 0
        store.connection.execute("DROP TRIGGER fail_second_location")
        refs = store.register_artifacts([first, second])
        assert len(refs) == 2 and all(store.verify_artifact(ref).is_file() for ref in refs)
