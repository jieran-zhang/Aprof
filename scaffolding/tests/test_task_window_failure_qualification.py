"""The next Task-window plan must bind the exact prior failed attempt."""

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
sys.path.insert(0, str(ROOT / 'skill-libs/graph-base/0.5.1/skills/ascendc-aprof-profiling/scripts'))
import qualify_task_window_timing_v051 as qualification


def test_prior_failure_ref_is_fixed(monkeypatch):
    reference = qualification.failed_attempt_ref()
    assert reference == {'path': str(qualification.FAILED_ATTEMPT_LEAF),
                         'sha256': qualification.FAILED_ATTEMPT_SHA256}
    monkeypatch.setattr(qualification, 'binding', lambda _: {'path': reference['path'],
                                                             'sha256': 'sha256:changed'})
    with pytest.raises(ValueError, match='prior Task-window failure leaf changed'):
        qualification.failed_attempt_ref()


def test_fixed_cost_design_and_prechange_package_bindings():
    assert qualification.cost_summary_ref()['sha256'] == qualification.COST_SUMMARY_SHA256
    assert qualification.design_package_ref()['sha256'] == qualification.PRE_CHANGE_PACKAGE_SHA256
    assert qualification.verify_cost_summary() == qualification.cost_summary_ref()


def test_current_target_is_ten_ms_and_old_history_remains_v1():
    qualification.task_modules()
    qualification.require_target_choice()
    assert qualification.PROTOCOL == 'shared_buffer_msprof_task_window_v4'
    assert qualification.PRIOR_PROTOCOL == 'shared_buffer_msprof_task_window_v2'
    assert qualification.HISTORICAL_PROTOCOL == 'shared_buffer_msprof_task_window_v1'


def test_v4_output_is_fresh_and_cannot_resume_v2(tmp_path):
    with pytest.raises(ValueError, match='fresh, distinct output directory'):
        qualification.prepare(tmp_path / 'production-task-window-confirmation-v2-10ms',
                              tmp_path / 'unused-history.json')
    output = tmp_path / qualification.PLANNED_OUTPUT_NAME
    output.mkdir()
    with pytest.raises(ValueError, match='no resume'):
        qualification.prepare(output, tmp_path / 'unused-history.json')


def test_four_completed_offline_studies_and_width4_restoration_are_planning_only(monkeypatch):
    refs = qualification.offline_cost_studies_ref()
    assert set(refs) == {'inventory', 'registration', 'width8_rejected',
                         'serial_cas_rejected', 'width4_restoration_ref'}
    for name in ('inventory', 'registration', 'width8_rejected', 'serial_cas_rejected'):
        summary = qualification.read(refs[name]['summary_ref']['path'])
        assert summary['accepted'] is False
        assert summary['eligible_for_publication'] is False
    assert qualification.read(refs['serial_cas_rejected']['summary_ref']['path'])['decision'] == (
        'reject_serial_cas_verification_cost_and_stage_complete_parallel_verification')
    restored = qualification.read(refs['width4_restoration_ref']['path'])
    assert restored['status'] == 'passed'
    assert restored['restored_exact_package_inventory'] is True
    original = qualification.binding
    path = refs['width8_rejected']['summary_ref']['path']
    monkeypatch.setattr(qualification, 'binding', lambda value: (
        {'path': str(value), 'sha256': 'sha256:changed'} if str(value) == path else original(value)))
    with pytest.raises(ValueError, match='offline cost study bytes changed'):
        qualification.offline_cost_studies_ref()


def test_v2_failed_attempt_replays_without_acceptance():
    reference = qualification.failed_attempt_v2_ref()
    result = qualification.replay_failed_attempt_v2(reference)
    assert result['valid'] is True
    assert result['accepted'] is False
    assert result['eligible_for_publication'] is False
    assert result['failure_reasons']['exp-confirmation'] == 'collection_timeout_114_of_120'
    assert result['failure_reasons']['sigmoid-confirmation'] == (
        'complete_collection_independent_replay_timeout')


def test_v2_failed_attempt_reference_cannot_be_substituted():
    reference = qualification.failed_attempt_v2_ref()
    with pytest.raises(ValueError, match='failed v2 leaf reference differs'):
        qualification.replay_failed_attempt_v2({**reference, 'sha256': 'sha256:changed'})
