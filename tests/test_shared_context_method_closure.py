import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import close_shared_context_method_block as module


def fixture(tmp_path, monkeypatch, *, outcome='quality_failed', candidates=None, running=False):
    task = {'candidates': candidates or {}, 'used': {'source': 0}, 'stages': {
        'exp-baseline-qualification': {'attempts': [{'outcome': None if running else outcome}]}}}
    ledger = SimpleNamespace(state={'tasks': {'exp': task}}, config={'tasks': {'exp': {'split': 'train'}}},
                             status=lambda: {'tasks': {'exp': {'remaining': {'source': 6}}}})
    monkeypatch.setattr(module, 'Ledger', lambda _: ledger)
    monkeypatch.setattr(module, 'verify_report', lambda *args: None)
    directory = tmp_path / 'tasks/exp'
    q = directory / 'qualification'
    q.mkdir(parents=True)
    failures = [{'check': 'aa_equivalence', 'status': 'precision_insufficient'}]
    records = {'qualification-result.json': {'status': outcome, 'error': None, 'failures': failures,
                    'cases': [1], 'successful_sessions': 12, 'actual_costs': {'native_sessions_completed': 12}},
               'qualification/manifest.json': {'task_id': 'exp', 'run_id': tmp_path.name},
               'qualification/sessions.json': {},
               'qualification/report.json': {'measurement_quality': {'observed_checks_pass': outcome == 'passed', 'failures': failures}}}
    for name in ('agent-initial-review.json', 'baseline-binding.json', 'input-bindings.json',
                 'baseline-memory-plan.json', 'qualification/wrapper-started.json', 'qualification/memory-plan-binding.json'):
        records[name] = {}
    for name, value in records.items():
        (directory / name).write_text(json.dumps(value))
    return directory


@pytest.mark.parametrize('options,match', [({'running': True}, 'running'),
                                        ({'candidates': {'exp001': {}}}, 'Candidate-bearing'),
                                        ({'outcome': 'passed'}, 'quality_failed')])
def test_refuses_unjustified_blocker(tmp_path, monkeypatch, options, match):
    directory = fixture(tmp_path, monkeypatch, **options)
    with pytest.raises(ValueError, match=match):
        module.close(tmp_path, 'exp')
    assert not (directory / 'closure.json').exists()


def test_retains_uncertainty_without_creating_attempt_or_overwriting(tmp_path, monkeypatch):
    directory = fixture(tmp_path, monkeypatch)
    before = {p: p.read_bytes() for p in directory.rglob('*.json')}
    result = module.close(tmp_path, 'exp')
    assert result['source_attempts'] == []
    assert result['candidate_performance']['speedup'] is None
    assert result['qualification']['failure_groups'] == [{'check': 'aa_equivalence', 'status': 'precision_insufficient', 'count': 1}]
    assert all(p.read_bytes() == data for p, data in before.items())
    with pytest.raises(FileExistsError):
        module.close(tmp_path, 'exp')
