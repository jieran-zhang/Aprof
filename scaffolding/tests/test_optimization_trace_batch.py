from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import stat

import pytest

from aprof_runtime import traces
from aprof_runtime.errors import ContractError, StoreError
from aprof_runtime.exploration import ExplorationGate
from aprof_runtime.jsonio import canonical_json, content_hash
from aprof_runtime.store import EpisodeStore
from test_traces_exploration import request_fixture


@pytest.fixture
def store(tmp_path):
    with EpisodeStore(tmp_path / 'episodes.sqlite') as value:
        yield value


def summary(store, identifier):
    digest = traces.register_json_artifact(store, {'source': identifier})
    return traces.make_optimization_trace({'run_id': 'run', 'task_id': 'task',
        'session_id': 'session', 'attempt_id': identifier, 'candidate_id': 'c-' + identifier,
        'operator': 'exp', 'split': 'train', 'source_parent_hash': digest})


def payload(records):
    return ''.join(canonical_json(record) + '\n' for record in records).encode()


def test_batch_preserves_order_and_retries_validate_without_rewriting(tmp_path, store, monkeypatch):
    path = tmp_path / 'summaries.jsonl'
    first, second, third = [summary(store, name) for name in ('first', 'second', 'third')]
    traces.write_optimization_trace(path, first, store)
    original_validate = traces.validate_optimization_trace
    checked = []

    def check(record, store=None):
        checked.append(record['identity']['attempt_id'])
        return original_validate(record, store)

    monkeypatch.setattr(traces, 'validate_optimization_trace', check)
    assert traces.write_optimization_traces(path, iter([third, first, second, third]), store) == {
        'valid': True, 'attempt_count': 3}
    assert checked == ['first', 'third', 'second']
    assert path.read_bytes() == payload([first, third, second])
    checked.clear()

    def no_rewrite(*args):
        pytest.fail('an identical retry must retain existing bytes')

    monkeypatch.setattr(traces, '_atomic_jsonl', no_rewrite)
    assert traces.write_optimization_traces(path, [second, third, first], store)['attempt_count'] == 3
    assert checked == ['first', 'third', 'second']


@pytest.mark.parametrize('already_written', [False, True])
def test_conflicting_batch_is_atomic(tmp_path, store, already_written):
    path = tmp_path / 'summaries.jsonl'
    first, second = summary(store, 'first'), summary(store, 'second')
    if already_written:
        traces.write_optimization_trace(path, first, store)
    before = path.read_bytes() if path.exists() else None
    conflict = deepcopy(first)
    conflict['lesson']['next_step'] = 'different content for the same attempt'
    with pytest.raises(StoreError, match='immutable'):
        traces.write_optimization_traces(path, [second, first, conflict], store)
    assert (path.read_bytes() if path.exists() else None) == before


@pytest.mark.parametrize('corruption', ['duplicate', 'schema', 'partial'])
def test_existing_stream_corruption_is_never_repaired_implicitly(tmp_path, store, corruption):
    path = tmp_path / 'summaries.jsonl'
    first, second = summary(store, 'first'), summary(store, 'second')
    if corruption == 'duplicate':
        data = payload([first, first])
    elif corruption == 'schema':
        first['invented'] = True
        data = payload([first])
    else:
        data = payload([first]) + b'{"identity":'
    path.write_bytes(data)
    with pytest.raises((StoreError, ContractError)):
        traces.write_optimization_traces(path, [second], store)
    assert path.read_bytes() == data


def test_invalid_new_summary_leaves_existing_bytes_unchanged(tmp_path, store):
    path = tmp_path / 'summaries.jsonl'
    first, second = summary(store, 'first'), summary(store, 'second')
    traces.write_optimization_traces(path, [first], store)
    second['null_reasons'].clear()
    before = path.read_bytes()
    with pytest.raises(ContractError, match='every null'):
        traces.write_optimization_traces(path, [second], store)
    assert path.read_bytes() == before


def test_duplicate_json_boolean_is_not_equal_to_an_integer(tmp_path, store):
    path = tmp_path / 'summaries.jsonl'
    record = summary(store, 'first')
    invalid = deepcopy(record)
    invalid['validation']['passed_count'] = False
    assert record == invalid  # Python equality alone would hide invalid JSON schema content.
    with pytest.raises(StoreError, match='immutable'):
        traces.write_optimization_traces(path, [record, invalid], store)
    assert not path.exists()


@pytest.mark.parametrize('repeat_input', [False, True])
def test_later_call_rehashes_existing_cas_even_without_new_records(tmp_path, store, repeat_input):
    path = tmp_path / 'summaries.jsonl'
    record = summary(store, 'first')
    traces.write_optimization_traces(path, [record], store)
    before = path.read_bytes()
    store.object_path(record['identity']['source_parent_hash']).write_text('corrupt after earlier verification')
    with pytest.raises(StoreError, match='does not match'):
        traces.write_optimization_traces(path, [record] if repeat_input else [], store)
    assert path.read_bytes() == before


