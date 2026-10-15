"""Whole-screen drain boundaries; CPU receipts are not measurement admission."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

import task_rule_controller as controller
from aprof_runtime.errors import ContractError
from task_budget import CollectionBoundaryStop
from task_rule_admission import _verify_screen_unit
from screen_parser import CASES


POLICY = dict(kind='finish_started_unit_v1', reserve_seconds=400,
              task_unit_seconds=300, pmu_unit_seconds=300, terminal_seconds=20)


@pytest.mark.parametrize('start,policy', [(599, POLICY), (600, POLICY), (650, None)])
def test_screen_gets_one_deadline_or_starts_no_collection(tmp_path, monkeypatch, start, policy):
    clock = {'mono': start}
    monkeypatch.setattr(controller.time, 'monotonic', lambda: clock['mono'])
    monkeypatch.setattr(controller.time, 'time', lambda: 2000 + clock['mono'] - start)
    local = controller.LocalEvidence(tmp_path / 'records')
    events, calls = [], []
    recorder = SimpleNamespace(start=lambda stage: events.append(('started', stage)),
        complete=lambda stage, evidence, **kwargs: events.append(('completed', stage, evidence, kwargs)))

    def collect(*args, deadline, **kwargs):
        calls.append(deadline)
        assert args[3] == tmp_path / 'screen'
        # A started screen crosses S=600, completes all its work, and is not stopped at S.
        clock['mono'] += 134
        output = args[3]; output.mkdir()
        reader = controller.LocalEvidence(output / 'records')
        controller.bridge.save(output / 'screen-result.json', {'status': 'passed', 'CPU': True})
        reader.register_artifact(output / 'screen-result.json')
        return {'local_index': reader.write_index(output / 'local-index.json')}

    monkeypatch.setattr(controller.screen, 'collect_screen', collect)
    args = (local, recorder, {'prepared_dir': '/CPU/prepared', 'physical_device': 0},
            tmp_path / 'assembly', tmp_path / 'build.json', tmp_path)
    if start == 600:
        with pytest.raises(CollectionBoundaryStop):
            controller._screen_stage(*args, deadline=1000, policy=policy)
        assert calls == [] and events == [('started', 'screen')]
        assert not (tmp_path / 'screen').exists()
        assert not (tmp_path / 'screen-collection-unit.json').exists()
    else:
        controller._screen_stage(*args, deadline=1000, policy=policy)
        assert calls == [899 if policy else 1000]
        assert events[-1][:2] == ('completed', 'screen')
        evidence = events[-1][2]
        assert len(evidence) == (2 if policy else 1)
        if policy:
            assert controller.read(local, evidence[1]) == dict(schema_version=1, started_at=2000,
                started_monotonic=599, deadline_monotonic=899)


def fixture(tmp_path, mutation=None):
    local = controller.LocalEvidence(tmp_path / 'records')
    unit = dict(schema_version=1, started_at=1000, started_monotonic=599, deadline_monotonic=899)
    sessions = []
    for index, cid in enumerate(CASES['exp']):
        start = 1002 + 20 * index
        session = dict(case_id=cid, started_at=start, finished_at=start + 17, oracles={})
        for offset, name in enumerate(('capture', 'export', 'baseline', 'candidate')):
            raw = dict(started_at=start + 3 * offset, ended_at=start + 3 * offset + 2,
                       timeout_seconds=1300 - start - 3 * offset, exit_code=0, error=None)
            embedded = dict(raw, log_hash=local.register_json(raw))
            if name in ('baseline', 'candidate'):
                embedded['result_ref'] = local.register_json({'CPU': name})
                session['oracles'][name] = embedded
            else:
                session[name] = embedded
        sessions.append(session)
    result = dict(started_at=1001, finished_at=1135, sessions=sessions)
    if mutation:
        mutation(unit, result, local)
    report_ref = local.register_json(result)
    evidence = [report_ref, local.register_json(unit)]
    report = dict(operator='exp', screen_report_ref=report_ref)
    launch = dict(schema_version=2, started_monotonic=100, monotonic_deadline=1000)
    return local, report, evidence, [995, 1400], launch, deepcopy(POLICY)


def test_replay_all_six_cases_inside_one_original_unit(tmp_path):
    _verify_screen_unit(*fixture(tmp_path))


def actual_change(unit, result, local, **changes):
    capture = result['sessions'][0]['capture']
    raw = controller.read(local, capture['log_hash'])
    raw.update(changes)
    capture.clear()
    capture.update(raw, log_hash=local.register_json(raw))


@pytest.mark.parametrize('mutation', [
    lambda u, r, s: u.update(started_monotonic=600, deadline_monotonic=900),
    lambda u, r, s: u.update(deadline_monotonic=900),
    lambda u, r, s: u.update(started_monotonic=99, deadline_monotonic=399),
    lambda u, r, s: u.update(started_at=994),
    lambda u, r, s: r.update(finished_at=1301),
    lambda u, r, s: r['sessions'].pop(),
    lambda u, r, s: r['sessions'][0]['oracles'].pop('candidate'),
    lambda u, r, s: r['sessions'][0]['capture'].update(timeout_seconds=1),
    lambda u, r, s: actual_change(u, r, s, timeout_seconds=1000),
    lambda u, r, s: actual_change(u, r, s, ended_at=1301),
    lambda u, r, s: actual_change(u, r, s, started_at=999),
    lambda u, r, s: actual_change(u, r, s, exit_code=1),
])
def test_replay_rejects_late_renewed_incomplete_or_substituted_screen(tmp_path, mutation):
    with pytest.raises((ValueError, ContractError)):
        _verify_screen_unit(*fixture(tmp_path, mutation))


def test_new_policy_cannot_omit_unit_receipt(tmp_path):
    args = list(fixture(tmp_path)); args[2] = args[2][:1]
    with pytest.raises(ValueError, match='receipt missing'):
        _verify_screen_unit(*args)
