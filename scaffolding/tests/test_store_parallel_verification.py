"""Complete CAS verification preserves file checks, ordering, and SQL isolation."""
from collections import Counter
from pathlib import Path
import sqlite3
import sys
import threading
import time

import pytest

RELEASE = Path(__file__).resolve().parents[2] / 'skill-libs/graph-base/0.5.1'
sys.path.insert(0, str(RELEASE / 'runtime/src'))
sys.path.insert(0, str(RELEASE / 'skills/ascendc-aprof-profiling/scripts'))
from aprof_runtime.errors import StoreError
from aprof_runtime.store import EpisodeStore
import aprof_runtime.store as store_module
import device_task_window_timing as collector


def seed(store, root):
    paths = [root / 'a', root / 'b']
    for path in paths: path.write_text(path.name)
    return paths, [store.register_artifact(path) for path in paths]


@pytest.mark.parametrize('workers', (1, 4))
def test_same_full_reads_duplicates_order_and_one_main_thread_snapshot(tmp_path, monkeypatch, workers):
    with EpisodeStore(tmp_path / 'store.db') as store:
        _, refs = seed(store, tmp_path)
        requested = [refs[1], refs[0], refs[1]]
        main = threading.get_ident(); reads = []; sql = []
        original = store_module.file_hash
        def hash_whole(path):
            reads.append((Path(path), threading.get_ident()))
            return original(path)
        monkeypatch.setattr(store_module, 'file_hash', hash_whole)
        store.connection.set_trace_callback(lambda statement: sql.append((statement, threading.get_ident(), len(reads))))
        actual = store.verify_artifacts(iter(requested), workers=workers)
        assert actual == tuple(store.object_path(ref) for ref in requested)
        assert Counter(path for path, _ in reads) == Counter(actual)
        assert all((thread == main) == (workers == 1) for _, thread in reads)
        assert [statement.split()[0] for statement, _, _ in sql] == ['SAVEPOINT', 'SELECT', 'SELECT', 'SELECT', 'RELEASE']
        assert all(thread == main and count == 3 for _, thread, count in sql)
        assert not store.connection.in_transaction
        reads.clear(); sql.clear()
        assert store.verify_artifact(refs[0]) == store.object_path(refs[0])
        assert len(reads) == 1 and reads[0][1] == main
        assert [statement.split()[0] for statement, _, _ in sql] == ['SELECT']


@pytest.mark.parametrize('mutation', ('corrupt', 'missing', 'symlink', 'unindexed'))
def test_original_object_and_index_rejections(tmp_path, mutation):
    with EpisodeStore(tmp_path / 'store.db') as store:
        paths, refs = seed(store, tmp_path)
        reference = refs[0]; destination = store.object_path(reference)
        if mutation == 'corrupt': destination.write_bytes(b'z')
        elif mutation == 'missing': destination.unlink()
        elif mutation == 'symlink': destination.unlink(); destination.symlink_to(paths[0])
        else:
            unindexed = tmp_path / 'unindexed'; unindexed.write_bytes(b'unindexed full bytes')
            reference, _ = store._persist_artifact_object(unindexed)
        before = store.connection.execute('SELECT * FROM artifacts').fetchall()
        with pytest.raises(StoreError) as single: store.verify_artifact(reference)
        with pytest.raises(StoreError) as bulk: store.verify_artifacts([refs[1], reference], workers=4)
        assert str(single.value) == str(bulk.value)
        assert not store.connection.in_transaction
        assert store.connection.execute('SELECT * FROM artifacts').fetchall() == before


def test_all_workers_join_before_failure_or_sql(tmp_path, monkeypatch):
    with EpisodeStore(tmp_path / 'store.db') as store:
        _, refs = seed(store, tmp_path)
        started = threading.Event(); finished = threading.Event(); sql = []
        original = store._verify_artifact_object
        def verify(reference):
            if reference == refs[0]:
                assert started.wait(2)
                raise OSError('synthetic full-read failure')
            started.set(); result = original(reference); time.sleep(.03); finished.set()
            return result
        monkeypatch.setattr(store, '_verify_artifact_object', verify)
        store.connection.set_trace_callback(sql.append)
        with pytest.raises(OSError, match='synthetic full-read failure'):
            store.verify_artifacts(refs, workers=4)
        assert finished.is_set() and sql == []


@pytest.mark.parametrize('failure', ('none', 'unindexed', 'sql_denied'))
def test_bulk_never_commits_existing_transaction_even_same_savepoint_name(tmp_path, failure):
    with EpisodeStore(tmp_path / 'store.db') as store:
        _, refs = seed(store, tmp_path)
        missing = tmp_path / 'not_indexed'; missing.write_bytes(b'no index')
        missing_ref, _ = store._persist_artifact_object(missing)
        marker = 'sha256:' + 'f' * 64
        store.connection.execute('SAVEPOINT aprof_verify_artifacts')
        store.connection.execute('INSERT INTO artifacts(content_hash) VALUES (?)', (marker,))
        threads = []; main = threading.get_ident()
        if failure == 'sql_denied':
            def deny_select(action, *args):
                threads.append(threading.get_ident())
                return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_SELECT else sqlite3.SQLITE_OK
            store.connection.set_authorizer(deny_select)
        try:
            if failure == 'none': store.verify_artifacts(refs, workers=4)
            else:
                with pytest.raises((StoreError, sqlite3.DatabaseError)):
                    store.verify_artifacts([missing_ref] if failure == 'unindexed' else refs, workers=4)
        finally: store.connection.set_authorizer(None)
        assert store.connection.in_transaction
        assert store.connection.execute('SELECT 1 FROM artifacts WHERE content_hash=?', (marker,)).fetchone() == (1,)
        store.connection.execute('ROLLBACK TO aprof_verify_artifacts')
        assert store.connection.execute('SELECT 1 FROM artifacts WHERE content_hash=?', (marker,)).fetchone() is None
        store.connection.execute('RELEASE aprof_verify_artifacts')
        assert not store.connection.in_transaction
        assert all(thread == main for thread in threads)


@pytest.mark.parametrize('workers', (True, 0, 5))
def test_invalid_worker_bound(tmp_path, workers):
    with EpisodeStore(tmp_path / 'store.db') as store:
        with pytest.raises(StoreError, match='integer from 1 to 4'):
            store.verify_artifacts([], workers=workers)


@pytest.mark.parametrize('substitution', ('none', 'missing', 'reversed'))
def test_collector_requires_exact_complete_path_sequence(tmp_path, monkeypatch, substitution):
    with EpisodeStore(tmp_path / 'store.db') as store:
        _, refs = seed(store, tmp_path); expected = {'b': refs[1], 'a': refs[0]}
        original = store.verify_artifacts
        def altered(digests, *, workers=1):
            assert workers == 4
            paths = original(digests, workers=workers)
            return paths if substitution == 'none' else paths[:-1] if substitution == 'missing' else paths[::-1]
        monkeypatch.setattr(store, 'verify_artifacts', altered)
        if substitution == 'none':
            result = collector.verify_profile_cas(expected, store, deadline=time.monotonic() + 30)
            assert list(result.items()) == list(expected.items())
        else:
            with pytest.raises(ValueError, match='incomplete profile|different profile object or order'):
                collector.verify_profile_cas(expected, store, deadline=time.monotonic() + 30)