def test_batch_replays_real_gate_and_rejects_rehashed_forged_outcome(tmp_path, store, monkeypatch):
    request = request_fixture(tmp_path, store, failed=True)
    candidate = request['candidates'][0]
    outcome = ExplorationGate().evaluate(request, store=store)[0]
    record = traces.make_optimization_trace({'run_id': 'run', 'task_id': 'task',
        'session_id': 'session', 'attempt_id': 'a1', 'candidate_id': 'c1',
        'operator': 'exp', 'split': 'train', 'source_parent_hash': candidate['source_hashes']['baseline']},
        provenance={'baseline_source_hash': candidate['source_hashes']['baseline'],
            'candidate_source_hash': candidate['source_hashes']['candidate'],
            'patch_hash': candidate['patch_artifact_hash']},
        intervention={'handler': {'id': candidate['handler_id'], 'version': candidate['handler_version']},
            'parameters': candidate['parameters']},
        result={'verdict': outcome['verdict'], 'exploration_outcome_ref': traces.register_json_artifact(store, outcome)})
    evaluate = ExplorationGate.evaluate
    calls = []

    def replay(self, request, *, store):
        calls.append(request['frozen_manifest_hash'])
        return evaluate(self, request, store=store)

    monkeypatch.setattr(ExplorationGate, 'evaluate', replay)
    path = tmp_path / 'summaries.jsonl'
    traces.write_optimization_traces(path, [record, record], store)
    assert len(calls) == 1
    traces.write_optimization_traces(path, [record], store)
    assert len(calls) == 2
    forged = deepcopy(outcome)
    forged['verdict'] = 'production_safe_gain'
    forged['outcome_hash'] = content_hash({key: value for key, value in forged.items() if key != 'outcome_hash'})
    record['result']['verdict'] = forged['verdict']
    record['result']['exploration_outcome_ref'] = traces.register_json_artifact(store, forged)
    with pytest.raises(StoreError, match='does not replay'):
        traces.write_optimization_traces(tmp_path / 'forged.jsonl', [record], store)
    assert len(calls) == 3
    assert not (tmp_path / 'forged.jsonl').exists()


def test_interrupted_replace_preserves_old_file_and_retry_commits(tmp_path, store, monkeypatch):
    path = tmp_path / 'summaries.jsonl'
    first, second = summary(store, 'first'), summary(store, 'second')
    traces.write_optimization_traces(path, [first], store)
    before = path.read_bytes()

    def interrupted(*args):
        raise OSError('simulated failure before atomic replacement')

    with monkeypatch.context() as patch:
        patch.setattr(traces.os, 'replace', interrupted)
        with pytest.raises(OSError, match='simulated failure'):
            traces.write_optimization_traces(path, [first, second], store)
    assert path.read_bytes() == before
    assert not list(tmp_path.glob('.trace-*'))
    assert traces.write_optimization_traces(path, [first, second], store)['attempt_count'] == 2
    assert path.read_bytes() == payload([first, second])


def test_empty_batch_creates_empty_export(tmp_path, store):
    path = tmp_path / 'empty.jsonl'
    assert traces.write_optimization_traces(path, [], store) == {'valid': True, 'attempt_count': 0}
    assert path.read_bytes() == b''


def test_retry_finishes_directory_sync_after_installed_file(tmp_path, store, monkeypatch):
    path = tmp_path / 'summaries.jsonl'
    record = summary(store, 'first')
    fsync = traces.os.fsync
    directory_calls = []

    def sync(fd):
        if stat.S_ISDIR(traces.os.fstat(fd).st_mode):
            directory_calls.append(fd)
            if len(directory_calls) == 1:
                raise OSError('simulated failure after rename')
        return fsync(fd)

    monkeypatch.setattr(traces.os, 'fsync', sync)
    with pytest.raises(OSError, match='after rename'):
        traces.write_optimization_traces(path, [record], store)
    assert path.read_bytes() == payload([record])
    assert traces.write_optimization_traces(path, [record], store)['attempt_count'] == 1
    assert len(directory_calls) == 2
    assert path.read_bytes() == payload([record])


def test_concurrent_batches_do_not_lose_attempts(tmp_path, store):
    path = tmp_path / 'summaries.jsonl'
    records = [summary(store, str(index)) for index in range(8)]
    # The file-lock test omits a store to avoid sharing SQLite connections across
    # threads; independent tests above verify CAS and gate checks with a store.
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda record: traces.write_optimization_traces(path, [record]), records))
    actual = [json.loads(line) for line in path.read_text().splitlines()]
    assert {item['identity']['attempt_id'] for item in actual} == {str(index) for index in range(8)}
    assert traces.verify_optimization_traces(path, store)['attempt_count'] == 8
