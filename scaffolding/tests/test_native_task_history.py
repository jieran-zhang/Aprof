"""Historical successes and cancelled attempts never grant method admission."""
from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collection/scripts'))
import replay_task_measurement_history as history
import replay_task_cancellation as cancelled
import probe_native_task_profile as facility
from run_shared_timing_confirmation import binding


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    prior = tmp_path / 'prior.json'
    prior.write_text(json.dumps({'purpose': 'retained_history_for_task_duration_method_qualification'}))
    anchor = tmp_path / 'anchor.json'; anchor.write_text('{}')
    cost = tmp_path / 'cost.json'; cost.write_text('{}')
    value = {'schema_version': 1,
        'purpose': 'retained_history_for_local_task_duration_method_qualification',
        'protocol': 'shared_buffer_msprof_task_v2', 'previous_history': binding(prior),
        'cancelled_task_attempt': {'audit': 'audit-ref', 'producer_archive': 'archive-ref'},
        'native_facility': {'directory': str(tmp_path), 'anchor': binding(anchor), 'source_archives': ['archive']},
        'cost_observations': [binding(cost)]}
    monkeypatch.setattr(history, 'replay_task_history', lambda reference: {'valid': True, 'eligible_for_publication': False})
    def cancellation(reference, *, producer_archive_ref):
        assert reference == 'audit-ref' and producer_archive_ref == 'archive-ref'
        return {'valid': True, 'complete': False, 'eligible_for_publication': False}
    monkeypatch.setattr(cancelled, 'replay_task_cancellation', cancellation)
    def probe(directory, anchor_path, *, source_archive_refs):
        assert directory == tmp_path and anchor_path == anchor and source_archive_refs == ['archive']
        return {'facility_complete': True, 'eligible_for_publication': False}
    monkeypatch.setattr(facility, 'replay', probe)
    return value


def test_native_history_preserves_no_admission(prepared):
    result = history.replay_local_task_history('history-ref', prepared, history.Evidence())
    assert result['valid'] is True and result['eligible_for_publication'] is False
    assert result['cancellation']['complete'] is False


@pytest.mark.parametrize('component', ['cancelled_task_attempt', 'native_facility', 'cost_observations'])
def test_cannot_omit_previous_attempts_or_costs(prepared, component):
    del prepared[component]
    with pytest.raises(ValueError, match='invalid local Task history'):
        history.replay_local_task_history('history-ref', prepared, history.Evidence())


@pytest.mark.parametrize('component', ['cancellation', 'facility'])
def test_historical_result_cannot_claim_publication(prepared, monkeypatch, component):
    if component == 'cancellation':
        monkeypatch.setattr(cancelled, 'replay_task_cancellation', lambda *a, **kw:
            {'valid': True, 'complete': False, 'eligible_for_publication': True})
    else:
        monkeypatch.setattr(facility, 'replay', lambda *a, **kw:
            {'facility_complete': True, 'eligible_for_publication': True})
    with pytest.raises(ValueError, match='gained admission|relabeled as admission'):
        history.replay_local_task_history('history-ref', prepared, history.Evidence())
