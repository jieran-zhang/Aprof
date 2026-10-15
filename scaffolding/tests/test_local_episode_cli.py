"""Local CLI finalization uses the real route/gate without appending an episode."""
import json

import pytest

from aprof_runtime import cli
from aprof_runtime.jsonio import to_primitive
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.store import EpisodeStore
from test_measurement_entry import _evidence
from test_runtime import finalization_inputs, noop_request_dict, request_dict
from test_shared_measurement_admission import archive, draft
from test_task_window_measurement_admission import window_archive


def arguments(tmp_path, request=None):
    context, request, graph = finalization_inputs(
        noop_request_dict() if request is None else request, noop=request is None)
    argv = ['episode', 'finalize']
    for name, value in [('context', context), ('request', request), ('graph', graph)]:
        path = tmp_path / (name + '.json')
        path.write_text(json.dumps(to_primitive(value)))
        argv.extend(['--' + name, str(path)])
    return argv


def no_database(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('local finalization must not open EpisodeStore')
    monkeypatch.setattr(cli, 'EpisodeStore', forbidden)


def test_local_noop_has_real_route_and_gate_without_writes(tmp_path, monkeypatch, capsys):
    argv = arguments(tmp_path)
    reader = LocalEvidence(tmp_path / 'records')
    index = reader.write_index(tmp_path / 'local-index.json')
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    no_database(monkeypatch)
    assert cli.main([*argv, '--local-index', str(index)]) == 0
    result = json.loads(capsys.readouterr().out)['result']
    assert result['store_sequences'] == []
    assert result['storage_mode'] == 'local_profile_only'
    assert result['archive_performed'] is False
    episode, = result['episodes']
    assert episode['outcome']['verdict'] == 'verified_noop'
    assert episode['outcome']['selected_as_best'] is False
    assert episode['graph_hash'].startswith('sha256:')
    assert episode['episode_hash'].startswith('sha256:')
    assert before == {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_local_index_and_store_are_mutually_exclusive(tmp_path):
    with pytest.raises(SystemExit) as error:
        cli.main([*arguments(tmp_path), '--local-index', 'index.json', '--store', 'db.sqlite'])
    assert error.value.code == 2
    assert not (tmp_path / 'db.sqlite').exists()


def test_local_route_is_still_recomputed(tmp_path, monkeypatch, capsys):
    argv = arguments(tmp_path)
    path = tmp_path / 'request.json'
    request = json.loads(path.read_text())
    request['candidates'][0]['route']['policy_version'] = 'forged-policy'
    path.write_text(json.dumps(request))
    index = LocalEvidence(tmp_path / 'records').write_index(tmp_path / 'local-index.json')
    no_database(monkeypatch)
    assert cli.main([*argv, '--local-index', str(index)]) == 2
    output = capsys.readouterr()
    assert output.out == '' and json.loads(output.err)['ok'] is False


def test_store_finalization_still_appends(tmp_path, capsys):
    database = tmp_path / 'episodes.sqlite'
    argv = arguments(tmp_path)
    source = tmp_path / 'empty-source'; source.write_bytes(b'')
    with EpisodeStore(database) as store:
        digest = store.register_artifact(source)
    request = tmp_path / 'request.json'
    request.write_text(request.read_text().replace('sha256:' + 'a' * 64, digest))
    assert cli.main([*argv, '--store', str(database)]) == 0
    result = json.loads(capsys.readouterr().out)['result']
    assert set(result) == {'episodes', 'store_sequences'}
    assert result['store_sequences'] == [1]
    with EpisodeStore(database) as store:
        assert store.connection.execute('SELECT COUNT(*) FROM episodes').fetchone()[0] == 1
        store.verify_integrity()


@pytest.mark.parametrize('mutation', [None, 'missing_measurement', 'changed_task_csv'])
def test_local_cli_replays_complete_task_evidence(window_archive, tmp_path, monkeypatch, capsys, mutation):
    store, config, expected, evidence, _ = _evidence(window_archive)
    request = request_dict(config['candidate_id'])
    request['candidates'][0]['session_id'] = config['session_id']
    request['candidates'][0]['source_hashes'] = expected['source_hashes']
    evidence['static_review'] = 'failed'  # A synthetic fixture is never a production acceptance.
    request['evidence'][0] = evidence
    argv = arguments(tmp_path, request)
    reader = LocalEvidence(tmp_path / 'records')
    for digest, in store.connection.execute('SELECT content_hash FROM artifacts'):
        if mutation == 'missing_measurement' and digest == evidence['artifacts']['measurement_admission']:
            continue
        reader.register_artifact(store.object_path(digest))
    index = reader.write_index(tmp_path / 'local-index.json')
    if mutation == 'changed_task_csv':
        table_ref = window_archive[1]['sessions'][0]['task_table_ref']
        store.object_path(table_ref).write_text('corrupt Task table')
    no_database(monkeypatch)
    status = cli.main([*argv, '--local-index', str(index)])
    output = capsys.readouterr()
    if mutation is not None:
        assert status == 2 and output.out == ''
        assert json.loads(output.err)['ok'] is False
    else:
        assert status == 0
        result = json.loads(output.out)['result']
        assert result['store_sequences'] == [] and result['archive_performed'] is False
        episode, = result['episodes']
        assert episode['outcome']['verdict'] == 'static_rejected'
        assert episode['outcome']['selected_as_best'] is False
        assert len(episode['evidence']['baseline_samples_ns']) == 30
        assert episode['evidence']['artifacts']['measurement_admission'] == evidence['artifacts']['measurement_admission']
    assert list(reader.directory.iterdir()) == []
    assert store.connection.execute('SELECT COUNT(*) FROM episodes').fetchone()[0] == 0
