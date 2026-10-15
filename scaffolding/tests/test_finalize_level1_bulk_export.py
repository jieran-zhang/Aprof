"""CPU-only export checks using finalized attempts and their real CAS evidence."""
from copy import deepcopy
from pathlib import Path

import pytest

from aprof_runtime.errors import StoreError
from aprof_runtime.exploration import ExplorationGate
from aprof_runtime.jsonio import canonical_json
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import validate_optimization_trace
from test_finalize_level1_campaign import dump, finalize, fixture_run


@pytest.fixture
def finalized_run(tmp_path):
    run = fixture_run(tmp_path, ('build_failed', 'build_failed'))
    finalizer = finalize.Finalizer(run)
    finalizer.finalize_operator('exp')
    return run, finalizer


def write_records(path, records):
    path.write_text(''.join(canonical_json(record) + '\n' for record in records))


def test_export_uses_one_real_bulk_write_per_split_and_preserves_bytes(finalized_run, monkeypatch):
    run, finalizer = finalized_run
    task_summaries = run / 'tasks/exp/optimization_traces.jsonl'
    expected_records = finalize.rows(task_summaries)
    bulk_write = finalize.write_optimization_traces
    evaluate = ExplorationGate.evaluate
    calls = []
    replays = []

    def bulk_spy(path, records, store=None):
        records = list(records)
        calls.append((Path(path), deepcopy(records), store is not None))
        return bulk_write(path, records, store)

    def replay_spy(self, *args, **kwargs):
        replays.append(None)
        return evaluate(self, *args, **kwargs)

    def single_write_is_forbidden(*args, **kwargs):
        pytest.fail('export must send all summaries for a split to the bulk writer')

    monkeypatch.setattr(finalize, 'write_optimization_traces', bulk_spy)
    monkeypatch.setattr(finalize, 'write_optimization_trace', single_write_is_forbidden)
    monkeypatch.setattr(ExplorationGate, 'evaluate', replay_spy)

    expected_calls = [
        (run / 'train/optimization_traces.jsonl', expected_records, True),
        (run / 'validation/optimization_traces.jsonl', [], True),
    ]
    result = finalizer.export()
    assert calls == expected_calls
    assert replays, 'bulk export must replay actual exploration evidence'
    assert result['attempt_count'] == 2
    assert result['verification']['train']['summaries'] == {'valid': True, 'attempt_count': 2}
    assert result['verification']['validation']['summaries'] == {'valid': True, 'attempt_count': 0}
    assert (run / 'train/optimization_traces.jsonl').read_bytes() == task_summaries.read_bytes()
    assert (run / 'validation/optimization_traces.jsonl').read_bytes() == b''
    assert (run / 'optimization_traces.jsonl').read_bytes() == task_summaries.read_bytes()

    outputs = [run / prefix / name for prefix in ('', 'train', 'validation')
               for name in ('trace_events.jsonl', 'optimization_traces.jsonl', 'episodes.jsonl')]
    outputs.append(run / 'campaign_summary.json')
    before = {path: path.read_bytes() for path in outputs}
    replay_count = len(replays)
    calls.clear()
    assert finalizer.export() == result
    assert calls == expected_calls
    assert len(replays) > replay_count, 'independent exports must verify evidence again'
    assert {path: path.read_bytes() for path in outputs} == before


@pytest.mark.parametrize('mutation', [
    'omitted_summary', 'duplicate_summary', 'foreign_task', 'foreign_candidate',
    'foreign_run', 'wrong_split', 'duplicate_report_candidate', 'wrong_report_count',
])
def test_export_requires_exact_task_summary_roster(finalized_run, mutation):
    run, finalizer = finalized_run
    path = run / 'tasks/exp/optimization_traces.jsonl'
    records = finalize.rows(path)
    report_path = run / 'tasks/exp/finalization_report.json'
    report = finalize.read(report_path)
    if mutation == 'omitted_summary':
        records.pop()
    elif mutation == 'duplicate_summary':
        records.append(deepcopy(records[0]))
    elif mutation == 'foreign_task':
        records[0]['identity']['task_id'] = 'norm'
    elif mutation == 'foreign_candidate':
        records[0]['identity']['candidate_id'] = 'exp-foreign'
    elif mutation == 'foreign_run':
        records[0]['identity']['run_id'] = 'another-campaign'
    elif mutation == 'wrong_split':
        records[0]['identity']['split'] = 'validation'
    elif mutation == 'duplicate_report_candidate':
        report['attempts'][1]['candidate_id'] = report['attempts'][0]['candidate_id']
    elif mutation == 'wrong_report_count':
        report['attempt_count'] += 1
    write_records(path, records)
    dump(report_path, report)

    with pytest.raises(StoreError):
        finalizer.export()
    assert not (run / 'train/optimization_traces.jsonl').exists()
    assert not (run / 'campaign_summary.json').exists()


def test_export_resumes_a_valid_partial_split(finalized_run):
    run, finalizer = finalized_run
    task_path = run / 'tasks/exp/optimization_traces.jsonl'
    records = finalize.rows(task_path)
    split_path = run / 'train/optimization_traces.jsonl'
    write_records(split_path, records[:1])

    result = finalizer.export()
    assert result['attempt_count'] == 2
    assert result['verification']['train']['summaries']['attempt_count'] == 2
    assert split_path.read_bytes() == task_path.read_bytes()


def test_export_rejects_a_valid_foreign_summary_already_in_split(finalized_run):
    run, finalizer = finalized_run
    foreign = deepcopy(finalize.rows(run / 'tasks/exp/optimization_traces.jsonl')[0])
    foreign['identity']['task_id'] = 'norm'
    foreign['identity']['attempt_id'] = 'norm-foreign'
    # This is valid runtime evidence; only the frozen export roster excludes it.
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        validate_optimization_trace(foreign, store)
    split_path = run / 'train/optimization_traces.jsonl'
    write_records(split_path, [foreign])
    before = split_path.read_bytes()

    with pytest.raises(StoreError):
        finalizer.export()
    assert split_path.read_bytes() == before
    assert not (run / 'campaign_summary.json').exists()


@pytest.mark.parametrize('corruption', ['incomplete_jsonl', 'conflicting_summary', 'cas'])
def test_export_does_not_overwrite_corrupt_existing_split(finalized_run, corruption):
    run, finalizer = finalized_run
    finalizer.export()
    split_path = run / 'train/optimization_traces.jsonl'
    if corruption == 'incomplete_jsonl':
        split_path.write_bytes(split_path.read_bytes()[:-1])
    elif corruption == 'conflicting_summary':
        records = finalize.rows(split_path)
        records[0]['lesson']['limitations'].append('Unverified alteration to an immutable summary.')
        write_records(split_path, records)
    else:
        record = finalize.rows(split_path)[0]
        with EpisodeStore(run / 'train/episodes.sqlite') as store:
            artifact = store.verify_artifact(record['provenance']['patch_hash'])
            artifact.write_bytes(b'corrupt CAS bytes')
    before = split_path.read_bytes()
    compatibility_before = (run / 'optimization_traces.jsonl').read_bytes()
    report_before = (run / 'campaign_summary.json').read_bytes()

    with pytest.raises(StoreError):
        finalizer.export()
    assert split_path.read_bytes() == before
    assert (run / 'optimization_traces.jsonl').read_bytes() == compatibility_before
    assert (run / 'campaign_summary.json').read_bytes() == report_before
